from __future__ import annotations

import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, Form, Header, Request, UploadFile
from fastapi.responses import JSONResponse, Response

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

PIPELINE_VERSION = {
    "profile": "prototype",
    "ocr_latin": "paddleocr-pp-ocrv5",
    "ocr_urdu": "qaari-0.1-urdu",
    "llm": "qwen2.5-7b-instruct",
    "prompt_hash": "sha256:2f1a9c",
    "schema_version": "0.3.0",
}

DOC_FAILED_GATE = "11111111-1111-1111-1111-111111111111"
DOC_FORMAT_ONLY = "22222222-2222-2222-2222-222222222222"
DOC_LOW_CONF_VERIFIED = "33333333-3333-3333-3333-333333333333"


def _source(origin: str, page: int = 1) -> dict[str, Any]:
    return {"origin": origin, "page": page, "bbox": [0.1, 0.2, 0.5, 0.24]}


def _field(
    value: str | None,
    confidence: float,
    verified: bool,
    gate: str | None = None,
    origin: str = "ocr_latin",
    gate_error: str | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "confidence": confidence,
        "verified": verified,
        "gate": gate,
        "gate_error": gate_error,
        "source": _source(origin),
    }


EXTRACTIONS: dict[str, dict[str, Any]] = {
    DOC_FAILED_GATE: {
        "document_id": DOC_FAILED_GATE,
        "extraction_id": "aaaaaaaa-0000-4000-8000-000000000001",
        "pipeline_version": PIPELINE_VERSION,
        "status": "needs_review",
        "document_type": {"value": "invoice", "confidence": 0.97},
        "language": {"primary": "en", "confidence": 0.99},
        "fields": {
            "po_number": _field("PO-2291", 0.96, False),
            "customer_name": _field("Karachi Textile Mills", 0.94, False),
            "iban": _field(
                "PK70BANK0000001234567890",
                0.88,
                False,
                gate="iban_checksum",
                gate_error="mod-97 checksum failed: remainder 87, expected 1",
            ),
            "subtotal": _field("25000.00", 0.93, False, gate="line_item_sum"),
            "tax": _field("4250.00", 0.91, False, gate="arithmetic_reconciliation"),
            "total": _field("29000.00", 0.92, False, gate="arithmetic_reconciliation"),
        },
        "line_items": [
            {
                "description": _field("Fibre link 100 Mbps", 0.95, False),
                "quantity": _field("2", 0.99, False),
                "unit_price": _field("10000.00", 0.94, False),
                "line_total": _field("20000.00", 0.94, False),
            },
            {
                "description": _field("Installation", 0.93, False),
                "quantity": _field("1", 0.99, False),
                "unit_price": _field("5000.00", 0.94, False),
                "line_total": _field("5000.00", 0.94, False),
            },
        ],
        "gates": [
            {
                "name": "line_item_sum",
                "result": "passed",
                "detail": "2 line items sum to subtotal 25000.00",
                "affected_fields": ["subtotal"],
            },
            {
                "name": "arithmetic_reconciliation",
                "result": "failed",
                "detail": "subtotal 25000.00 + tax 4250.00 = 29250.00, total is 29000.00",
                "affected_fields": ["subtotal", "tax", "total"],
            },
            {
                "name": "iban_checksum",
                "result": "failed",
                "detail": "mod-97 checksum failed: remainder 87, expected 1",
                "affected_fields": ["iban"],
            },
        ],
        "review": {"required": True, "reason": "gate_failed:arithmetic_reconciliation"},
        "timings_ms": {"ocr_latin": 3100, "llm": 41200, "validation": 8, "total": 44308},
        "created_at": "2026-08-04T09:15:00Z",
    },
    DOC_FORMAT_ONLY: {
        "document_id": DOC_FORMAT_ONLY,
        "extraction_id": "aaaaaaaa-0000-4000-8000-000000000002",
        "pipeline_version": PIPELINE_VERSION,
        "status": "needs_review",
        "document_type": {"value": "contract", "confidence": 0.91},
        "language": {"primary": "mixed", "confidence": 0.87},
        "fields": {
            "customer_name": _field("لاہور ٹیکسٹائل", 0.79, False, origin="ocr_urdu"),
            "cnic": _field("42101-1234567-1", 0.95, False, gate="cnic_format_check"),
            "mrc": _field("45000.00", 0.9, False, gate="arithmetic_reconciliation"),
            "otc": _field("5000.00", 0.89, False, gate="arithmetic_reconciliation"),
        },
        "line_items": [],
        "gates": [
            {
                "name": "cnic_format_check",
                "result": "format_only",
                "detail": "13 digits, well-formed; CNIC has no checksum so nothing is confirmed",
                "affected_fields": ["cnic"],
            },
            {
                "name": "arithmetic_reconciliation",
                "result": "format_only",
                "detail": (
                    "mrc/otc to total relationship is undetermined: no specified rule "
                    "exists to check them against subtotal or total. See ADR-005"
                ),
                "affected_fields": ["mrc", "otc"],
            },
            {
                "name": "line_item_sum",
                "result": "format_only",
                "detail": "line item sum not computable: line_items absent",
                "affected_fields": ["line_items"],
            },
        ],
        "review": {"required": True, "reason": "format_only:cnic"},
        "timings_ms": {"ocr_latin": 2900, "ocr_urdu": 5100, "llm": 38800, "total": 46800},
        "created_at": "2026-08-04T10:02:00Z",
    },
    DOC_LOW_CONF_VERIFIED: {
        "document_id": DOC_LOW_CONF_VERIFIED,
        "extraction_id": "aaaaaaaa-0000-4000-8000-000000000003",
        "pipeline_version": PIPELINE_VERSION,
        "status": "complete",
        "document_type": {"value": "invoice", "confidence": 0.88},
        "language": {"primary": "en", "confidence": 0.96},
        "fields": {
            "iban": _field("PK36SCBL0000001123456702", 0.41, True, gate="iban_checksum"),
            "subtotal": _field("10000.00", 0.45, True, gate="line_item_sum"),
            "tax": _field("1700.00", 0.52, True, gate="arithmetic_reconciliation"),
            "total": _field("11700.00", 0.49, True, gate="arithmetic_reconciliation"),
        },
        "line_items": [
            {
                "description": _field("Managed router", 0.44, False),
                "quantity": _field("1", 0.98, False),
                "unit_price": _field("10000.00", 0.45, False),
                "line_total": _field("10000.00", 0.45, False),
            }
        ],
        "gates": [
            {
                "name": "iban_checksum",
                "result": "passed",
                "detail": "mod-97 checksum verified",
                "affected_fields": ["iban"],
            },
            {
                "name": "line_item_sum",
                "result": "passed",
                "detail": "1 line items sum to subtotal 10000.00",
                "affected_fields": ["subtotal"],
            },
            {
                "name": "arithmetic_reconciliation",
                "result": "passed",
                "detail": "subtotal 10000.00 + tax 1700.00 = total 11700.00",
                "affected_fields": ["subtotal", "tax", "total"],
            },
        ],
        "review": {"required": False, "reason": "low_confidence:iban"},
        "timings_ms": {"ocr_latin": 2200, "llm": 30100, "validation": 6, "total": 32306},
        "created_at": "2026-08-04T11:40:00Z",
    },
}

