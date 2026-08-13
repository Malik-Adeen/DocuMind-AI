from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from tests import mock_server
from tests.contract.conftest import assert_error_envelope

STATUSES = {
    "queued",
    "ocr",
    "extracting",
    "validating",
    "needs_review",
    "complete",
    "failed",
}
TERMINAL = {"complete", "needs_review", "failed"}
PDF = ("scan.pdf", b"%PDF-1.4 mock", "application/pdf")
CLASSIFIED = {"data_classification": "synthetic"}


def test_login_returns_token_and_user(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "reviewer@ptcl.internal", "password": mock_server.PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "expires_in", "user"}
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert body["expires_in"] == 3600
    assert set(body["user"]) == {"id", "name", "role"}
    assert body["user"]["role"] in {"viewer", "reviewer", "admin"}


def test_login_rejects_bad_credentials(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "reviewer@ptcl.internal", "password": "wrong"},
    )
    assert response.status_code == 401
    assert_error_envelope(response.json(), "UNAUTHORIZED", False)


def test_upload_returns_202_and_queued(client: TestClient, reviewer: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/documents", files={"file": PDF}, data=CLASSIFIED, headers=reviewer
    )
    assert response.status_code == 202
    body = response.json()
    assert set(body) == {
        "document_id",
        "filename",
        "status",
        "data_classification",
        "uploaded_at",
    }
    assert body["status"] == "queued"
    assert body["filename"] == "scan.pdf"
    assert body["data_classification"] == "synthetic"
    assert body["uploaded_at"].endswith("Z")


def test_upload_rejects_unsupported_type(client: TestClient, reviewer: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data=CLASSIFIED,
        headers=reviewer,
    )
    assert response.status_code == 415
    assert_error_envelope(response.json(), "UNSUPPORTED_TYPE", False)


@pytest.mark.parametrize("classification", ["public", "synthetic", "restricted"])
def test_upload_records_the_classification_it_was_given(
    client: TestClient, reviewer: dict[str, str], classification: str
) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": PDF},
        data={"data_classification": classification},
        headers=reviewer,
    )
    assert response.status_code == 202
    assert response.json()["data_classification"] == classification


def test_upload_without_a_classification_is_rejected(
    client: TestClient, reviewer: dict[str, str]
) -> None:
    response = client.post("/api/v1/documents", files={"file": PDF}, headers=reviewer)
    assert response.status_code == 422
    assert_error_envelope(response.json(), "INVALID_CLASSIFICATION", False)
    assert not [
        document_id
        for document_id, record in mock_server.DOCUMENTS.items()
        if record["uploaded_monotonic"] is not None
    ], "an unclassified upload was stored"


@pytest.mark.parametrize("classification", ["", "   ", "customer", "internal", "PUBLIC"])
def test_upload_with_an_unrecognised_classification_is_rejected(
    client: TestClient, reviewer: dict[str, str], classification: str
) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": PDF},
        data={"data_classification": classification},
        headers=reviewer,
    )
    assert response.status_code == 422
    assert_error_envelope(response.json(), "INVALID_CLASSIFICATION", False)


def test_classification_cannot_be_changed_by_a_correction(
    client: TestClient, reviewer: dict[str, str]
) -> None:
    before = mock_server.DOCUMENTS[mock_server.DOC_FAILED_GATE]["data_classification"]
    response = client.patch(
        f"/api/v1/documents/{mock_server.DOC_FAILED_GATE}/extraction",
        json={"corrections": [{"field": "data_classification", "value": "public"}]},
        headers=reviewer,
    )
    assert response.status_code == 422
    assert_error_envelope(response.json(), "IMMUTABLE_FIELD", False)
    assert mock_server.DOCUMENTS[mock_server.DOC_FAILED_GATE]["data_classification"] == before


def test_status_progresses_queued_to_complete(
    client: TestClient, reviewer: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mock_server, "PROGRESSION_SECONDS", 0.4)
    document_id = client.post(
        "/api/v1/documents", files={"file": PDF}, data=CLASSIFIED, headers=reviewer
    ).json()["document_id"]

    seen = []
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        body = client.get(f"/api/v1/documents/{document_id}/status", headers=reviewer).json()
        assert set(body) == {"document_id", "status", "progress", "stage_detail", "error"}
        assert body["status"] in STATUSES
        assert 0.0 <= body["progress"] <= 1.0
        if not seen or seen[-1] != body["status"]:
            seen.append(body["status"])
        if body["status"] in TERMINAL:
            break
        time.sleep(0.05)

    assert seen[0] == "queued"
    assert seen[-1] == "complete"
    assert "ocr" in seen or "extracting" in seen


