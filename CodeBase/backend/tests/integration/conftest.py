from __future__ import annotations

import os
import pathlib
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.orm import Session

BACKEND = pathlib.Path(__file__).resolve().parents[2]
ADMIN_URL = os.environ.get(
    "PTCL_ADMIN_DATABASE_URL", "postgresql+psycopg://ptcl:ptcl@localhost:5432/postgres"
)
TEST_URL = os.environ.get(
    "PTCL_TEST_DATABASE_URL", "postgresql+psycopg://ptcl:ptcl@localhost:5432/ptcl_test"
)
TEST_DB_NAME = TEST_URL.rsplit("/", 1)[-1]

TABLES = ("audit_log", "exports", "corrections", "extractions", "documents", "users")

PIPELINE_VERSION: dict[str, Any] = {
    "profile": "prototype",
    "ocr_latin": "paddleocr-pp-ocrv5",
    "ocr_urdu": "qaari-0.1-urdu",
    "llm": "qwen2.5-7b-instruct",
    "prompt_hash": "sha256:2f1a9c",
    "schema_version": "0.3.1",
}


def _admin_engine() -> sqlalchemy.Engine:
    return sqlalchemy.create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")


def postgres_is_reachable() -> bool:
    try:
        with _admin_engine().connect():
            return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def database() -> str:
    if not postgres_is_reachable():
        pytest.skip(
            f"no Postgres at {ADMIN_URL}. Start one with: "
            "cd CodeBase/backend && docker compose up -d"
        )

    with _admin_engine().connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        ).scalar()
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))

    os.environ["DATABASE_URL"] = TEST_URL

    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings
    from app.db.session import get_engine, get_sessionmaker

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "app" / "db" / "migrations"))
    config.set_main_option("sqlalchemy.url", TEST_URL)
    command.upgrade(config, "head")

    return TEST_URL


@pytest.fixture
def session(database: str) -> Iterator[Session]:
    from app.db.session import get_engine, get_sessionmaker

    with get_engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))

    with get_sessionmaker()() as db:
        yield db


@pytest.fixture
def reviewer_id(session: Session) -> uuid.UUID:
    from app.db.models import User

    user = User(
        id=uuid.uuid4(),
        email="reviewer@ptcl.internal",
        name="Reviewer User",
        password_hash="x",
        role="reviewer",
    )
    session.add(user)
    session.commit()
    return user.id


@pytest.fixture
def document_id(session: Session) -> uuid.UUID:
    from app.db.models import Document

    document = Document(
        id=uuid.uuid4(),
        filename="invoice-2291.pdf",
        storage_path="var/uploads/aa/invoice-2291.pdf",
        content_type="application/pdf",
        byte_size=1024,
        sha256="a" * 64,
        data_classification="synthetic",
        status="needs_review",
        document_type="invoice",
    )
    session.add(document)
    session.commit()
    return document.id


def extraction_result(document_id: uuid.UUID, **fields: Any) -> dict[str, Any]:
    return {
        "document_id": str(document_id),
        "pipeline_version": PIPELINE_VERSION,
        "status": "needs_review",
        "document_type": {"value": "invoice", "confidence": 0.97},
        "fields": fields,
        "gates": [],
    }


def field(value: str | None, confidence: float = 0.9, verified: bool = False) -> dict[str, Any]:
    return {
        "value": value,
        "confidence": confidence,
        "verified": verified,
        "gate": None,
        "gate_error": None,
        "source": {"origin": "ocr_latin", "page": 1, "bbox": [0.1, 0.2, 0.5, 0.24]},
    }
