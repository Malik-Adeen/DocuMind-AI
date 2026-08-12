from __future__ import annotations

import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, Form, Header, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from app.db.fixtures import DOC_FAILED_GATE as DOC_FAILED_GATE
from app.db.fixtures import DOC_FORMAT_ONLY as DOC_FORMAT_ONLY
from app.db.fixtures import DOC_LOW_CONF_VERIFIED as DOC_LOW_CONF_VERIFIED
from app.db.fixtures import DOCUMENTS as FIXTURE_DOCUMENTS
from app.db.fixtures import EXTRACTIONS as FIXTURE_EXTRACTIONS
from app.db.fixtures import field
from app.db.seed import PLACEHOLDER

EXTRACTIONS: dict[str, dict[str, Any]] = {k: dict(v) for k, v in FIXTURE_EXTRACTIONS.items()}
DOCUMENTS: dict[str, dict[str, Any]] = {k: dict(v) for k, v in FIXTURE_DOCUMENTS.items()}

PROGRESSION_SECONDS = float(os.environ.get("MOCK_STATUS_PROGRESSION_SECONDS", "10"))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))

ACCEPTED_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
}

CLASSIFICATIONS = {"public", "synthetic", "restricted"}
IMMUTABLE_FIELDS = {"data_classification"}

USERS = {
    "viewer@ptcl.internal": ("viewer", "Viewer User"),
    "reviewer@ptcl.internal": ("reviewer", "Reviewer User"),
    "admin@ptcl.internal": ("admin", "Admin User"),
}
PASSWORD = "mock-password"
ROLE_RANK = {"viewer": 0, "reviewer": 1, "admin": 2}

CORRECTIONS: dict[str, list[dict[str, str]]] = {}
EXPORTS: dict[str, dict[str, Any]] = {}

TERMINAL = {"complete", "needs_review", "failed"}

app = FastAPI(title="DocuMind mock", version="0.3.0")


def error(status: int, code: str, message: str, retryable: bool) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "trace_id": str(uuid.uuid4()),
                "retryable": retryable,
            }
        },
    )


def role_of(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if not token.startswith("mock-token-"):
        return None
    role = token.removeprefix("mock-token-")
    return role if role in ROLE_RANK else None


def progression(document_id: str) -> tuple[str, float, str | None]:
    record = DOCUMENTS[document_id]
    started = record["uploaded_monotonic"]
    if started is None:
        return str(record["status"]), 1.0, None

    elapsed = time.monotonic() - float(started)
    fraction = elapsed / PROGRESSION_SECONDS

    if fraction < 0.25:
        return "queued", 0.05, "queued"
    if fraction < 0.5:
        return "ocr", 0.3, "latin_ocr"
    if fraction < 1.0:
        return "extracting", 0.7, "llm_extraction"
    return "complete", 1.0, None


@app.post("/api/v1/auth/login")
async def login(payload: dict[str, Any]) -> Response:
    email = payload.get("email")
    password = payload.get("password")
    if not isinstance(email, str) or email not in USERS or password != PASSWORD:
        return error(401, "UNAUTHORIZED", "Invalid credentials.", False)
    role, name = USERS[email]
    return JSONResponse(
        status_code=200,
        content={
            "access_token": f"mock-token-{role}",
            "expires_in": 3600,
            "user": {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, email)), "name": name, "role": role},
        },
    )


