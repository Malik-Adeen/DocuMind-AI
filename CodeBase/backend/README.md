# backend

The document-intelligence service: a scanned or PDF business document goes in, a validated
structured record and an Excel export come out. Two-stage OCR (PaddleOCR for Latin, Qaari for
Urdu) feeds a locally hosted Qwen2.5-7B-Instruct extraction step, whose output is then judged by
deterministic gates — IBAN mod-97, arithmetic reconciliation, date parse — that outrank the
model's own confidence. Anything a gate cannot confirm is returned marked `unverified` rather
than guessed. Read [`../../Docs/PROJECT_CONTEXT.md`](../../Docs/PROJECT_CONTEXT.md) before
writing code here; the working rules for this directory are in
[`CLAUDE.md`](./CLAUDE.md).

## Setup

```bash
uv sync
cp .env.example .env
```

## Mock server

The frontend is built against a mock, not against the real pipeline — see
[`../../Docs/API_CONTRACT.md`](../../Docs/API_CONTRACT.md) §9. The mock serves fixture responses
from `tests/fixtures/` for every endpoint in the contract and walks a document through
`queued → ocr → extracting → complete` over roughly ten seconds
(`MOCK_STATUS_PROGRESSION_SECONDS`).

```bash
uv run uvicorn tests.mock_server:app --reload --port 8000
```

Point the frontend's API base URL at `http://localhost:8000/api/v1`.

The mock lives in `tests/`, not `app/`. It is a test double, not shipped code: it must never be
importable from the real application, and it is deliberately outside the `files = ["app"]` scope
of mypy-strict in `pyproject.toml`.

> Not yet implemented — this repository is currently a scaffold. `tests/mock_server.py` and the
> fixtures it serves are the first thing to be written, before any pipeline code.
