---
status: active
owner: Adeen
last_reviewed: 2026-08-04
version: 1.0.0
---

# AGENT_RULES.md — how to change this repository

Applies to everyone who commits here: backend, frontend, human, or AI assistant. These are the
cross-cutting rules. Area-specific rules live elsewhere and are listed in §5 — this file does not
restate them.

Read [[PROJECT_CONTEXT]] first. This file tells you how to work; that one tells you what the
system is.

---

## 1. The rule

**Docs and code are one repository. Any change that contradicts a document updates that document
in the same commit.**

A commit that changes described behaviour and leaves the relevant doc untouched is an incomplete
commit — not a follow-up task, not a TODO. Stale context is worse than no context, because it is
trusted.

If you discover a doc is *already* wrong before you start, fix it first, in its own commit, so the
correction is not buried inside a feature change.

---

## 2. Trigger table

Find the row your change touches. Update the listed document in the same commit.

| If your change touches | Update | Extra gate |
|---|---|---|
| `backend/app/pipeline/**` — stages, orchestration, OCR, LLM call | [[ARCHITECTURE]] §2 (component map) and the affected stage section | — |
| `backend/app/pipeline/gates/**` — any validator | [[ARCHITECTURE]] §5 (the gate list) | Reversing gate philosophy needs a new ADR superseding [[ADR-003-deterministic-gates]] |
| `backend/app/api/**` — any endpoint, status, or error code | [[API_CONTRACT]] **and bump its version** | **Both owners agree first.** Tell the frontend dev — the contract is co-owned |
| `backend/app/schemas/**` or any extracted field | [[EXTRACTION_SCHEMA.json]] | Changing it changes four things: LLM output, DB row, API response, Excel columns. Check all four. `prompt_builder.py:24` injects `EXTRACTION_SCHEMA.json` into the prompt at runtime via `model_output_schema()` — a `description` edit is a prompt change, not a docs-only change, and requires a live N≥20 check before landing ([[ADR-010-mrc-otc-require-a-verbatim-field-label]]) |
| `backend/app/export/**` — column order or format | [[EXTRACTION_SCHEMA.json]] (column order derives from field order) | — |
| `backend/app/db/**` — models or migrations | [[ARCHITECTURE]] §6 (data model) | Extraction and correction tables are append-only (INV-4). No `UPDATE` |
| `backend/evals/**` — harness, metrics, golden set rules | [[EVAL_AND_GOLDEN_SET]] | No accuracy number is quotable unless it came from this harness |
| Dependencies, models, or infrastructure | [[PROJECT_CONTEXT]] §3 (real stack) | If it is in the "explicitly NOT in scope" list, it needs a decision first, not a commit |
| An invariant INV-1 … INV-5 | [[PROJECT_CONTEXT]] §6 | An invariant does not change quietly. New ADR, or it did not happen |
| Reversing any past decision | New ADR in [`decisions/`](./decisions/), linked from [[PROJECT_CONTEXT]] §8 | Never edit a decided ADR's reasoning. Supersede it |
| **Any session that changed anything** | [[JOURNAL]] — one entry, newest first | — |

If your change fits no row, it is probably a refactor with no behavioural change. Say so in the
commit message rather than skipping the check silently.

---

## 3. Session protocol

**Open** by stating in one line: which invariant your change touches, and which file in `Docs/`
you will update.

**Close** by quoting the decisive command output, and by appending a [[JOURNAL]] entry.

---

## 4. Evidence, not summary

**Do not report a task complete based on your own description of it.** Quote the output of the
command that proves it — the test summary line, the `git check-ignore` result, the eval table.

A self-authored summary is not evidence. "It should work now" and "tests pass" are the same
sentence unless one of them is followed by the output.

This applies hardest to accuracy claims: see [[EVAL_AND_GOLDEN_SET]] §1.

---

## 5. Where the area rules live

This file is the shared layer. It is deliberately short. Do not copy area rules into it — a rule
in two places is a rule that will disagree with itself.

| Scope | File |
|---|---|
| Working in `CodeBase/` at all | [`../CodeBase/CLAUDE.md`](../CodeBase/CLAUDE.md) |
| Backend implementation rules — layering, gates, money, Celery, prompts | [`../CodeBase/backend/CLAUDE.md`](../CodeBase/backend/CLAUDE.md) |
| Frontend | owned by the frontend dev; not specified here |
| The map of every document | [[INDEX]] |
