---
status: active
owner: Adeen
last_reviewed: 2026-08-22
version: 1.1.7
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

- **Adeen — both sides.** OCR pipeline, LLM extraction, validation gates, API, DB, Excel export,
  and the frontend surfaces: upload UI, processing status, review/correction screen, export trigger.
  Single owner as of [[ADR-013-single-owner-for-the-api-contract]] (2026-08-14) — previously split
  with a separate frontend developer; see that ADR for what changed and why.

**The contract between backend and frontend is still [`API_CONTRACT.md`](./API_CONTRACT.md)**, even
with one owner on both sides of it — it is what keeps the mock server, the real API, and the frontend
client from drifting apart. Change = update the file and bump its version, in the same commit as the
code. There is no separate agreement step; see [[ADR-013-single-owner-for-the-api-contract]] for why
that gate was retired rather than left in place unable to fire.

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
- [x] **Multi-page documents: one extraction per file, or per logical document?** One extraction per
      file — every page is OCR'd and its text fed into a single LLM call, not one call per page
      merged afterward, and not filtered down to a "relevant" subset. See
      [[ADR-016-multi-page-pdfs-are-one-extraction-not-a-merge]].
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

### Known gaps — recorded, not fixed

- [ ] **`/status.error` is `null` for most failure causes, still.** Narrowed 2026-08-14, not
      resolved: `documents.error` is now populated for two causes — `HostedEndpointRefusedError`
      (INV-6 refusing a restricted document at extraction) and the unclassified-exception catch-all
      in `extract_document` — both via `app/core/errors.py`'s `envelope()`, `code`/`message`/
      `trace_id`/`retryable` only, no document content (ADR-006's constraint on `HostedEndpointRefusedError`'s
      own message already guaranteed this; the catch-all uses a fixed generic message rather than
      `str(exc)` for the same reason). A PaddleOCR crash, an LLM schema-validation failure, and a
      gate-coverage failure (`OCRFailedError` / `ExtractionFailedError` / `GateCoverageError`, all
      `OrchestratorError` subclasses) still leave `error: null` — only their `stage` reaches the log,
      not the API. Closing that is unstarted.
- [ ] **Two of eight gates are unbuildable as designed.** The gate registry names
      `ntn_format_check` and `strn_format_check`, but [[EXTRACTION_SCHEMA.json]]'s `fields` block
      has no `ntn`/`strn` field for either to check against. First found 2026-08-10 ([[JOURNAL]]),
      still unfixed.
