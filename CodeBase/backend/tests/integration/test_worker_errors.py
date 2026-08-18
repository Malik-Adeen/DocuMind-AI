from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.orm import Session

from app.db.models import Document
from app.pipeline.llm.client import DeploymentProfile, Endpoint, LLMClient
from app.pipeline.llm.transport import TruncatedResponseError
from app.pipeline.ocr.paddle import TextRegion
from app.workers import tasks as worker_tasks

pytestmark = pytest.mark.integration

SECRET = "leaked-ocr-text-should-never-reach-the-api"


class _FakeOCR:
    def read(self, image_path: str, *, page: int = 1) -> list[TextRegion]:
        return [
            TextRegion(
                text="Invoice total 100.00", confidence=0.9, bbox=(0.0, 0.0, 1.0, 1.0), page=1
            )
        ]


class _RaisingOCR:
    def read(self, image_path: str, *, page: int = 1) -> list[TextRegion]:
        raise RuntimeError(SECRET)


class _UnreachableTransport:
    def __call__(self, prompt: str) -> str:
        raise AssertionError("hosted transport was called despite INV-6 refusing the document")


class _TruncatingTransport:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    def __call__(self, prompt: str) -> str:
        self.calls += 1
        raise TruncatedResponseError(self.content)


def _hosted_client(transport: object) -> LLMClient:
    return LLMClient(
        profile=DeploymentProfile.PROTOTYPE,
        endpoint=Endpoint.HOSTED,
        model="fake-hosted-model",
        transport=transport,  # type: ignore[arg-type]
    )


def _queued_document(session: Session, *, data_classification: str) -> Document:
    document = Document(
        id=uuid.uuid4(),
        filename="invoice.pdf",
        storage_path="var/uploads/aa/invoice.pdf",
        content_type="application/pdf",
        byte_size=1024,
        sha256="c" * 64,
        data_classification=data_classification,
        status="queued",
        document_type="unknown",
    )
    session.add(document)
    session.commit()
    return document


def test_hosted_endpoint_refusal_populates_a_safe_error(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _queued_document(session, data_classification="restricted")
    monkeypatch.setattr(worker_tasks, "build_ocr_reader", lambda: _FakeOCR())
    monkeypatch.setattr(
        worker_tasks, "build_llm_client", lambda: _hosted_client(_UnreachableTransport())
    )

    worker_tasks.extract_document(str(document.id))

    session.refresh(document)
    assert document.status == "failed"
    assert document.error is not None
    assert document.error["code"] == "HOSTED_ENDPOINT_REFUSED"
    assert document.error["retryable"] is False
    assert "INV-6" in document.error["message"]
    assert str(document.id) in document.error["message"]
    uuid.UUID(document.error["trace_id"])


def test_unclassified_failure_produces_a_generic_error_without_leaking_content(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _queued_document(session, data_classification="synthetic")
    monkeypatch.setattr(worker_tasks, "build_ocr_reader", lambda: _RaisingOCR())
    monkeypatch.setattr(
        worker_tasks, "build_llm_client", lambda: _hosted_client(_UnreachableTransport())
    )

    with pytest.raises(RuntimeError, match=SECRET):
        worker_tasks.extract_document(str(document.id))

    session.refresh(document)
    assert document.status == "failed"
    assert document.error is not None
    assert document.error["code"] == "INTERNAL"
    assert document.error["retryable"] is True
    assert SECRET not in json.dumps(document.error)
    uuid.UUID(document.error["trace_id"])


def test_a_successful_extraction_leaves_error_null(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _queued_document(session, data_classification="synthetic")
    monkeypatch.setattr(worker_tasks, "build_ocr_reader", lambda: _FakeOCR())
    monkeypatch.setattr(
        worker_tasks,
        "build_llm_client",
        lambda: _hosted_client(
            lambda prompt: (
                '{"fields": {}, "document_type": {"value": "invoice", "confidence": 0.5}}'
            )
        ),
    )

    worker_tasks.extract_document(str(document.id))

    session.refresh(document)
    assert document.status in {"complete", "needs_review"}
    assert document.error is None


def test_a_truncated_response_with_recoverable_fields_routes_to_needs_review_not_failed(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _queued_document(session, data_classification="synthetic")
    monkeypatch.setattr(worker_tasks, "build_ocr_reader", lambda: _FakeOCR())
    truncated_body = (
        '{"document_type": {"value": "invoice", "confidence": 0.95}, "fields": {'
        '"po_number": {"value": "PO-2291", "confidence": 0.9, "verified": false, '
        '"source": {"origin": "llm_inferred", "raw_text": "PO-2291"}}, '
        '"notes": {"value": "terms and conditions that go on for a while and then just sto'
    )
    transport = _TruncatingTransport(truncated_body)
    monkeypatch.setattr(worker_tasks, "build_llm_client", lambda: _hosted_client(transport))

    worker_tasks.extract_document(str(document.id))

    session.refresh(document)
    assert document.status == "needs_review"
    assert transport.calls == 1, "a truncated response must not enter the repair-prompt retry loop"
    assert document.error is not None
    assert document.error["code"] == "LLM_OUTPUT_TRUNCATED"
    assert document.error["retryable"] is True
    uuid.UUID(document.error["trace_id"])


def test_a_truncated_response_with_nothing_recoverable_fails_the_document(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _queued_document(session, data_classification="synthetic")
    monkeypatch.setattr(worker_tasks, "build_ocr_reader", lambda: _FakeOCR())
    transport = _TruncatingTransport('{"document_type": {"value": "in')
    monkeypatch.setattr(worker_tasks, "build_llm_client", lambda: _hosted_client(transport))

    worker_tasks.extract_document(str(document.id))

    session.refresh(document)
    assert document.status == "failed"
    assert transport.calls == 1
