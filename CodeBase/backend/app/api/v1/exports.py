from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db
from app.db.models import User
from app.export.xlsx import MEDIA_TYPE
from app.services.exports import artifact_bytes, create_export, export_payload, get_export

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


@router.post("")
def create(
    request: Request,
    payload: dict[str, Any],
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    trace = getattr(request.state, "trace_id", None)
    export = create_export(
        db,
        document_ids=[str(value) for value in payload.get("document_ids", [])],
        export_format=str(payload.get("format", "xlsx")),
        actor_id=user.id,
        trace_id=uuid.UUID(str(trace)) if trace else None,
    )
    return JSONResponse(
        status_code=202,
        content={"export_id": str(export.id), "status": export.status},
    )


@router.get("/{export_id}")
def read(
    export_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(status_code=200, content=export_payload(get_export(db, export_id)))


@router.get("/{export_id}/file")
def download(
    export_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    export = get_export(db, export_id)
    return Response(
        content=artifact_bytes(export),
        media_type=MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="export-{export.id}.xlsx"'},
    )
