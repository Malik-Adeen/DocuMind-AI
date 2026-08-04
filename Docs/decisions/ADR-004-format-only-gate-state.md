---
status: accepted
owner: Adeen
last_reviewed: 2026-08-04
version: 1.0.0
---

# ADR-004 — Gate results are three-state; a format check can never verify

**Status:** accepted · **Decided:** 2026-08-04
**Supersedes:** [[ADR-003-deterministic-gates]]

## Context

[[ADR-003-deterministic-gates]] established the right principle — deterministic validators outrank
model confidence (INV-5) — and then undermined it in its own gate list. It named
`cnic_digit_count` in the same flat list as `iban_checksum`, as though the two produced the same
kind of answer. They do not.

**A CNIC has no check digit.** It is 13 digits: a 5-digit district and area code, a 7-digit serial,
and a trailing digit that encodes gender — odd for male, even for female. That last digit is not
derived from the preceding twelve and constrains nothing about them. Transpose two digits in the
serial and the result is another perfectly well-formed CNIC. NTN and STRN carry no checksum either.

So `cnic_digit_count` could only ever answer *"could this be a CNIC?"* — never *"is this the right
CNIC?"*. `iban_checksum` answers the second question, because mod-97 fails on a transposed digit.

[[EXTRACTION_SCHEMA.json]] then recorded every gate outcome as a boolean `passed`. A format match
and a verified checksum serialised identically. A CNIC misread by OCR would have arrived at the
Excel export carrying `verified: true` — the precise failure this system exists to prevent
([[PROJECT_CONTEXT]] §2), produced by the mechanism built to prevent it.

## Decision

**A gate returns three states, not two:** `passed`, `failed`, `format_only`.

**Only a gate that can falsify a well-formed value may return `passed`.**

| Gate | May return `passed`? |
|---|---|
| `iban_checksum` — mod-97 | Yes |
| `arithmetic_reconciliation` | Yes |
| `date_parse` | Yes |
| `line_item_sum` | Yes |
| `currency_consistency` | Yes |
| `cnic_format_check` (was `cnic_digit_count`) | **No** — `format_only` or `failed` |
| `ntn_format_check` | **No** — `format_only` or `failed` |
| `strn_format_check` | **No** — `format_only` or `failed` |

**`format_only` can never set `verified: true`.** A field whose only gate is a format check reaches
the reviewer unverified, always, no matter how clean the value looks or how confident the model was.

**An absent field returns `format_only`, not `failed`.** A document with no IBAN is not a document
with a broken IBAN.

**Everything else in [[ADR-003-deterministic-gates]] is retained unchanged:** gates are
authoritative over model confidence (INV-5), a gate failure routes to `needs_review` rather than
failing the document, silent auto-correction stays forbidden, and gate false-pass rate remains a
hard-fail release gate at 0.00. This ADR narrows what "pass" is allowed to mean; it does not
reverse the principle.

## Reason

A boolean cannot hold the distinction between *well-formed* and *correct*, and that distinction is
the entire value of the validation stage. Collapsing it puts the weaker claim and the stronger
claim in the same field, at exactly the point where a number is about to reach a billing sheet.

The correct place for the safety property is the result itself, so that any code path that wants to
set `verified: true` has to look at a value that says `format_only` and decide to ignore it.

## Consequences

**Accepted:**

- **CNIC, NTN and STRN always reach human review unverified.** Review load is higher than a
  boolean design would produce. That is the intended trade, and the same one
  [[PROJECT_CONTEXT]] §2 already makes: flagging beats guessing.
- **Breaking schema change.** `gates[].passed` (boolean) is replaced by `gates[].result` (enum).
  [[EXTRACTION_SCHEMA.json]] 0.1.0 → 0.2.0, [[API_CONTRACT]] → 0.2.0. The frontend must render three
  states, and `format_only` must not look like a pass. Co-owned change — the frontend owner has to
  agree before the review screen is built against it.
- **Format-only gates need three unit tests, not two:** well-formed → `format_only`, malformed →
  `failed`, and an assertion that neither path ever sets `verified: true`. A format gate tested only
  for pass/fail is the bug it is supposed to catch ([[EVAL_AND_GOLDEN_SET]] §4).
- Any future gate must declare which side of this line it falls on before it ships. "Format check"
  is not a lesser gate; it is a different claim.

**Rejected alternatives:**

- *Keep boolean `passed`, add a `can_verify` flag to the gate definition.* Rejected: it puts the
  safety property in a lookup table away from the value being judged, so the one place that must
  never get it wrong depends on a join that is easy to omit.
- *Treat a CNIC as verified when it matches a known customer record.* Rejected: that is a database
  lookup, not a deterministic gate. It puts I/O into a pure stage ([[ARCHITECTURE]] §5) and swaps a
  checksum failure for a stale-data failure.
- *Drop the CNIC gate entirely, since it cannot verify.* Rejected: a malformed CNIC is still worth
  catching. `failed` remains meaningful even when `passed` is unreachable.

## Revisit when

NADRA publishes a checksum or verification scheme for the CNIC, or a verification API becomes
available *and* in scope ([[PROJECT_CONTEXT]] §3 currently excludes external calls). Either would
turn `cnic_format_check` into a genuinely verifying gate — and would need a new ADR, because it
would also mean accepting an external dependency in the validation stage.
