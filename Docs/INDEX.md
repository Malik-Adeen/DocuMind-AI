---
status: active
owner: Adeen
last_reviewed: 2026-08-04
version: 1.1.0
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
| [[API_CONTRACT]] | The exact frontend/backend boundary — endpoints, statuses, error envelope, mock server | Adeen & Frontend | Before writing or calling any endpoint. Both owners agree before it changes |
| [[EXTRACTION_SCHEMA.json]] | The one shape an extraction result ever takes — source of truth for LLM output, DB rows, API responses, Excel columns | Adeen | Before changing any field. Changing it changes four things at once |
| [[EVAL_AND_GOLDEN_SET]] | How we know it works — golden set rules, per-field metrics, release gates, test layers | Adeen | Before quoting any accuracy number, before a release, and when adding tests |
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
