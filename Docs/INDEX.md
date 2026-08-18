---
status: active
owner: Adeen
last_reviewed: 2026-08-18
version: 1.2.3
---

# INDEX.md — map of content

Every document in this vault, what question it answers, who owns it, and when to open it.
**Start at [[PROJECT_CONTEXT]].** Everything else assumes you have read it.

Frontmatter on each file carries `status`, `owner`, `last_reviewed`, `version`. If
`last_reviewed` is old and the code has moved, the doc is a suspect — check it before trusting it.

---

## Core

| Doc | Answers | Owner | Read it when |
|---|---|---|---|
| [[PROJECT_CONTEXT]] | What is this, why does it exist, what stack is real, what is out of scope, what must never break | Adeen | **First, every session.** Before any code, and again whenever scope or stack feels ambiguous |
| [[AGENT_RULES]] | How to change this repo — docs-in-the-same-commit, the trigger table (§2) mapping a code change to the doc it obliges, session protocol, evidence rule | Adeen | Second, every session. Before your first commit, and again before you claim anything is done |
| [[ARCHITECTURE]] | How the system is actually built — components, the seven pipeline stages, failure modes, known weaknesses | Adeen | Before touching the pipeline, the queue, the data model, or anything that changes where work happens |
| [[API_CONTRACT]] | The exact frontend/backend boundary — endpoints, statuses, error envelope, mock server | Adeen | Before writing or calling any endpoint. Update the file and bump its version in the same commit — no separate agreement step ([[ADR-013-single-owner-for-the-api-contract]]) |
| [[EXTRACTION_SCHEMA.json]] | The one shape an extraction result ever takes — source of truth for LLM output, DB rows, API responses, Excel columns | Adeen | Before changing any field. Changing it changes four things at once |
| [[EVAL_AND_GOLDEN_SET]] | How we know it works — golden set rules, per-field metrics, release gates, test layers | Adeen | Before quoting any accuracy number, before a release, and when adding tests |
| [[DATASETS]] | Every corpus we might train on or measure against, what each is actually worth, and the defects that are invisible from their documentation | Adeen | **Before quoting a number off any corpus**, before adopting a generator, and before assuming a published benchmark means what it says |
| [[JOURNAL]] | What has actually happened, session by session — append-only, newest first | Adeen | At the end of every session to append, and at the start when you need to know what the last one left half-done |

## Decisions

Append-only. Reasoning lives here so it does not have to be re-derived or re-argued. Reversing a
decision means a new ADR that supersedes the old one — never an edit to a decided one.
Summary list in [[PROJECT_CONTEXT]] §8.

