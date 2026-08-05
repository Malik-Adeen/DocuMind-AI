# CLAUDE.md — backend

Extends `../CLAUDE.md`. Owner: Adeen.

## Stack

Python 3.11 · FastAPI · Celery + Redis · PostgreSQL + SQLAlchemy/Alembic · vLLM (Qwen2.5-7B-Instruct) · PaddleOCR PP-OCRv5 · Qaari-0.1-Urdu · openpyxl · pytest.

Package manager: `uv`. Lint/format: `ruff`. Types: `mypy` on `app/` (not on tests).

## Layout

```
backend/
├── app/
│   ├── api/v1/          # routers — thin, no business logic
│   ├── core/            # config, security, logging
│   ├── db/              # models, session, migrations/
│   ├── schemas/         # pydantic — generated from EXTRACTION_SCHEMA.json, not hand-written
│   ├── pipeline/
│   │   ├── ocr/         # paddle.py, qaari.py, merge.py
│   │   ├── llm/         # client.py, prompts/, repair.py
│   │   ├── gates/       # one module per validator
│   │   └── orchestrator.py
│   ├── workers/         # celery tasks
│   └── export/          # xlsx, csv, json
├── tests/
│   ├── unit/  integration/  contract/  fixtures/
├── tools/               # developer scripts, not shipped, not under mypy
└── evals/               # see ../../Docs/EVAL_AND_GOLDEN_SET.md
```

## Rules

- **Routers are thin.** Parse, authorize, delegate, serialize. Business logic lives in `pipeline/` or a service module. A router with an `if` about extraction logic is misplaced.
- **Pydantic models derive from `EXTRACTION_SCHEMA.json`.** Do not hand-maintain a parallel definition — they will drift. Generate or load, and test that they match.
- **Each gate is one module, one pure function**, signature `(extraction) -> GateResult`. No I/O, no model calls. Trivially unit-testable, and that is the point.
- **A gate returns three states, not two:** `passed`, `failed`, `format_only`. Format-only checks (CNIC, NTN, STRN) can never set `verified: true` — they have no checksum. Only IBAN mod-97, arithmetic reconciliation, and date parse can verify.
- **Money is `Decimal` in Python, `NUMERIC` in Postgres, decimal string in JSON.** Never float, at any layer.
- **Every DB write that represents an extraction or correction is an INSERT.** No UPDATE on those tables (INV-4).
- **Celery tasks are idempotent and re-runnable.** Assume the worker will die mid-task, because it will.
- **The LLM call goes through one client module.** Prompts live in `llm/prompts/` as files, hashed into `pipeline_version`. Do not inline prompt strings in business logic.
- **Structured output via vLLM `guided_json` + XGrammar backend.** Retry-with-repair is a backstop, capped at 1 retry — not the primary validity mechanism.
- **Log the trace_id on every request and task.** An error the frontend reports must be findable in your logs by that id alone.

## Commands

```bash
docker compose up -d                       # postgres 16, required by the app and integration tests
uv run alembic upgrade head                # apply migrations
uv run python -m app.db.seed               # 3 users + the 3 review-state documents
uv run uvicorn app.main:app --reload      # dev server
uv run celery -A app.workers worker -l info
uv run pytest tests/unit -q                # fast, run constantly
uv run pytest tests/contract -q            # must pass before any push
uv run pytest tests/integration -q         # needs postgres; skips cleanly without it
uv run alembic revision --autogenerate -m ""
uv run python evals/run_eval.py            # nightly; exits non-zero on gate failure
uv sync --group ocr                        # installs paddleocr; not in the default sync
uv run python tools/degrade.py IN OUT --seed 0   # 6-step degradation ladder from a clean image
```

## Before pushing

1. `ruff check . && ruff format --check .`
2. `uv run pytest tests/unit tests/contract -q` — quote the summary line
3. Mock server still matches `API_CONTRACT.md` — the contract suite proves it, by running
   every test against both `tests/mock_server.py` and `app.main:app`
4. Docs updated per [`../../Docs/AGENT_RULES.md`](../../Docs/AGENT_RULES.md) §2 (trigger table)
