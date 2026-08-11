---
status: active
owner: Adeen
last_reviewed: 2026-08-08
version: 1.1.1
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
| OCR (Urdu) | `oddadmix/Qaari-0.1-Urdu-OCR-VL-2B-Instruct` | second stage, Urdu regions. A **PEFT adapter on Qwen2-VL-2B**, not a classic OCR engine: it returns page text and **no coordinates** ([[DATASETS]] §4) |
| LLM | Qwen2.5-7B-Instruct | local on `production`; **hosted API on `prototype`** — see below |
| Compute | **`prototype`: RTX 3060 Ti, 8 GB.** `production`: 1× L20, 48 GB GDDR6 | single node, no cluster |
| Validation | deterministic gates | IBAN mod-97 (the only verifying identifier gate), CNIC/NTN/STRN format checks, arithmetic reconciliation. Three-state results — see [[ADR-004-format-only-gate-state]]. `app/pipeline/orchestrator.py` also validates the LLM's raw JSON against `EXTRACTION_SCHEMA.json` (via `jsonschema`'s `Draft202012Validator`) before any gate runs, rejecting malformed output outright rather than partially accepting it. `jsonschema` moved from the dev-only group to a real runtime dependency on 2026-08-07 for this reason |
| **Synthetic generation** | to be built — see [[ADR-008-synthetic-generation-is-a-component]] | **A component, not tooling.** No public dataset of mixed Urdu/English business documents exists, so this is the *only* source of training and eval data for the core document type. Field schema from FBR SRO 1006(I)/2021. Synthdog-RTL was evaluated and cannot be used as-is ([[DATASETS]] §2) |
| Synthetic text/values | SynthDoG-family renderer + Faker `ur_PK` | corpus values; the renderer is the open part |
| Image handling | Pillow | page size for bbox normalisation; the degradation ladder in `backend/tools/degrade.py` |

`paddleocr` is an **optional dependency group**, not a default one — `uv sync --group ocr` installs
it. It pulls PaddlePaddle, which nothing but Stage 1 needs, and the Stage 1 unit tests inject a fake
engine rather than loading a model. Without the group installed, importing
`app.pipeline.ocr.paddle` works and calling its loader does not.

### Two deployment profiles

**There is no L20 yet.** It is procured only if the project is approved. Until then everything runs
on a local RTX 3060 Ti, which cannot hold a 7B model alongside two OCR models — so the prototype
calls a hosted LLM API, and is therefore restricted to documents that carry no customer data.

| | `prototype` — now | `production` — if approved |
|---|---|---|
| GPU | RTX 3060 Ti, 8 GB | L20, 48 GB |
| PaddleOCR PP-OCRv5 | local | local |
| Qaari-0.1-Urdu | local, 4-bit base if fp16 does not fit | local, fp16 |
| Qwen2.5-7B-Instruct | hosted API | local (vLLM) |
| **Documents permitted** | **public and synthetic only** | real PTCL documents |

VRAM budgets are in [`ARCHITECTURE.md`](./ARCHITECTURE.md) §1. The data rule is **INV-6** in §6 and
the reasoning is [[ADR-006-two-deployment-profiles]].

**Explicitly NOT in scope right now:** Kubernetes, multi-tenant orgs, OAuth/SSO, MinIO/S3,
mobile app, ERP connectors. If a doc or a code comment mentions these, it is out of date — delete it.

**Hosted GPT/Claude API calls** were on that list and are now scoped rather than banned: permitted
on the `prototype` profile for public and synthetic documents only, never for a real PTCL document,
on any profile ([[ADR-006-two-deployment-profiles]], INV-6). [[ADR-001-local-llm]] is not reversed.

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
- **INV-6** **A real PTCL document never reaches a hosted API.** Every document **record** carries a
  `data_classification` of `public`, `synthetic` or `restricted`; only the first two may be sent to
  a hosted endpoint, on any profile, ever. It is **set at upload and immutable afterwards**, like
  the raw file under INV-3 — reclassification is a new document record with a new `document_id`,
  never an `UPDATE`. Default is `restricted`, and an absent or unrecognised value is `restricted`.
  Enforced by a guard in `backend/app/pipeline/llm/client.py` that reads the classification **off
  the record** and raises before the request is made; it is not a call argument, because an
  invariant that depends on every caller passing the right value is not an invariant
  ([[ADR-007-classification-on-the-document-record]]). Unlike INV-1 … INV-5 this one cannot be
  caught after the fact: nothing fails, no gate trips, and the data is already gone
  ([[ADR-006-two-deployment-profiles]]).

## 7. Open questions

Keep this list short and honest. Move items to a decision below once resolved.

