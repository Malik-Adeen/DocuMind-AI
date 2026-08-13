from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.models import Document, Extraction
from app.services.exports import create_export
from tests.integration.conftest import PIPELINE_VERSION, extraction_result

pytestmark = pytest.mark.integration


def test_export_refuses_a_document_with_no_extraction(
    session: Session, reviewer_id: uuid.UUID
) -> None:
    failed = Document(
        id=uuid.uuid4(),
        filename="invoice-9931.pdf",
        storage_path="var/uploads/bb/invoice-9931.pdf",
        content_type="application/pdf",
        byte_size=2048,
        sha256="b" * 64,
        data_classification="synthetic",
        status="failed",
        document_type="unknown",
    )
    session.add(failed)
    session.commit()

    with pytest.raises(ApiError) as excinfo:
        create_export(
            session,
            document_ids=[str(failed.id)],
            export_format="xlsx",
            actor_id=reviewer_id,
        )

    assert excinfo.value.code == "DOCUMENTS_NOT_EXPORTABLE"
    assert "invoice-9931.pdf" in excinfo.value.message
    assert "failed" in excinfo.value.message


def test_export_succeeds_when_every_document_has_an_extraction(
    session: Session, document_id: uuid.UUID, reviewer_id: uuid.UUID
) -> None:
    session.add(
        Extraction(
            id=uuid.uuid4(),
            document_id=document_id,
            pipeline_version=PIPELINE_VERSION,
            result=extraction_result(document_id),
            status="needs_review",
        )
    )
    session.commit()

    export = create_export(
        session,
        document_ids=[str(document_id)],
        export_format="xlsx",
        actor_id=reviewer_id,
    )

    assert export.status == "queued"
