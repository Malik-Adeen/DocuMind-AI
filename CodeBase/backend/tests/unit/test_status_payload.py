from __future__ import annotations

import uuid

from app.db.models import Document
from app.services.documents import status_payload


def _document(*, status: str, error: dict[str, object] | None) -> Document:
    return Document(
        id=uuid.uuid4(),
        filename="invoice.pdf",
        storage_path="var/uploads/aa/invoice.pdf",
        content_type="application/pdf",
        byte_size=1024,
        sha256="d" * 64,
        data_classification="synthetic",
        status=status,
        document_type="unknown",
        error=error,
    )


def test_status_payload_reports_null_error_when_none_is_recorded() -> None:
    payload = status_payload(_document(status="extracting", error=None))
    assert payload["error"] is None


def test_status_payload_passes_through_a_recorded_error_verbatim() -> None:
    error = {
        "code": "HOSTED_ENDPOINT_REFUSED",
        "message": "INV-6: refusing to send document doc-1 to a hosted LLM endpoint.",
        "trace_id": str(uuid.uuid4()),
        "retryable": False,
    }
    payload = status_payload(_document(status="failed", error=error))
    assert payload["error"] == error
