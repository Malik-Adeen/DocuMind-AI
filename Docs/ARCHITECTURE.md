---
status: active
owner: Adeen
last_reviewed: 2026-08-04
version: 1.0.0
---

# ARCHITECTURE.md

Scope: the system as it actually is — one node, one GPU, one tenant.
Aspirational infrastructure lives in `PROJECT_CONTEXT.md` §3 under "not in scope".

---

## 1. Constraints that shape everything

- **One L20, 48 GB.** OCR models and Qwen2.5-7B share it. Throughput is bounded by GPU, not CPU or IO.
- **Single tenant, internal users.** No org isolation, no per-tenant quotas.
- **Correctness > latency.** A 90-second document that is right beats a 10-second document that is wrong.

Consequence: the design is a **queue with a serialised GPU stage**, not a scale-out service.
Everything else exists to keep that stage fed and to check its output.

---

## 2. Components

```
Browser (Next.js)
      │  HTTPS, JWT
      ▼
FastAPI  ──────────►  PostgreSQL   (documents, extractions, corrections, audit)
      │                     ▲
      │ enqueue             │
      ▼                     │
Redis ──► Celery worker ────┘
              │
              ├─ Stage 1  PaddleOCR PP-OCRv5      → text + layout boxes
              ├─ Stage 2  Qaari-0.1-Urdu          → Urdu regions only
              ├─ Stage 3  text assembly + cleanup
              ├─ Stage 4  Qwen2.5-7B-Instruct     → JSON per EXTRACTION_SCHEMA
              ├─ Stage 5  schema validation       → reject malformed, no partial accept
              ├─ Stage 6  deterministic gates     → IBAN / CNIC / arithmetic
              └─ Stage 7  persist + route         → complete | needs_review
                            │
                            ▼
                  Excel generator (on demand)
```

Local filesystem for raw uploads and exports. Not MinIO, not S3 — a directory with a documented
path and a backup cron. Swap later if it ever needs to be shared across nodes.

---

## 3. Why a queue at all

Because the GPU stage is serial and slow. Without a queue, a second upload either blocks an HTTP
request for a minute or OOMs the GPU. Celery gives: bounded concurrency, retry on transient
failure, and a status a client can poll. `API_CONTRACT.md` §3 exists because of this design, not
the other way round.

**Concurrency is a config value, not a guess.** Set it from the load test in
`EVAL_AND_GOLDEN_SET.md` §4.

---

## 4. The two-stage OCR decision

Neither engine alone is sufficient. PaddleOCR handles Latin text and layout well and is weak on
Urdu script; Qaari is Urdu-specialised and not a general layout engine.

Flow: PaddleOCR runs first and produces layout regions. Regions whose script is detected as Urdu
are re-read by Qaari. Results are merged by bounding box, Qaari winning on overlap in Urdu regions.

**Cost:** two model loads resident on one GPU, and a merge step that can produce duplicated or
dropped text at region boundaries. That merge is a known sharp edge — it needs its own unit tests
with overlapping-box fixtures.

---

## 5. Validation as a separate stage

The gates (Stage 6) are ordinary deterministic code. No model involvement.

- `iban_checksum` — mod-97.
- `cnic_digit_count` — 13 digits, format check.
- `arithmetic_reconciliation` — line items sum to subtotal; subtotal + tax = total; MRC/OTC consistent with terms.
- `date_parse` — parses to a real date, and is not absurd (e.g. year 1900).
- `currency_consistency` — one currency per document.

A gate failure does **not** fail the document. It sets `verified: false` on the affected fields and
routes to `needs_review`. Silent auto-correction is forbidden — it converts a visible problem into
an invisible one.

---

## 6. Data model (shape, not DDL)

- `documents` — file metadata, current status. Raw file immutable (INV-3).
- `extractions` — one row per pipeline run, stamped with `pipeline_version`. Append-only (INV-4).
- `corrections` — one row per human edit, referencing extraction + field. Append-only.
- `exports` — export jobs and their artifacts.
- `users` — id, name, email, password hash, role.
- `audit_log` — who did what, when.

Current extraction view = latest extraction + corrections applied on top. Never destructive.

---

## 7. Failure modes and what happens

| Failure | Behaviour |
|---|---|
| OCR returns near-empty text | fail fast, `OCR_FAILED`, retryable. Do not send empty text to the LLM. |
| LLM emits invalid JSON | retry once with a repair prompt; then `EXTRACTION_FAILED`. Never regex-patch the JSON. |
| LLM omits a required field | field is `null`, `confidence: 0` — not a crash. |
| Gate fails | `needs_review`, affected fields `verified: false`. |
| GPU OOM | task retries with backoff; concurrency limit is the real fix. |
| Worker dies mid-task | Celery re-queues; idempotency (INV-4) makes this safe. |

---

## 8. Known weaknesses

Stated plainly so they are chosen, not discovered:

- **Single point of failure at the GPU.** No node dies gracefully here. Acceptable for internal use.
- **OCR merge boundary** (§4) is the most likely source of silent text corruption.
- **7B model on numerically dense documents.** The gates exist precisely because we do not trust it.
- **Local filesystem storage** blocks horizontal scaling the day a second node appears.
- **No streaming.** Large multi-page PDFs load fully into memory.

---

## 9. What would change this design

Write it down when it happens: a second GPU node, an external tenant, a p95 latency requirement,
or a document volume that makes the serial GPU stage the business bottleneck. None are true today.