- [ ] **A malformed money value can orphan its well-formed siblings and hard-kill the whole
      document, not just itself.** Found 2026-08-18 while live-testing [[ADR-015-truncated-llm-output-is-salvaged-not-repaired]]
      (1 of 6 real uploads of the same document, unrelated to truncation — `document b45b59f6`,
      `INV-1: money field(s) tax reached persistence with no gate verdict attached`). Root cause in
      `app/pipeline/gates/arithmetic.py`: `_check_totals()` and `_check_mrc_otc()` each parse their
      2–3 money fields **sequentially inside one shared `try` block**
      (`subtotal = _money(...); tax = _money(...); total = _money(...)`, similarly `mrc`/`otc`). If
      the Nth field raises `_MalformedAmountError`, the function returns immediately naming only
      that field — every field parsed *before* N (already successfully parsed) and every field
      *after* N (never reached) gets no `GateResult` from this function at all. If no other gate
      independently names them, `_assert_money_fields_gated`'s INV-1 check correctly (by its own
      logic) sees a present, valued, ungated money field and raises `GateCoverageError` — the whole
      document fails, not just the malformed field. Confirmed by direct reproduction: a malformed
      `subtotal` orphans `tax` and `total`; a malformed `tax` orphans `total`; `mrc`/`otc` orphan
      each other the same way. `subtotal` alone is structurally immune — `_check_line_items` parses
      it independently and redundantly names it either way. No precise production rate measured (no
      metric currently tracks `GateCoverageError` frequency); structurally it fires whenever the
      model emits one non-`-?[0-9]+\.[0-9]{2}` money string ahead of a well-formed sibling in parse
      order, which real hosted-model output on this document family has already been observed doing
      (`"%5"` for a GST rate, digit-duplication misreads — see the deskew-task provenance report).
      **This is a false positive of a structurally-correct assertion, not a case for loosening
      INV-1** — `_assert_money_fields_gated` should stay a hard failure (same structural-fact-vs-
      fallible-judgment distinction [[ADR-012-provenance-merge-was-dead-code]] already draws for why
      *its* check gets a hard raise and provenance-matching doesn't); the fix belongs in
      `_check_totals`/`_check_mrc_otc` evaluating each field's parse independently so one malformed
      value can no longer suppress a verdict on fields that are perfectly checkable on their own.
      Out of scope for `fix/llm-truncation-detection` (different module, different root cause);
      filed here rather than fixed inline.
- [ ] **[[ADR-009-omission-is-invisible-to-the-gate-layer]] needs amending — its claim isn't true
      for every gate.** ADR-009 holds that no gate should be expected to catch field omission. The
      2026-08-10 real-path run ([[JOURNAL]]) showed `line_item_sum` doing exactly that: the model
      dropped a line item from `line_items` entirely, and the gate failed on the resulting
      arithmetic mismatch. Omission is invisible to the gate layer only when the omitted value
      doesn't participate in an arithmetic identity another gate checks — ADR-009's claim needs
      narrowing, not reversing.

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
- [[ADR-012-provenance-merge-was-dead-code]] — INV-2 shipped unenforced since ADR-002: `TextRegion.as_source()` was dead code, so every real extraction carried no `source.page`/`source.bbox`. Fixed with a provenance-merge stage that matches a field's claimed `raw_text` back to its OCR region; an unmatched claim is logged and forces `needs_review`, it does not fail the extraction — the match itself is a fallible check and must not be authoritative, same logic as `format_only` (ADR-004). First real-run evidence: 277/283 (97.9%) claimed quotes resolved across 3 synthetic invoices.
- [[ADR-013-single-owner-for-the-api-contract]] — `API_CONTRACT.md`'s co-ownership gate (§4) is retired: the frontend/backend split ended and Adeen owns both sides. The "not agreed" banner covering 0.2.0/0.3.0 is removed, not backfilled as reviewed — the gate is gone because the role it depended on no longer exists, not because a second reading happened.
- [[ADR-014-hosted-processing-exception-for-two-named-documents]] — Two real PTCL documents (`Azeem.jpeg`, `Azeem.pdf`) are uploaded as `data_classification: public` for a one-off hosted-profile test, under verbal authorization. Per-document exception only, not a category or a precedent — INV-6's guard, default-deny behaviour, and code are all unchanged.
- [[ADR-015-truncated-llm-output-is-salvaged-not-repaired]] — A response cut off by `max_tokens` (measured 1340–3201 natural tokens on a dense document against a 2000 ceiling, ~45% failure rate) is detected via `finish_reason`, never retried through the repair-prompt loop, and salvaged field-by-field against `EXTRACTION_SCHEMA.json` — forced to `needs_review`, never promoted to `complete`, and only failed outright if nothing survives. Same fallible-check-must-not-be-authoritative reasoning as [[ADR-012-provenance-merge-was-dead-code]]. `hosted_llm_max_tokens` now a measured `Settings` default (4000), not a hardcoded literal.
- [[ADR-016-multi-page-pdfs-are-one-extraction-not-a-merge]] — Every page of a multi-page PDF is now OCR'd (previously page 1 only, silently) and fed into a single LLM call, not one call per page merged afterward and not a page-relevance filter. No new field-conflict/arbitration mechanism was built — the single-call design produces no per-page candidates to arbitrate; `check_arithmetic` remains the only backstop, unchanged. New fail-loud `DocumentTooLargeError`/`DOCUMENT_TOO_LARGE` fires before OCR (`max_pdf_pages`, default 50) or before the LLM call (`hosted_llm_max_input_tokens`, default 20000, an unmeasured engineering estimate — revisit once the deployed context window is confirmed).
- [[ADR-017-unrecognized-document-type-is-coerced-not-discarded]] — An LLM-classified `document_type.value` outside the closed enum (e.g. `"addendum"`, seen on a real 12-page addendum) no longer discards the whole extraction. Coerced to `"unknown"` server-side — already the DB default, already enum-valid, zero schema change — with the model's original string surfaced via `review.reason: "document_type_unrecognized:<value>"`, forcing `needs_review` the same way truncation does. Concatenates with the truncation cause via `;` (truncation first) rather than either clobbering the other. Widening the enum to accept the value outright was rejected — deliberately left as a separate, undecided question.

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