@app.post("/api/v1/documents")
async def upload(
    request: Request,
    file: UploadFile,
    data_classification: str = Form(default=""),
    authorization: str | None = Header(default=None),
) -> Response:
    if role_of(authorization) is None:
        return error(401, "UNAUTHORIZED", "Missing or invalid bearer token.", False)

    body = await file.read()
    if len(body) > MAX_UPLOAD_BYTES:
        return error(413, "FILE_TOO_LARGE", "File exceeds 25 MB.", False)
    if file.content_type not in ACCEPTED_TYPES:
        return error(415, "UNSUPPORTED_TYPE", f"Unsupported type {file.content_type}.", False)
    if data_classification not in CLASSIFICATIONS:
        allowed = ", ".join(sorted(CLASSIFICATIONS))
        return error(
            422,
            "INVALID_CLASSIFICATION",
            f"data_classification is required and must be one of {allowed}.",
            False,
        )

    document_id = str(uuid.uuid4())
    uploaded_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    DOCUMENTS[document_id] = {
        "filename": file.filename or "upload.pdf",
        "status": "queued",
        "document_type": "unknown",
        "data_classification": data_classification,
        "uploaded_at": uploaded_at,
        "needs_review_count": 0,
        "uploaded_monotonic": time.monotonic(),
        "content_type": file.content_type,
        "content": body,
    }
    return JSONResponse(
        status_code=202,
        content={
            "document_id": document_id,
            "filename": DOCUMENTS[document_id]["filename"],
            "status": "queued",
            "data_classification": data_classification,
            "uploaded_at": uploaded_at,
        },
    )


@app.get("/api/v1/documents")
async def list_documents(
    status: str | None = None,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
    authorization: str | None = Header(default=None),
) -> Response:
    if role_of(authorization) is None:
        return error(401, "UNAUTHORIZED", "Missing or invalid bearer token.", False)

    rows = []
    for document_id, record in DOCUMENTS.items():
        current, _, _ = progression(document_id)
        if status and current != status:
            continue
        if q and q.lower() not in str(record["filename"]).lower():
            continue
        rows.append(
            {
                "document_id": document_id,
                "filename": record["filename"],
                "status": current,
                "document_type": record["document_type"],
                "uploaded_at": record["uploaded_at"],
                "needs_review_count": record["needs_review_count"],
            }
        )

    start = (page - 1) * page_size
    return JSONResponse(
        status_code=200,
        content={
            "items": rows[start : start + page_size],
            "page": page,
            "page_size": page_size,
            "total": len(rows),
        },
    )


@app.get("/api/v1/documents/{document_id}/status")
async def document_status(
    document_id: str,
    authorization: str | None = Header(default=None),
) -> Response:
    if role_of(authorization) is None:
        return error(401, "UNAUTHORIZED", "Missing or invalid bearer token.", False)
    if document_id not in DOCUMENTS:
        return error(404, "NOT_FOUND", "No such document.", False)

    current, progress, stage_detail = progression(document_id)
    return JSONResponse(
        status_code=200,
        content={
            "document_id": document_id,
            "status": current,
            "progress": progress,
            "stage_detail": stage_detail,
            "error": None,
        },
    )


KNOWN_FIXTURE_IDS = {DOC_FAILED_GATE, DOC_FORMAT_ONLY, DOC_LOW_CONF_VERIFIED}


@app.get("/api/v1/documents/{document_id}/file")
async def download_file(
    document_id: str,
    authorization: str | None = Header(default=None),
) -> Response:
    if role_of(authorization) is None:
        return error(401, "UNAUTHORIZED", "Missing or invalid bearer token.", False)
    if document_id not in DOCUMENTS:
        return error(404, "NOT_FOUND", "No such document.", False)

    record = DOCUMENTS[document_id]
    content = record.get("content")
    content_type = record.get("content_type")
    if content is None:
        if document_id not in KNOWN_FIXTURE_IDS:
            return error(404, "NOT_FOUND", "No file stored for this document.", False)
        content = PLACEHOLDER + document_id.encode()
        content_type = "application/pdf"

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{record["filename"]}"'},
    )


def _merged(document_id: str) -> dict[str, Any]:
    extraction = {**EXTRACTIONS[document_id]}
    fields = {name: dict(entry) for name, entry in extraction["fields"].items()}
    for correction in CORRECTIONS.get(document_id, []):
        name = correction["field"]
        entry = fields.get(name, field(None, 0.0, False))
        entry["value"] = correction["value"]
        entry["verified"] = True
        entry["gate"] = None
        entry["gate_error"] = None
        entry["source"] = {"origin": "human"}
        fields[name] = entry
    extraction["fields"] = fields
    return extraction


