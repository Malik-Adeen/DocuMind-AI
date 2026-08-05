from __future__ import annotations

import json
import pathlib
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from tests import mock_server

SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[4] / "Docs" / "EXTRACTION_SCHEMA.json"


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


@pytest.fixture(autouse=True)
def reset_state() -> Iterator[None]:
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
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(mock_server.app) as test_client:
        yield test_client


@pytest.fixture
def reviewer(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "reviewer@ptcl.internal", "password": mock_server.PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def viewer(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@ptcl.internal", "password": mock_server.PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def assert_error_envelope(payload: dict[str, Any], code: str, retryable: bool) -> None:
    assert set(payload) == {"error"}
    envelope = payload["error"]
    assert set(envelope) == {"code", "message", "trace_id", "retryable"}
    assert envelope["code"] == code
    assert envelope["retryable"] is retryable
    assert isinstance(envelope["message"], str) and envelope["message"]
    assert isinstance(envelope["trace_id"], str) and envelope["trace_id"]
