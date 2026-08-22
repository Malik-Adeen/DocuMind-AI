# DocuMind AI

An internal document-intelligence service. It ingests scanned or PDF business documents —
invoices, purchase orders, contracts, quotations, billing sheets — and returns a validated
structured record plus an Excel export.

It is not a chatbot and not a general document Q&A tool. One job: document in, verified fields
out. The design bias throughout is to flag a field as unverified rather than guess it — the
failure mode this system exists to prevent is a confidently wrong number reaching a billing
sheet, not slowness.

Full background, the current stack, and the non-negotiable invariants (INV-1 … INV-6) live in
[`Docs/PROJECT_CONTEXT.md`](Docs/PROJECT_CONTEXT.md) — read that first in any working session.
The system design, component map, and failure-mode table live in
[`Docs/ARCHITECTURE.md`](Docs/ARCHITECTURE.md).

## Pipeline stages

A document moves through these stages, in order, once it is picked up by a Celery worker:

1. **Deskew** — level a skewed scan before OCR reads it; an exact no-op on an already-straight page.
2. **PaddleOCR PP-OCRv5** — page count discovered up front; every page of a PDF is rasterized and
   read, not page 1 only. A page count over the configured cap fails fast, before any OCR call.
3. **Qaari-0.1-Urdu** — a second OCR pass over Urdu-detected regions only.
4. **Text assembly and cleanup** — merge the two OCR passes into one per-page text corpus.
5. **Qwen2.5-7B-Instruct** — extracts structured JSON matching the extraction schema; local vLLM
   in production, a hosted API in the prototype profile (never for a real document — see INV-6).
6. **Schema validation** — reject malformed output outright; no partial accept.
7. **Provenance merge** — match every field's claimed quote back to the OCR region that produced
   it, recovering its page and bounding box. No match means the claim is flagged unmatched, never
   a fabricated location.
8. **Deterministic gates** — IBAN checksum, CNIC/NTN/STRN format checks, arithmetic reconciliation.
   These, not the model's self-reported confidence, decide what `verified: true` means.
9. **Persist and route** — write the extraction and route the document to `complete` or
   `needs_review`.

The full component diagram, including what does and doesn't run yet, is in
[`Docs/ARCHITECTURE.md`](Docs/ARCHITECTURE.md) §2.

## Stack

- OCR: PaddleOCR PP-OCRv5 (Latin/layout), Qaari-0.1-Urdu (second stage, Urdu regions)
- LLM: Qwen2.5-7B-Instruct — local via vLLM in production, hosted API in the prototype profile
- Backend: Python 3.11, FastAPI, Celery + Redis, PostgreSQL 16 with SQLAlchemy/Alembic
- Frontend: React, Vite (`CodeBase/frontend/documind-ai`)
- Validation: deterministic gates, no model involvement — three-state results
  (`passed` / `failed` / `format_only`)
- Export: openpyxl
- Package manager: `uv` (backend), `npm` (frontend). Lint/format: `ruff`. Types: `mypy` on `app/`.

Two deployment profiles exist: `prototype` (RTX 3060 Ti, hosted LLM, public/synthetic documents
only) and `production` (L20, everything local, real documents permitted). See
[`Docs/PROJECT_CONTEXT.md`](Docs/PROJECT_CONTEXT.md) §3.

## Quickstart

```bash
./dev.sh start
```

This brings up Postgres and Redis via Docker Compose, waits for both to report healthy, then
starts the Celery worker, the FastAPI dev server, and the frontend dev server in the background.
Logs land under `.dev/*.log`; PIDs under `.dev/*.pid`.

```bash
./dev.sh stop
```

Stops all three background processes and brings the Compose stack down.

The frontend expects port 5173 free — its CORS origin is fixed to `http://localhost:5173`
(`app/core/config.py`'s `cors_allow_origins`), so `dev.sh` refuses to start rather than let Vite
silently fall back to a different port and break login.

For running things individually, migrations, seeding, and the test suite, see
[`CodeBase/backend/CLAUDE.md`](CodeBase/backend/CLAUDE.md)'s Commands section.

## Current limitations

**No accuracy number exists for this system yet, and none is quotable until one does.** The eval
harness described in [`Docs/EVAL_AND_GOLDEN_SET.md`](Docs/EVAL_AND_GOLDEN_SET.md) has not been
built: `CodeBase/backend/evals/` currently holds three `.gitkeep` placeholders and nothing else — no
`run_eval.py`, no `scorers.py`, no golden documents. The `uv run python evals/run_eval.py` command
listed in the backend's own command reference does not currently run. Any accuracy figure quoted
anywhere else in this repo's history predates that rule and should not be trusted.

Other known gaps, stated plainly rather than discovered later:

- `/status.error` is `null` for most failure causes — populated only for a hosted-endpoint refusal,
  a truncated LLM response, and the generic internal-error catch-all. An OCR crash, an LLM
  schema-validation failure, and a gate-coverage failure still leave it `null`. An unrecognized
  `document_type` is surfaced via `review.reason`, not `/status.error`.
- Two of the eight named gates (`ntn_format_check`, `strn_format_check`) have no corresponding
  field in the extraction schema to check against.
- No streaming: large multi-page PDFs load fully into memory.
- The frontend has no inline PDF preview and no page-switcher; `source.page` is correct end to end
  in the API response, but nothing yet displays it.
- Single point of failure at the GPU stage; no horizontal scaling story while storage is local
  filesystem.

The full, current list — including what is deliberately out of scope — is in
[`Docs/PROJECT_CONTEXT.md`](Docs/PROJECT_CONTEXT.md) §7 and
[`Docs/ARCHITECTURE.md`](Docs/ARCHITECTURE.md) §8.

## Decisions

Every non-obvious design decision is recorded as an ADR, in order, with its context, reasoning,
and what would make it worth revisiting: [`Docs/INDEX.md`](Docs/INDEX.md). Start there before
touching code that already has a decision behind it.
