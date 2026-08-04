---
status: active
owner: Adeen
last_reviewed: 2026-08-04
version: 1.0.0
---

# PROJECT_CONTEXT.md — Second Brain

> **Read this file first.** Every coding session (human or AI assistant) starts here.
> If something in this file is wrong, fix it *before* writing code. Stale context is worse than no context.

---

## 1. What this is

An internal document-intelligence service. It ingests scanned/PDF business documents
(invoices, purchase orders, contracts, quotations, billing sheets) and returns a
**validated structured record** plus an Excel export.

**Not** a chatbot. **Not** a general document Q&A tool. One job: document in, verified fields out.

## 2. Why it exists

Documents arrive from many vendors in many layouts. Today someone retypes the fields into
Excel by hand. That is slow, expensive, and silently wrong. The failure mode we care about
is not "slow" — it is **confidently wrong numbers reaching a billing sheet**.

Design consequence: **we prefer flagging a field as unverified over guessing it.**

## 3. Current stack (real, not aspirational)

| Layer | Choice | Notes |
|---|---|---|
| OCR (Latin) | PaddleOCR PP-OCRv5 | primary text + layout |
| OCR (Urdu) | Qaari-0.1-Urdu | second stage, Urdu regions |
| LLM | Qwen2.5-7B-Instruct | **local**, self-hosted |
| Compute | 1× L20, 48 GB GDDR6 | single node, no cluster |
| Validation | deterministic gates | IBAN checksum, CNIC digit count, arithmetic reconciliation |
| Synthetic data | SynthDoG + Faker `ur_PK` | training/eval corpus |

**Explicitly NOT in scope right now:** Kubernetes, multi-tenant orgs, OAuth/SSO, MinIO/S3,
hosted GPT/Claude API calls, mobile app, ERP connectors. If a doc or a code comment mentions
these, it is out of date — delete it.

## 4. Team split

- **Adeen — backend.** OCR pipeline, LLM extraction, validation gates, API, DB, Excel export.
- **Friend — frontend.** Upload UI, processing status, review/correction screen, export trigger.

**The contract between them is [`API_CONTRACT.md`](./API_CONTRACT.md).**
Neither side changes it unilaterally. Change = both agree, bump version, update the file in
the same commit as the code.

### Working rule
Frontend does **not** wait for backend. Backend ships the API contract + a mock server on day one;
frontend builds against the mock. First integration happens against a real endpoint that already
matches a contract both sides have read.

## 5. The two artifacts everything hangs off

1. **[`EXTRACTION_SCHEMA.json`](./EXTRACTION_SCHEMA.json)** — the only shape an extraction result
   ever takes. LLM output, DB row, API response, and Excel columns all derive from it.
   Change it → four things change. Do not change it casually.
2. **[`EVAL_AND_GOLDEN_SET.md`](./EVAL_AND_GOLDEN_SET.md)** — how we know it works.
   No accuracy claim is valid unless it came from the harness described there.

## 6. Non-negotiable invariants

These are the rules that, if broken, make the product worthless. Guard them in code and tests.

- **INV-1** The LLM never emits a number that reaches Excel unchecked. Every monetary field
  passes arithmetic reconciliation or is marked `unverified`.
- **INV-2** Every extracted field carries a confidence value and a source span (page + bbox).
  A field with no provenance is a bug, not a low-confidence result.
- **INV-3** Raw uploads are immutable. Reprocessing re-reads the original file; it never mutates it.
- **INV-4** Extraction is idempotent per (document, pipeline_version). Re-running produces a new
  extraction row, never an overwrite. Audit trail is append-only.
- **INV-5** Deterministic validators are authoritative over the LLM. If the checksum says the IBAN
  is invalid, the IBAN is invalid — regardless of model confidence.

## 7. Open questions

Keep this list short and honest. Move items to a decision below once resolved.

- [ ] Concurrency limit on the L20 — how many documents in flight before latency degrades?
- [ ] Human review: is correction mandatory below a confidence threshold, or advisory?
- [ ] Retention: how long do we keep raw uploads?
- [ ] Multi-page documents: one extraction per file, or per logical document?

## 8. Decision log

Append-only. Each decision is an ADR in [`decisions/`](./decisions/) — context, reasoning,
consequences, and what would make us revisit it. Never edit a decided ADR's reasoning; supersede
it with a new one.

- [[ADR-001-local-llm]] — Local Qwen2.5-7B instead of hosted GPT/Claude. Data residency + fixed cost on owned GPU.
- [[ADR-002-two-stage-ocr]] — Two-stage OCR (PaddleOCR + Qaari). Single engine handles Urdu poorly.
- [[ADR-003-deterministic-gates]] — Deterministic gates over model self-reported confidence. Model confidence is uncalibrated on numbers.

## 9. Session protocol (for AI coding assistants)

At the start of a session, state in one line: which invariant your change touches, and which
file in `docs/` you will update. At the end, if behaviour diverged from these docs, update the
docs in the same commit. **Do not report a task complete based on your own summary — quote the
decisive command output.**

## 10. Glossary

- **MRC** — Monthly Recurring Charge.
- **OTC** — One-Time Charge.
- **Gate** — a deterministic validator that can fail an extraction without the LLM's involvement.
- **Golden set** — hand-labelled documents used to measure accuracy. See `EVAL_AND_GOLDEN_SET.md`.
- **Pipeline version** — the tuple of (OCR versions, model, prompt hash). Stamped on every extraction.