| ADR | Answers | Owner | Read it when |
|---|---|---|---|
| [[ADR-001-local-llm]] | Why a local Qwen2.5-7B rather than a hosted GPT/Claude API | Adeen | Considering an external model call, or wondering why extraction quality is capped |
| [[ADR-002-two-stage-ocr]] | Why two OCR engines (PaddleOCR + Qaari) and what the merge costs | Adeen | Touching OCR, script detection, bounding boxes, or chasing corrupted text |
| [[ADR-003-deterministic-gates]] | Why validators outrank model confidence, and why gates never auto-correct — **superseded by ADR-004**, kept as record | Adeen | Only for history. Read ADR-004 instead |
| [[ADR-004-format-only-gate-state]] | Why gate results are three-state, and why a format check (CNIC/NTN/STRN) can never set `verified: true` | Adeen | Writing any validator, deciding what `passed` is allowed to mean, or rendering gate results in the UI |
| [[ADR-005-mrc-otc-relationship-unspecified]] | Why the MRC/OTC-to-total check asserts nothing, and why an unspecified rule inside a verifying gate is worse than no rule | Adeen | Tempted to infer a business rule from field names, or before writing any MRC/OTC validation |
| [[ADR-006-two-deployment-profiles]] | Why there are two profiles, what runs where on 8 GB vs 48 GB, and why INV-6 forbids a real document ever reaching a hosted API — **INV-6 wording amended by ADR-007** | Adeen | **Before running the pipeline on any real document**, before changing the LLM endpoint, and before quoting a prototype accuracy number |
| [[ADR-007-classification-on-the-document-record]] | Why `data_classification` lives on the document record rather than in a call argument, why it is immutable, why reclassification is a new document, and why the third value is `restricted` rather than `customer` | Adeen | Before touching the INV-6 guard, the upload endpoint, or the `documents` table — and any time an invariant looks like it depends on callers behaving |
| [[ADR-008-synthetic-generation-is-a-component]] | Why synthetic document generation is a first-class component rather than tooling, why no public dataset makes it optional, and why the generator gets a version stamp | Adeen | Before building or changing the generator, and before treating any synthetic corpus as regenerable on a whim |
| [[ADR-009-omission-is-invisible-to-the-gate-layer]] | Why a silently dropped field looks identical to a genuinely absent one at every gate, and why the fix is the eval harness's recall metric, not a new gate | Adeen | Before assuming a clean `gates` array means nothing is missing, and before writing W12's `run_eval.py`/`scorers.py` |
| [[ADR-010-mrc-otc-require-a-verbatim-field-label]] | Why a verbatim-real `source.raw_text` quote isn't enough for `mrc`/`otc` — it must also verbatim-label that specific field, not a differently-labeled line copied over | Adeen | Before trusting `source.raw_text` as proof of a correct `mrc`/`otc` value, and before retrying the reverted `EXTRACTION_SCHEMA.json` description fix |
| [[ADR-011-terminal-status-requires-positive-verification-evidence]] | Why an extraction with zero populated fields was routing to `complete` — `all()` over an empty set is vacuously true — and why terminal status must be earned by positive verification, not the absence of an unverified field | Adeen | Before touching `_needs_review` or any other routing decision shaped like "no problems found"; before trusting `complete` without checking `fields` is non-empty |
| [[ADR-013-single-owner-for-the-api-contract]] | Why `API_CONTRACT.md`'s co-ownership gate is retired and the "not agreed" banner removed — the frontend/backend split ended, not a second review that happened after the fact | Adeen | Before citing the old "both owners agree" rule anywhere, and before assuming an API contract change needs anyone else's sign-off |
| [[ADR-014-hosted-processing-exception-for-two-named-documents]] | Why `Azeem.jpeg` and `Azeem.pdf` are uploaded `public` for a hosted-profile test under verbal authorization, why this is per-document and not a precedent, and why INV-6 itself is untouched | Adeen | Before treating this ADR as license to classify any other real document `public`, and before citing it as a general exception rather than a two-document one |
| [[ADR-015-truncated-llm-output-is-salvaged-not-repaired]] | Why a `max_tokens`-truncated LLM response is detected via `finish_reason`, salvaged field-by-field instead of retried through the repair prompt, and forced to `needs_review` rather than `failed` or `complete` — and why `hosted_llm_max_tokens` is now a measured `Settings` default, not a hardcoded literal | Adeen | Before touching `HostedChatTransport`, `complete_with_repair`, or the truncation/salvage path in `orchestrator.py`; before assuming any `document.error` implies `status: "failed"` |

## Code

| Location | Answers | Owner | Read it when |
|---|---|---|---|
| [`../CodeBase/CLAUDE.md`](../CodeBase/CLAUDE.md) | The working rule for code: required reading, and docs update in the same commit as the change | Adeen | Before the first commit in `CodeBase/` |
| [`../CodeBase/backend/CLAUDE.md`](../CodeBase/backend/CLAUDE.md) | Backend implementation rules — layering, gates, money, Celery, prompts, pre-push checks | Adeen | Before writing backend code |
| [`../.claude/`](../.claude/) | Shared Claude Code workspace config: permission allowlist (`settings.json`) and five slash commands — `/gate`, `/adr`, `/journal`, `/contract-change`, `/eval` (`commands/`) | Adeen | When a permission prompt is noisy, or before adding a command |

---

## The rule that keeps this map true

Docs and code are one repository. **Any change that contradicts a document updates that document
in the same commit.** A commit that changes described behaviour and leaves these files untouched
is incomplete — stale context is worse than no context.

When you add a document here, add its row above. An unlisted doc is a doc nobody reads.