@app.get("/api/v1/documents/{document_id}/extraction")
async def get_extraction(
    document_id: str,
    authorization: str | None = Header(default=None),
) -> Response:
    if role_of(authorization) is None:
        return error(401, "UNAUTHORIZED", "Missing or invalid bearer token.", False)
    if document_id not in DOCUMENTS:
        return error(404, "NOT_FOUND", "No such document.", False)

    current, _, _ = progression(document_id)
    if current not in TERMINAL:
        return error(409, "NOT_READY", f"Document is {current}.", True)
    if document_id not in EXTRACTIONS:
        return error(409, "NOT_READY", "No extraction for this document yet.", True)

    return JSONResponse(status_code=200, content=_merged(document_id))


@app.patch("/api/v1/documents/{document_id}/extraction")
async def correct_extraction(
    document_id: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
) -> Response:
    role = role_of(authorization)
    if role is None:
        return error(401, "UNAUTHORIZED", "Missing or invalid bearer token.", False)
    if ROLE_RANK[role] < ROLE_RANK["reviewer"]:
        return error(403, "FORBIDDEN", "Role viewer cannot correct an extraction.", False)
    if document_id not in EXTRACTIONS:
        return error(404, "NOT_FOUND", "No such document.", False)

    corrections = payload.get("corrections")
    if not isinstance(corrections, list):
        return error(422, "EXTRACTION_FAILED", "corrections must be a list.", False)

    named = {c["field"] for c in corrections if isinstance(c, dict) and "field" in c}
    immutable = sorted(named & IMMUTABLE_FIELDS)
    if immutable:
        return error(
            422,
            "IMMUTABLE_FIELD",
            f"{', '.join(immutable)} is set at upload and cannot be corrected. "
            "Reclassification is a new upload, not an edit.",
            False,
        )

    stored = CORRECTIONS.setdefault(document_id, [])
    for correction in corrections:
        if isinstance(correction, dict):
            stored.append({"field": correction["field"], "value": correction["value"]})

    return JSONResponse(status_code=200, content=_merged(document_id))


@app.post("/api/v1/exports")
async def create_export(
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
) -> Response:
    if role_of(authorization) is None:
        return error(401, "UNAUTHORIZED", "Missing or invalid bearer token.", False)

    fmt = payload.get("format", "xlsx")
    if fmt not in {"xlsx"}:
        return error(415, "UNSUPPORTED_TYPE", f"Unsupported export format {fmt}.", False)

    export_id = str(uuid.uuid4())
    EXPORTS[export_id] = {"format": fmt, "document_ids": payload.get("document_ids", [])}
    return JSONResponse(status_code=202, content={"export_id": export_id, "status": "queued"})


@app.get("/api/v1/exports/{export_id}")
async def get_export(
    export_id: str,
    authorization: str | None = Header(default=None),
) -> Response:
    if role_of(authorization) is None:
        return error(401, "UNAUTHORIZED", "Missing or invalid bearer token.", False)
    if export_id not in EXPORTS:
        return error(404, "NOT_FOUND", "No such export.", False)

    return JSONResponse(
        status_code=200,
        content={
            "status": "complete",
            "download_url": f"/api/v1/exports/{export_id}/file",
            "expires_at": "2026-08-05T00:00:00Z",
        },
    )


@app.get("/api/v1/exports/{export_id}/file")
async def download_export(
    export_id: str,
    authorization: str | None = Header(default=None),
) -> Response:
    if role_of(authorization) is None:
        return error(401, "UNAUTHORIZED", "Missing or invalid bearer token.", False)
    if export_id not in EXPORTS:
        return error(404, "NOT_FOUND", "No such export.", False)

    return Response(
        content=b"PK\x03\x04mock-xlsx-bytes",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="export-{export_id}.xlsx"'},
    )