- [ ] Concurrency limit on the L20 — how many documents in flight before latency degrades?
- [ ] Human review: is correction mandatory below a confidence threshold, or advisory?
- [ ] Retention: how long do we keep raw uploads?
- [ ] Multi-page documents: one extraction per file, or per logical document?
- [ ] **What generates our synthetic documents?** [[ADR-008-synthetic-generation-is-a-component]]
      decides generation is a component; it deliberately does not decide the implementation.
      Synthdog-RTL emits page-level plain text with no field boxes and no bidi ([[DATASETS]] §2), so
      the options are: fork it, build on `synthtiger` directly, or compose from a template engine.
- [ ] **How do FBR SRO 1006(I)/2021's mandated fields map onto [[EXTRACTION_SCHEMA.json]]?** The SRO
      is named as the generator's field schema and has not been read into this repository. Until
      that mapping exists, ADR-008 item 3 is a decision with no implementation.
- [ ] **How much synthetic data before it stops helping?** Unknown, and unmeasurable until the
      generator and the harness both exist.
- [ ] **Is there any deterministic relationship between `mrc`/`otc` and the totals?** No rule is
      known to hold across invoices, contracts and multi-month billing, so the sub-check is
      `format_only` and these two fields have no deterministic backstop ([[ADR-005-mrc-otc-relationship-unspecified]]).
      Answering it needs real PTCL documents in the golden set, and probably a `months` field
      read from `billing_terms`.

## 8. Decision log

Append-only. Each decision is an ADR in [`decisions/`](./decisions/) — context, reasoning,
consequences, and what would make us revisit it. Never edit a decided ADR's reasoning; supersede
it with a new one.

- [[ADR-001-local-llm]] — Local Qwen2.5-7B instead of hosted GPT/Claude. Data residency + fixed cost on owned GPU.
- [[ADR-002-two-stage-ocr]] — Two-stage OCR (PaddleOCR + Qaari). Single engine handles Urdu poorly.
- [[ADR-003-deterministic-gates]] — Deterministic gates over model self-reported confidence. Model confidence is uncalibrated on numbers. **Superseded by ADR-004.**
- [[ADR-004-format-only-gate-state]] — Gate results are three-state (`passed` / `failed` / `format_only`); a format check can never verify. CNIC's trailing digit is a gender marker, not a checksum, so `cnic_digit_count` could never confirm a value. Supersedes ADR-003.
- [[ADR-005-mrc-otc-relationship-unspecified]] — `mrc + otc == subtotal` was assumed, not specified, and is false for multi-month billing and for contracts with no total. The sub-check is `format_only` until verified against real documents.
- [[ADR-006-two-deployment-profiles]] — `prototype` (RTX 3060 Ti, hosted LLM, public/synthetic documents only) and `production` (L20, all local, real documents). INV-6: a real PTCL document never reaches a hosted API. Scopes [[ADR-001-local-llm]] rather than reversing it.
- [[ADR-007-classification-on-the-document-record]] — `data_classification` is persisted on the document record, set at upload and immutable, not passed per call. Third value renamed `customer` → `restricted`; reclassification is a new document. Amends INV-6's wording in ADR-006.
- [[ADR-008-synthetic-generation-is-a-component]] — Synthetic document generation is a first-class component, not tooling: no public dataset of mixed Urdu/English business documents exists, so it is the only source of training and eval data for the core document type. Versioned and stamped; field schema from FBR SRO 1006(I)/2021.
- [[ADR-009-omission-is-invisible-to-the-gate-layer]] — A field the LLM silently drops looks identical, at every gate, to a field genuinely absent from the document — neither INV-1 nor INV-5 protects recall, only precision. No gate can fix this without inventing a per-document-type field model; W12's eval harness must report per-field recall and an absent-vs-present breakdown to catch it at all.
- [[ADR-010-mrc-otc-require-a-verbatim-field-label]] — A populated `mrc`/`otc` value is only valid if the document itself labels that specific field; a numerically plausible value copied from a differently-labeled line is a violation even when its quoted `source.raw_text` is a real, non-fabricated substring. Names the rule; does not decide an enforcement mechanism — retrying the already-reverted schema-description fix needs a live-fail check first.
- [[ADR-011-terminal-status-requires-positive-verification-evidence]] — `_needs_review`'s `all()` over an empty set of populated fields was vacuously `True`, so an extraction with zero populated fields routed to `complete` with `review.required: false` — indistinguishable from a fully verified document. Fixed to require at least one populated, gate-verified field before `complete` is earned; terminal status must come from positive evidence, not the absence of an unverified field.

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
- **Pipeline version** — the tuple of (profile, OCR versions, model, prompt hash). Stamped on every
  extraction. Two extractions are comparable only if all of it matches — `profile` included, since
  `prototype` and `production` do not run the same LLM.
