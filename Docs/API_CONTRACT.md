---
status: draft
owner: Adeen & Frontend
last_reviewed: 2026-08-04
version: 0.2.0
---

# API_CONTRACT.md

**Version:** 0.2.0 · **Status:** Draft — freeze before frontend work starts
**Owners:** backend (Adeen) + frontend (friend). Changes require both.

Base path: `/api/v1`. All bodies JSON unless stated. All timestamps ISO-8601 UTC.

---

## Ground rules

1. Extraction is **async**. Upload returns immediately; the client polls or subscribes.
2. Field shapes come from `EXTRACTION_SCHEMA.json`. This file does not restate them — it references them.
3. Errors always use the envelope in §7. Frontend renders `message`; logs `code` and `trace_id`.
4. Additive changes (new optional field) → minor bump, no coordination. Removing or renaming a field → major bump, both sides agree first.

---

## 1. Auth

Single-tenant internal tool. JWT bearer token, no OAuth.

```
POST /api/v1/auth/login
{ "email": "...", "password": "..." }
→ 200 { "access_token": "...", "expires_in": 3600, "user": { "id", "name", "role" } }
→ 401 invalid credentials
```

All other endpoints: `Authorization: Bearer <token>`.
Roles: `viewer` (read + export), `reviewer` (+ correct), `admin` (+ delete, settings).

---

## 2. Upload

```
POST /api/v1/documents
Content-Type: multipart/form-data
  file: <pdf|png|jpg|tiff>   max 25 MB
→ 202 {
    "document_id": "uuid",
    "filename": "...",
    "status": "queued",
    "uploaded_at": "..."
  }
→ 413 file too large   → 415 unsupported type
```

`status` ∈ `queued | ocr | extracting | validating | needs_review | complete | failed`

> Frontend: treat this list as closed. If an unknown status arrives, show it verbatim and do not crash.

---

## 3. Status polling

```
GET /api/v1/documents/{id}/status
→ 200 {
    "document_id": "uuid",
    "status": "extracting",
    "progress": 0.55,          // 0..1, advisory only — never gate UI on exact values
    "stage_detail": "urdu_ocr",
    "error": null
  }
```

Poll interval: 2 s while not terminal. Terminal states: `complete`, `needs_review`, `failed`.

---

## 4. Extraction result

```
GET /api/v1/documents/{id}/extraction
→ 200  <ExtractionResult>   // shape defined in EXTRACTION_SCHEMA.json
→ 409  { "code": "NOT_READY", ... } if status is not terminal
```

Every field object carries `value`, `confidence`, `verified`, `source` (page + bbox).
**Frontend must render `verified: false` visually distinct from low confidence** — they are
different failures. Low confidence = model unsure. Unverified = a deterministic gate could not
confirm it.

### Gate results are three-state (new in 0.2.0)

`gates[].passed` (boolean) is **removed**. It is replaced by `gates[].result`:

```
"gates": [
  { "name": "iban_checksum",     "result": "passed",      "affected_fields": ["iban"] },
  { "name": "cnic_format_check", "result": "format_only", "affected_fields": ["cnic"] }
]
```

| `result` | Means | `verified` |
|---|---|---|
| `passed` | A deterministic check confirmed the value | may be `true` |
| `failed` | A deterministic check rejected the value | always `false` |
| `format_only` | Well-formed, but nothing confirmed it is *correct* | **always `false`** |

**`format_only` never implies `verified`.** It is not a soft pass. Most identifiers on these
documents carry no checksum — a CNIC's trailing digit is a gender marker, not a check digit, and
NTN and STRN have none — so a format check can only prove a value is *malformed*, never that a
well-formed value is the right one. `iban_checksum` is the only identifier gate that can verify.
`format_only` is also what a gate returns when its field is absent.

**Frontend: render `format_only` as unconfirmed, alongside `failed`, not alongside `passed`.**
Treating it as a pass reintroduces exactly the failure the gates exist to prevent — see
[`decisions/ADR-004-format-only-gate-state.md`](./decisions/ADR-004-format-only-gate-state.md).
Field shapes remain defined by `EXTRACTION_SCHEMA.json` (now 0.2.0), which this file references
rather than restates.

---

## 5. Human correction

```
PATCH /api/v1/documents/{id}/extraction
{
  "corrections": [
    { "field": "mrc", "value": "45000.00" },
    { "field": "po_number", "value": "PO-2291" }
  ]
}
→ 200 <ExtractionResult>   // corrected fields now verified=true, source="human"
→ 403 role < reviewer
```

Corrections are append-only in the DB (audit trail). The response returns the merged current view.

---

## 6. Export

```
POST /api/v1/exports
{ "document_ids": ["uuid", ...], "format": "xlsx" }   // xlsx | csv | json
→ 202 { "export_id": "uuid", "status": "queued" }

GET /api/v1/exports/{id}
→ 200 { "status": "complete", "download_url": "/api/v1/exports/{id}/file", "expires_at": "..." }

GET /api/v1/exports/{id}/file
→ 200 binary stream
```

Column order for `xlsx` is fixed and derived from `EXTRACTION_SCHEMA.json` field order.

---

## 7. Listing

```
GET /api/v1/documents?status=&page=1&page_size=25&q=&from=&to=
→ 200 {
    "items": [ { "document_id", "filename", "status", "document_type",
                 "uploaded_at", "needs_review_count" } ],
    "page": 1, "page_size": 25, "total": 137
  }
```

---

## 8. Error envelope

```json
{
  "error": {
    "code": "OCR_FAILED",
    "message": "Could not read text from page 3.",
    "trace_id": "uuid",
    "retryable": true
  }
}
```

| Code | HTTP | Retryable |
|---|---|---|
| `UNAUTHORIZED` | 401 | no |
| `FORBIDDEN` | 403 | no |
| `NOT_FOUND` | 404 | no |
| `NOT_READY` | 409 | yes |
| `UNSUPPORTED_TYPE` | 415 | no |
| `FILE_TOO_LARGE` | 413 | no |
| `OCR_FAILED` | 422 | yes |
| `EXTRACTION_FAILED` | 422 | yes |
| `RATE_LIMITED` | 429 | yes |
| `INTERNAL` | 500 | yes |

---

## 9. Mock server

Backend ships a mock **before** the real implementation so frontend is never blocked.
Minimum: FastAPI app returning fixture responses for every endpoint above, with an artificial
status progression (`queued → ocr → extracting → complete`) over ~10 s
(`MOCK_STATUS_PROGRESSION_SECONDS`).

**Module:** `backend/tests/mock_server.py`, exposing `app`.
**Command:**

```bash
uv run uvicorn tests.mock_server:app --reload --port 8000
```

Base URL for the frontend: `http://localhost:8000/api/v1`, supplied via one env var.

The mock lives under `tests/`, **not** under `app/`. It is a test double: shipped code must never
import it, and it stays outside the mypy-strict scope (`files = ["app"]`). A mock in `app/` is a
mock that eventually gets deployed.

Fixtures live in `backend/tests/fixtures/`.
