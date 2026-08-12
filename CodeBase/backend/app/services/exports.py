from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.models import Export
from app.services.documents import record_audit
from app.workers.tasks import generate_export

FORMATS = frozenset({"xlsx"})


def create_export(
    db: Session,
    *,
    document_ids: list[str],
    export_format: str,
    actor_id: uuid.UUID,
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

    enqueue_export(export)
    return export


_export_threads: list[threading.Thread] = []


def _run_export_soon(export_id: str) -> None:
    time.sleep(0.05)
    generate_export.delay(export_id)


def enqueue_export(export: Export) -> None:
    export_id = str(export.id)
    if get_settings().celery_task_always_eager:
        thread = threading.Thread(target=_run_export_soon, args=(export_id,), daemon=True)
        _export_threads.append(thread)
        thread.start()
    else:
        generate_export.delay(export_id)


def join_export_threads(timeout: float = 5.0) -> None:
    while _export_threads:
        _export_threads.pop().join(timeout)


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
