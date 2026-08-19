from __future__ import annotations

import json
import os
import pathlib
import time
from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy import text

from tests import mock_server

BACKEND = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = BACKEND.parent.parent / "Docs" / "EXTRACTION_SCHEMA.json"

ADMIN_URL = os.environ.get(
    "PTCL_ADMIN_DATABASE_URL", "postgresql+psycopg://ptcl:ptcl@localhost:5432/postgres"
)
CONTRACT_URL = os.environ.get(
    "PTCL_CONTRACT_DATABASE_URL", "postgresql+psycopg://ptcl:ptcl@localhost:5432/ptcl_contract"
)
CONTRACT_DB_NAME = CONTRACT_URL.rsplit("/", 1)[-1]

PER_TEST_TABLES = ("audit_log", "exports", "corrections", "extractions", "documents")

MOCK_ONLY: dict[str, str] = {}

FAKE_VALID_IBAN = "PK36SCBL0000001123456702"


def _fake_extraction_json() -> str:
    return json.dumps(
        {
            "document_type": {"value": "invoice", "confidence": 0.95},
            "fields": {
                "iban": {
                    "value": FAKE_VALID_IBAN,
                    "confidence": 0.95,
                    "verified": False,
                    "source": {"origin": "llm_inferred", "raw_text": "mock"},
                }
            },
        }
    )


def _fake_transport(prompt: str) -> str:
    time.sleep(0.15)
    return _fake_extraction_json()


def _fake_ocr_reader() -> Any:
    from app.pipeline.ocr.paddle import TextRegion

    class _FakeOCR:
        def read(self, image_path: str, *, page: int = 1) -> list[TextRegion]:
            return [TextRegion(text="mock", confidence=1.0, bbox=(0.0, 0.0, 1.0, 1.0), page=page)]

        def page_count(self, image_path: str) -> int:
            return 1

    return _FakeOCR()


def _fake_llm_client() -> Any:
    from app.pipeline.llm.client import DeploymentProfile, Endpoint, LLMClient

    return LLMClient(
        profile=DeploymentProfile.PROTOTYPE,
        endpoint=Endpoint.LOCAL,
        model="fake-contract-test-model",
        transport=_fake_transport,
    )


def _install_fake_worker_dependencies() -> None:
    from app.workers import tasks as worker_tasks

    worker_tasks.build_ocr_reader = _fake_ocr_reader
    worker_tasks.build_llm_client = _fake_llm_client


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if item.originalname in MOCK_ONLY and "real" in item.callspec.params.values():  # type: ignore[attr-defined]
            item.add_marker(pytest.mark.skip(reason=MOCK_ONLY[item.originalname]))


def postgres_is_reachable() -> bool:
    try:
        with sqlalchemy.create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT").connect():
            return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def extraction_schema() -> dict[str, Any]:
    if not SCHEMA_PATH.exists():
        pytest.fail(f"EXTRACTION_SCHEMA.json not found at {SCHEMA_PATH}")
    schema: dict[str, Any] = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    return schema


@pytest.fixture(scope="session")
def validator(extraction_schema: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator(extraction_schema)


@pytest.fixture(scope="session")
def real_app(tmp_path_factory: pytest.TempPathFactory) -> FastAPI:
    if not postgres_is_reachable():
        pytest.skip(
            f"no Postgres at {ADMIN_URL}. Start one with: "
            "cd CodeBase/backend && docker compose up -d"
        )

    admin = sqlalchemy.create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": CONTRACT_DB_NAME}
        ).scalar()
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{CONTRACT_DB_NAME}"'))

    workspace = tmp_path_factory.mktemp("contract")
    os.environ["DATABASE_URL"] = CONTRACT_URL
    os.environ["UPLOAD_DIR"] = str(workspace / "uploads")
    os.environ["EXPORT_DIR"] = str(workspace / "exports")

    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings
    from app.db.session import get_engine, get_sessionmaker

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "app" / "db" / "migrations"))
    config.set_main_option("sqlalchemy.url", CONTRACT_URL)
    command.upgrade(config, "head")

    from app.db.seed import seed_users

    with get_engine().begin() as connection:
        connection.execute(
            text(f"TRUNCATE {', '.join((*PER_TEST_TABLES, 'users'))} RESTART IDENTITY CASCADE")
        )
    with get_sessionmaker()() as db:
        seed_users(db)

    _install_fake_worker_dependencies()

    from app.main import create_app

    return create_app()


def _reset_real_app() -> None:
    from app.core.config import get_settings
    from app.db.seed import seed_review_state_documents
    from app.db.session import get_engine, get_sessionmaker

    with get_engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(PER_TEST_TABLES)} RESTART IDENTITY CASCADE"))
    with get_sessionmaker()() as db:
        seed_review_state_documents(db, get_settings())


def _reset_mock() -> None:
    mock_server.CORRECTIONS.clear()
    mock_server.EXPORTS.clear()
    known = {
        mock_server.DOC_FAILED_GATE,
        mock_server.DOC_FORMAT_ONLY,
        mock_server.DOC_LOW_CONF_VERIFIED,
    }
    for document_id in list(mock_server.DOCUMENTS):
        if document_id not in known:
            del mock_server.DOCUMENTS[document_id]
    for document_id in known:
        mock_server.DOCUMENTS[document_id]["uploaded_monotonic"] = None


@pytest.fixture(params=["mock", "real"])
def under_test(request: pytest.FixtureRequest) -> str:
    target: str = request.param
    if target == "real":
        request.getfixturevalue("real_app")
    return target


@pytest.fixture
def client(under_test: str, request: pytest.FixtureRequest) -> Iterator[TestClient]:
    _reset_mock()
    if under_test == "mock":
        application: FastAPI = mock_server.app
    else:
        application = request.getfixturevalue("real_app")
        _reset_real_app()

    with TestClient(application) as test_client:
        yield test_client

    if under_test == "real":
        from app.services.documents import join_extraction_threads
        from app.services.exports import join_export_threads

        join_extraction_threads()
        join_export_threads()


def _login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": mock_server.PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def reviewer(client: TestClient) -> dict[str, str]:
    return _login(client, "reviewer@ptcl.internal")


@pytest.fixture
def viewer(client: TestClient) -> dict[str, str]:
    return _login(client, "viewer@ptcl.internal")


def assert_error_envelope(payload: dict[str, Any], code: str, retryable: bool) -> None:
    assert set(payload) == {"error"}
    envelope = payload["error"]
    assert set(envelope) == {"code", "message", "trace_id", "retryable"}
    assert envelope["code"] == code
    assert envelope["retryable"] is retryable
    assert isinstance(envelope["message"], str) and envelope["message"]
    assert isinstance(envelope["trace_id"], str) and envelope["trace_id"]