DOCUMENTS: dict[str, dict[str, Any]] = {
    DOC_FAILED_GATE: {
        "filename": "invoice-2291.pdf",
        "status": "needs_review",
        "document_type": "invoice",
        "data_classification": "synthetic",
        "uploaded_at": "2026-08-04T09:14:10Z",
        "needs_review_count": 3,
        "uploaded_monotonic": None,
    },
    DOC_FORMAT_ONLY: {
        "filename": "contract-lahore.pdf",
        "status": "needs_review",
        "document_type": "contract",
        "data_classification": "synthetic",
        "uploaded_at": "2026-08-04T10:01:05Z",
        "needs_review_count": 2,
        "uploaded_monotonic": None,
    },
    DOC_LOW_CONF_VERIFIED: {
        "filename": "invoice-8841.pdf",
        "status": "complete",
        "document_type": "invoice",
        "data_classification": "public",
        "uploaded_at": "2026-08-04T11:39:02Z",
        "needs_review_count": 0,
        "uploaded_monotonic": None,
    },
}

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


def _merged(document_id: str) -> dict[str, Any]:
    extraction = {**EXTRACTIONS[document_id]}
    fields = {name: dict(entry) for name, entry in extraction["fields"].items()}
    for correction in CORRECTIONS.get(document_id, []):
        name = correction["field"]
        entry = fields.get(name, _field(None, 0.0, False))
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
    if fmt not in {"xlsx", "csv", "json"}:
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