def test_extraction_returns_409_before_terminal(
    client: TestClient, reviewer: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mock_server, "PROGRESSION_SECONDS", 30.0)
    document_id = client.post(
        "/api/v1/documents", files={"file": PDF}, data=CLASSIFIED, headers=reviewer
    ).json()["document_id"]

    response = client.get(f"/api/v1/documents/{document_id}/extraction", headers=reviewer)
    assert response.status_code == 409
    assert_error_envelope(response.json(), "NOT_READY", True)


def test_download_file_returns_the_raw_upload_with_its_content_type(
    client: TestClient, reviewer: dict[str, str]
) -> None:
    document_id = client.post(
        "/api/v1/documents", files={"file": PDF}, data=CLASSIFIED, headers=reviewer
    ).json()["document_id"]

    response = client.get(f"/api/v1/documents/{document_id}/file", headers=reviewer)
    assert response.status_code == 200
    assert response.content == PDF[1]
    assert response.headers["content-type"] == "application/pdf"


@pytest.mark.parametrize(
    "document_id",
    [
        mock_server.DOC_FAILED_GATE,
        mock_server.DOC_FORMAT_ONLY,
        mock_server.DOC_LOW_CONF_VERIFIED,
    ],
)
def test_download_file_for_a_seeded_fixture_returns_bytes(
    client: TestClient, reviewer: dict[str, str], document_id: str
) -> None:
    response = client.get(f"/api/v1/documents/{document_id}/file", headers=reviewer)
    assert response.status_code == 200
    assert response.content


def test_download_file_for_unknown_document_returns_404(
    client: TestClient, reviewer: dict[str, str]
) -> None:
    response = client.get(
        "/api/v1/documents/00000000-0000-0000-0000-000000000000/file", headers=reviewer
    )
    assert response.status_code == 404
    assert_error_envelope(response.json(), "NOT_FOUND", False)


@pytest.mark.parametrize(
    "document_id",
    [
        mock_server.DOC_FAILED_GATE,
        mock_server.DOC_FORMAT_ONLY,
        mock_server.DOC_LOW_CONF_VERIFIED,
    ],
)
def test_extraction_validates_against_schema(
    client: TestClient,
    reviewer: dict[str, str],
    validator: Draft202012Validator,
    document_id: str,
) -> None:
    response = client.get(f"/api/v1/documents/{document_id}/extraction", headers=reviewer)
    assert response.status_code == 200
    body = response.json()
    errors = sorted(validator.iter_errors(body), key=lambda e: list(e.absolute_path))
    assert not errors, "; ".join(f"{list(e.absolute_path)}: {e.message}" for e in errors)
    assert body["status"] in TERMINAL


def test_patch_returns_merged_result_and_validates(
    client: TestClient, reviewer: dict[str, str], validator: Draft202012Validator
) -> None:
    response = client.patch(
        f"/api/v1/documents/{mock_server.DOC_FAILED_GATE}/extraction",
        json={"corrections": [{"field": "total", "value": "29250.00"}]},
        headers=reviewer,
    )
    assert response.status_code == 200
    body = response.json()
    assert not list(validator.iter_errors(body))
    total = body["fields"]["total"]
    assert total["value"] == "29250.00"
    assert total["verified"] is True
    assert total["source"]["origin"] == "human"


def test_patch_forbidden_for_viewer(client: TestClient, viewer: dict[str, str]) -> None:
    response = client.patch(
        f"/api/v1/documents/{mock_server.DOC_FAILED_GATE}/extraction",
        json={"corrections": [{"field": "total", "value": "1.00"}]},
        headers=viewer,
    )
    assert response.status_code == 403
    assert_error_envelope(response.json(), "FORBIDDEN", False)


def test_create_export_returns_202(client: TestClient, reviewer: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/exports",
        json={"document_ids": [mock_server.DOC_FAILED_GATE], "format": "xlsx"},
        headers=reviewer,
    )
    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"export_id", "status"}
    assert body["status"] == "queued"


def test_get_export_returns_download_url(client: TestClient, reviewer: dict[str, str]) -> None:
    export_id = client.post(
        "/api/v1/exports",
        json={"document_ids": [mock_server.DOC_FAILED_GATE], "format": "xlsx"},
        headers=reviewer,
    ).json()["export_id"]

    response = client.get(f"/api/v1/exports/{export_id}", headers=reviewer)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "download_url", "expires_at"}
    assert body["download_url"] == f"/api/v1/exports/{export_id}/file"


