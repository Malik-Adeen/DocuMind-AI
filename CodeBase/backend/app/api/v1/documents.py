from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db, require_reviewer
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.db.models import User
from app.services.documents import (
    apply_corrections,
    create_document,
    extraction_payload,
    get_document,
    list_documents,
    status_payload,
)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _trace_id(request: Request) -> uuid.UUID | None:
    value = getattr(request.state, "trace_id", None)
    return uuid.UUID(str(value)) if value else None


@router.post("")
async def upload(
    request: Request,
    file: UploadFile,
    data_classification: str = Form(default=""),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    document = create_document(
        db,
        content=await file.read(),
        filename=file.filename or "upload.pdf",
        content_type=file.content_type,
        data_classification=data_classification,
        actor_id=user.id,
        settings=settings,
        trace_id=_trace_id(request),
    )
    return JSONResponse(
        status_code=202,
        content={
            "document_id": str(document.id),
            "filename": document.filename,
            "status": document.status,
            "data_classification": document.data_classification,
            "uploaded_at": document.uploaded_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )


@router.get("")
def index(
    status: str | None = None,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=list_documents(
            db,
            status=status,
            page=page,
            page_size=page_size,
            q=q,
            date_from=from_,
            date_to=to,
        ),
    )


@router.get("/{document_id}/status")
def document_status(
    document_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(status_code=200, content=status_payload(get_document(db, document_id)))


@router.get("/{document_id}/extraction")
def get_extraction(
    document_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    document = get_document(db, document_id)
    return JSONResponse(status_code=200, content=extraction_payload(db, document))


@router.patch("/{document_id}/extraction")
def correct_extraction(
    request: Request,
    document_id: str,
    payload: dict[str, Any],
    user: User = require_reviewer,
    db: Session = Depends(get_db),
) -> JSONResponse:
    corrections = payload.get("corrections")
    if not isinstance(corrections, list):
        raise ApiError("EXTRACTION_FAILED", "corrections must be a list.")

    document = get_document(db, document_id)
    merged = apply_corrections(
        db,
        document=document,
        corrections=corrections,
        actor_id=user.id,
        trace_id=_trace_id(request),
    )
    return JSONResponse(status_code=200, content=merged)
