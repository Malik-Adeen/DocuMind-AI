from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.storage import store_upload
from app.db.models import AuditLog, Correction, Document, Extraction
from app.db.queries import current_extraction, unverified_field_counts
from app.schemas.extraction import field_names, terminal_statuses
from app.workers.tasks import extract_document

ACCEPTED_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg", "image/tiff"})
CLASSIFICATIONS = frozenset({"public", "synthetic", "restricted"})
IMMUTABLE_FIELDS = frozenset({"data_classification"})

PROGRESS = {
    "queued": (0.05, "queued"),
    "ocr": (0.3, "latin_ocr"),
    "extracting": (0.7, "llm_extraction"),
    "validating": (0.9, "gates"),
    "needs_review": (1.0, None),
    "complete": (1.0, None),
    "failed": (1.0, None),
}


def record_audit(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: str | None,
    trace_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            trace_id=trace_id,
            detail=detail,
        )
    )


def create_document(
    db: Session,
    *,
    content: bytes,
    filename: str,
    content_type: str | None,
    data_classification: str,
    actor_id: uuid.UUID,
    settings: Settings,
    trace_id: uuid.UUID | None = None,
) -> Document:
    if len(content) > settings.max_upload_bytes:
        raise ApiError("FILE_TOO_LARGE", "File exceeds 25 MB.")
    if content_type not in ACCEPTED_TYPES:
        raise ApiError("UNSUPPORTED_TYPE", f"Unsupported type {content_type}.")
    if data_classification not in CLASSIFICATIONS:
        allowed = ", ".join(sorted(CLASSIFICATIONS))
        raise ApiError(
            "INVALID_CLASSIFICATION",
            f"data_classification is required and must be one of {allowed}.",
        )

    stored = store_upload(content, filename=filename, upload_dir=Path(settings.upload_dir))
    document = Document(
        id=uuid.uuid4(),
        filename=filename,
        storage_path=stored.path,
        content_type=content_type,
        byte_size=stored.byte_size,
        sha256=stored.sha256,
        data_classification=data_classification,
        status="queued",
        document_type="unknown",
        uploaded_by=actor_id,
    )
    db.add(document)
    record_audit(
        db,
        actor_id=actor_id,
        action="document.upload",
        entity="document",
        entity_id=str(document.id),
        trace_id=trace_id,
        detail={"data_classification": data_classification, "sha256": stored.sha256},
    )
    db.commit()
    enqueue_extraction(document)
    return document


_extraction_threads: list[threading.Thread] = []


def _run_extraction_soon(document_id: str) -> None:
    time.sleep(0.05)
    extract_document.delay(document_id)


def enqueue_extraction(document: Document) -> None:
    document_id = str(document.id)
    if get_settings().celery_task_always_eager:
        thread = threading.Thread(target=_run_extraction_soon, args=(document_id,), daemon=True)
        _extraction_threads.append(thread)
        thread.start()
    else:
        extract_document.delay(document_id)


def join_extraction_threads(timeout: float = 5.0) -> None:
    while _extraction_threads:
        _extraction_threads.pop().join(timeout)


def get_document(db: Session, document_id: str) -> Document:
    try:
        parsed = uuid.UUID(document_id)
    except ValueError:
        raise ApiError("NOT_FOUND", "No such document.") from None
    document = db.get(Document, parsed)
    if document is None:
        raise ApiError("NOT_FOUND", "No such document.")
    return document


def status_payload(document: Document) -> dict[str, Any]:
    progress, stage_detail = PROGRESS[document.status]
    return {
        "document_id": str(document.id),
        "status": document.status,
        "progress": progress,
        "stage_detail": stage_detail,
        "error": document.error,
    }


def extraction_payload(db: Session, document: Document) -> dict[str, Any]:
    if document.status not in terminal_statuses():
        raise ApiError("NOT_READY", f"Document is {document.status}.")
    view = current_extraction(db, document.id)
    if view is None:
        raise ApiError("NOT_READY", "No extraction for this document yet.")
    return view


def latest_extraction(db: Session, document_id: uuid.UUID) -> Extraction:
    extraction = db.scalars(
        select(Extraction)
        .where(Extraction.document_id == document_id)
        .order_by(Extraction.seq.desc())
        .limit(1)
    ).first()
    if extraction is None:
        raise ApiError("NOT_FOUND", "No such document.")
    return extraction


def apply_corrections(
    db: Session,
    *,
    document: Document,
    corrections: list[dict[str, Any]],
    actor_id: uuid.UUID,
    trace_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    named = [entry.get("field") for entry in corrections if isinstance(entry, dict)]
    immutable = sorted({name for name in named if name in IMMUTABLE_FIELDS})
    if immutable:
        raise ApiError(
            "IMMUTABLE_FIELD",
            f"{', '.join(immutable)} is set at upload and cannot be corrected. "
            "Reclassification is a new upload, not an edit.",
        )

    unknown = sorted({str(name) for name in named if name not in field_names()})
    if unknown:
        raise ApiError(
            "EXTRACTION_FAILED",
            f"{', '.join(unknown)} is not a field in EXTRACTION_SCHEMA.json.",
        )

    extraction = latest_extraction(db, document.id)
    for entry in corrections:
        db.add(
            Correction(
                id=uuid.uuid4(),
                extraction_id=extraction.id,
                field=entry["field"],
                value=entry.get("value"),
                corrected_by=actor_id,
            )
        )
    record_audit(
        db,
        actor_id=actor_id,
        action="extraction.correct",
        entity="extraction",
        entity_id=str(extraction.id),
        trace_id=trace_id,
        detail={"fields": [entry["field"] for entry in corrections]},
    )
    db.commit()

    view = current_extraction(db, document.id)
    if view is None:
        raise ApiError("NOT_READY", "No extraction for this document yet.")
    return view


def list_documents(
    db: Session,
    *,
    status: str | None,
    page: int,
    page_size: int,
    q: str | None,
    date_from: str | None,
    date_to: str | None,
) -> dict[str, Any]:
    query = select(Document)
    if status:
        query = query.where(Document.status == status)
    if q:
        query = query.where(Document.filename.ilike(f"%{q}%"))
    if date_from:
        query = query.where(Document.uploaded_at >= date_from)
    if date_to:
        query = query.where(Document.uploaded_at <= date_to)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        db.scalars(
            query.order_by(Document.uploaded_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    counts = unverified_field_counts(db, [row.id for row in rows])

    return {
        "items": [
            {
                "document_id": str(row.id),
                "filename": row.filename,
                "status": row.status,
                "document_type": row.document_type,
                "uploaded_at": _iso(row.uploaded_at),
                "needs_review_count": counts.get(row.id, 0),
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def _iso(value: Any) -> str:
    return str(value.strftime("%Y-%m-%dT%H:%M:%SZ"))