def _wait_for_export_complete(
    client: TestClient, headers: dict[str, str], export_id: str, timeout: float = 5.0
) -> str:
    """Poll until the export leaves 'queued', or fail loudly rather than hang or race it."""
    deadline = time.monotonic() + timeout
    status = "queued"
    while time.monotonic() < deadline:
        status = client.get(f"/api/v1/exports/{export_id}", headers=headers).json()["status"]
        if status in ("complete", "failed"):
            return status
        time.sleep(0.05)
    pytest.fail(
        f"export {export_id} did not leave 'queued' within {timeout}s (last seen: {status})"
    )


def test_download_export_returns_binary(client: TestClient, reviewer: dict[str, str]) -> None:
    export_id = client.post(
        "/api/v1/exports",
        json={"document_ids": [mock_server.DOC_FAILED_GATE], "format": "xlsx"},
        headers=reviewer,
    ).json()["export_id"]

    status = _wait_for_export_complete(client, reviewer, export_id)
    assert status == "complete"

    response = client.get(f"/api/v1/exports/{export_id}/file", headers=reviewer)
    assert response.status_code == 200
    assert response.content
    assert "spreadsheetml" in response.headers["content-type"]


def test_list_documents_shape_and_paging(client: TestClient, reviewer: dict[str, str]) -> None:
    response = client.get("/api/v1/documents?page=1&page_size=2", headers=reviewer)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "page", "page_size", "total"}
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) <= 2
    for row in body["items"]:
        assert set(row) == {
            "document_id",
            "filename",
            "status",
            "document_type",
            "uploaded_at",
            "needs_review_count",
        }
        assert row["status"] in STATUSES


def test_list_documents_filters_by_status(client: TestClient, reviewer: dict[str, str]) -> None:
    response = client.get("/api/v1/documents?status=needs_review", headers=reviewer)
    assert response.status_code == 200
    assert all(row["status"] == "needs_review" for row in response.json()["items"])


def test_every_endpoint_requires_a_bearer_token(client: TestClient) -> None:
    calls: list[tuple[str, str, dict[str, Any]]] = [
        ("get", "/api/v1/documents", {}),
        ("get", f"/api/v1/documents/{mock_server.DOC_FAILED_GATE}/status", {}),
        ("get", f"/api/v1/documents/{mock_server.DOC_FAILED_GATE}/extraction", {}),
        ("get", f"/api/v1/documents/{mock_server.DOC_FAILED_GATE}/file", {}),
        (
            "patch",
            f"/api/v1/documents/{mock_server.DOC_FAILED_GATE}/extraction",
            {"json": {"corrections": []}},
        ),
        ("post", "/api/v1/exports", {"json": {"document_ids": [], "format": "xlsx"}}),
    ]
    for method, url, kwargs in calls:
        response = getattr(client, method)(url, **kwargs)
        assert response.status_code == 401, f"{method.upper()} {url}"
        assert_error_envelope(response.json(), "UNAUTHORIZED", False)


def test_fixtures_cover_the_three_review_states(
    client: TestClient, reviewer: dict[str, str]
) -> None:
    results: dict[str, set[str]] = {}
    for document_id in (
        mock_server.DOC_FAILED_GATE,
        mock_server.DOC_FORMAT_ONLY,
        mock_server.DOC_LOW_CONF_VERIFIED,
    ):
        body = client.get(f"/api/v1/documents/{document_id}/extraction", headers=reviewer).json()
        results[document_id] = {gate["result"] for gate in body["gates"]}

    assert "failed" in results[mock_server.DOC_FAILED_GATE]
    assert "format_only" in results[mock_server.DOC_FORMAT_ONLY]

    low_conf = client.get(
        f"/api/v1/documents/{mock_server.DOC_LOW_CONF_VERIFIED}/extraction", headers=reviewer
    ).json()
    iban = low_conf["fields"]["iban"]
    assert iban["verified"] is True
    assert iban["confidence"] < 0.5


def test_format_only_never_implies_verified(client: TestClient, reviewer: dict[str, str]) -> None:
    body = client.get(
        f"/api/v1/documents/{mock_server.DOC_FORMAT_ONLY}/extraction", headers=reviewer
    ).json()

    format_only_fields: set[str] = set()
    for gate in body["gates"]:
        if gate["result"] == "format_only":
            format_only_fields.update(gate.get("affected_fields", []))

    assert format_only_fields
    for name in format_only_fields:
        field = body["fields"].get(name)
        if field is not None:
            assert field["verified"] is False, f"{name} is format_only but marked verified"


