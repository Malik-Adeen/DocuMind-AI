from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.db.models import Export
from app.export.xlsx import write_workbook
from app.services.documents import record_audit

FORMATS = frozenset({"xlsx", "csv", "json"})
TTL_HOURS = 24


def create_export(
    db: Session,
    *,
    document_ids: list[str],
    export_format: str,
    actor_id: uuid.UUID,
    settings: Settings,
    trace_id: uuid.UUID | None = None,
) -> Export:
    if export_format not in FORMATS:
        raise ApiError("UNSUPPORTED_TYPE", f"Unsupported export format {export_format}.")

    export = Export(
        id=uuid.uuid4(),
        format=export_format,
        document_ids=list(document_ids),
        status="queued",
        requested_by=actor_id,
    )
    db.add(export)
    record_audit(
        db,
        actor_id=actor_id,
        action="export.create",
        entity="export",
        entity_id=str(export.id),
        trace_id=trace_id,
        detail={"format": export_format, "documents": len(document_ids)},
    )
    db.commit()

    _render(db, export, settings)
    return export


def _render(db: Session, export: Export, settings: Settings) -> None:
    """Stub for the Celery export worker: renders inline, then marks the job complete."""
    parsed = []
    for raw in export.document_ids:
        try:
            parsed.append(uuid.UUID(str(raw)))
        except ValueError:
            continue

    target = Path(settings.export_dir) / f"export-{export.id}.xlsx"
    write_workbook(db, document_ids=parsed, target=target)

    export.artifact_path = str(target)
    export.status = "complete"
    export.expires_at = datetime.now(UTC) + timedelta(hours=TTL_HOURS)
    db.commit()


def get_export(db: Session, export_id: str) -> Export:
    try:
        parsed = uuid.UUID(export_id)
    except ValueError:
        raise ApiError("NOT_FOUND", "No such export.") from None
    export = db.get(Export, parsed)
    if export is None:
        raise ApiError("NOT_FOUND", "No such export.")
    return export


def export_payload(export: Export) -> dict[str, Any]:
    return {
        "status": export.status,
        "download_url": f"/api/v1/exports/{export.id}/file",
        "expires_at": export.expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        if export.expires_at
        else None,
    }


def artifact_bytes(export: Export) -> bytes:
    if not export.artifact_path or not Path(export.artifact_path).exists():
        raise ApiError("NOT_READY", "Export artifact is not ready.")
    return Path(export.artifact_path).read_bytes()