def test_schema_validation_actually_rejects_violations(
    client: TestClient, reviewer: dict[str, str], validator: Draft202012Validator
) -> None:
    body = client.get(
        f"/api/v1/documents/{mock_server.DOC_LOW_CONF_VERIFIED}/extraction", headers=reviewer
    ).json()
    assert not list(validator.iter_errors(body))

    reverted = {**body, "gates": [{"name": "iban_checksum", "passed": True}]}
    assert list(validator.iter_errors(reverted)), "validator accepted the removed boolean form"

    bad_state = {**body, "gates": [{"name": "iban_checksum", "result": "ok"}]}
    assert list(validator.iter_errors(bad_state)), "validator accepted an invalid gate result"

    bad_money = {
        **body,
        "fields": {**body["fields"], "total": {**body["fields"]["total"], "value": "11700"}},
    }
    assert list(validator.iter_errors(bad_money)), "validator accepted a non-2dp money value"

    no_source = {
        **body,
        "fields": {
            **body["fields"],
            "total": {k: v for k, v in body["fields"]["total"].items() if k != "source"},
        },
    }
    assert list(validator.iter_errors(no_source)), "validator accepted a field with no provenance"


@pytest.mark.parametrize(
    "document_id",
    [
        mock_server.DOC_FAILED_GATE,
        mock_server.DOC_FORMAT_ONLY,
        mock_server.DOC_LOW_CONF_VERIFIED,
    ],
)
def test_pipeline_version_stamps_the_profile(
    client: TestClient, reviewer: dict[str, str], document_id: str
) -> None:
    body = client.get(f"/api/v1/documents/{document_id}/extraction", headers=reviewer).json()
    pipeline_version = body["pipeline_version"]
    assert pipeline_version["profile"] in {"prototype", "production"}
    assert pipeline_version["schema_version"] == "0.3.0"


def test_pipeline_version_without_a_profile_is_rejected(
    client: TestClient, reviewer: dict[str, str], validator: Draft202012Validator
) -> None:
    body = client.get(
        f"/api/v1/documents/{mock_server.DOC_LOW_CONF_VERIFIED}/extraction", headers=reviewer
    ).json()
    assert not list(validator.iter_errors(body))

    unprofiled = {
        **body,
        "pipeline_version": {k: v for k, v in body["pipeline_version"].items() if k != "profile"},
    }
    assert list(validator.iter_errors(unprofiled)), "validator accepted an unprofiled extraction"

    bad_profile = {
        **body,
        "pipeline_version": {**body["pipeline_version"], "profile": "staging"},
    }
    assert list(validator.iter_errors(bad_profile)), "validator accepted an unknown profile"

    stale_schema = {
        **body,
        "pipeline_version": {**body["pipeline_version"], "schema_version": "0.2.0"},
    }
    assert list(validator.iter_errors(stale_schema)), "validator accepted schema_version 0.2.0"


def test_two_profiles_of_the_same_document_do_not_compare_as_equivalent(
    client: TestClient, reviewer: dict[str, str]
) -> None:
    body = client.get(
        f"/api/v1/documents/{mock_server.DOC_LOW_CONF_VERIFIED}/extraction", headers=reviewer
    ).json()
    hosted_run = body["pipeline_version"]
    local_run = {**hosted_run, "profile": "production"}

    pre_0_3_0 = {k: v for k, v in hosted_run.items() if k != "profile"}
    assert pre_0_3_0 == {k: v for k, v in local_run.items() if k != "profile"}, (
        "this test no longer isolates profile as the only difference"
    )
    assert hosted_run != local_run, (
        "the same document under two profiles produced an identical pipeline_version"
    )


def test_no_gate_uses_the_removed_passed_boolean(
    client: TestClient, reviewer: dict[str, str]
) -> None:
    for document_id in (
        mock_server.DOC_FAILED_GATE,
        mock_server.DOC_FORMAT_ONLY,
        mock_server.DOC_LOW_CONF_VERIFIED,
    ):
        body = client.get(f"/api/v1/documents/{document_id}/extraction", headers=reviewer).json()
        for gate in body["gates"]:
            assert "passed" not in gate, "gates[].passed was removed in EXTRACTION_SCHEMA 0.2.0"
            assert gate["result"] in {"passed", "failed", "format_only"}
