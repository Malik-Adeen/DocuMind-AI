---
status: superseded
owner: Adeen
last_reviewed: 2026-08-04
version: 1.1.0
---

# ADR-003 — Deterministic gates are authoritative over model self-reported confidence

**Status:** superseded · **Decided:** date not recorded; extracted from the decision log in [[PROJECT_CONTEXT]] §8 on 2026-08-04
**Supersedes:** —
**Superseded by:** [[ADR-004-format-only-gate-state]] (2026-08-04)

> **Superseded — read [[ADR-004-format-only-gate-state]] first.** The principle below still holds:
> deterministic validators outrank model confidence. What is wrong is the gate list in *Decision*.
> It names `cnic_digit_count` alongside `iban_checksum` as if both could confirm a value. CNIC has
> no check digit — its trailing digit is a gender marker — so that gate can never verify. ADR-004
> replaces the two-state verdict with `passed` / `failed` / `format_only`. The text below is left
> exactly as decided; it is a record, not current guidance.

## Context

The failure mode this product exists to prevent is **confidently wrong numbers reaching a billing
sheet** ([[PROJECT_CONTEXT]] §2). Not slowness — wrongness that looks right.

The obvious control is the model's own confidence score: accept high-confidence fields, flag low
ones. That control does not work here. LLM self-reported confidence is uncalibrated on numeric
and identifier fields — a model will report high confidence on a transposed digit in an IBAN or a
misread MRC as readily as on a correct one. The problem is worse with a local 7B model
([[ADR-001-local-llm]]) and worse again downstream of a two-engine OCR merge that can silently
corrupt text ([[ADR-002-two-stage-ocr]]).

Many of the fields that matter are checkable without a model at all: an IBAN either passes mod-97
or it does not; line items either sum to the subtotal or they do not.

## Decision

**Deterministic validators are authoritative over the LLM** (INV-5). Where a gate exists, its
verdict wins — regardless of what confidence the model reported.

Validation is a **separate pipeline stage** ([[ARCHITECTURE]] §5), ordinary code with no model
involvement:

- `iban_checksum` — mod-97
- `cnic_digit_count` — 13 digits, format check
- `arithmetic_reconciliation` — line items sum to subtotal; subtotal + tax = total; MRC/OTC consistent with terms
- `date_parse` — parses to a real date, and not an absurd one
- `currency_consistency` — one currency per document

Confidence is still recorded per field (INV-2), but it is advisory. `verified: false` and low
confidence are **different signals** and must stay distinguishable end to end — including visually
in the UI ([[API_CONTRACT]] §4).

## Reason

Model confidence is uncalibrated on numbers. A checksum is not. Where a cheap deterministic truth
exists, deferring to a probabilistic estimate instead is choosing the weaker signal.

## Consequences

**Accepted:**

- **A gate failure does not fail the document.** It sets `verified: false` on the affected fields
  and routes to `needs_review`. A blocked document is worse than a flagged one.
- **Silent auto-correction is forbidden.** A gate never repairs a value — that would turn a visible
  problem into an invisible one, which is the exact failure this decision prevents.
- **We prefer flagging a field as unverified over guessing it** ([[PROJECT_CONTEXT]] §2), so more
  documents land in human review than a confidence-threshold design would produce. That is the
  intended trade: recall gates are looser than precision gates in [[EVAL_AND_GOLDEN_SET]] §3
  because a missing field costs 20 seconds and a wrong field costs a wrong invoice.
- **Gate false-pass rate is a hard-fail release gate at 0.00** — a bad value marked `verified` is
  the one outcome with no acceptable rate.
- Gate coverage is now a first-class concern: a field with no gate has no deterministic backstop.
  Each gate needs unit tests in isolation, and integration tests must force a valid-looking but
  checksum-failing value and assert `verified: false`.

**Rejected alternatives:**

- *Confidence thresholding* — accept above a cutoff, review below. Rejected: the cutoff is
  meaningless on uncalibrated scores, and it silently accepts confidently wrong numbers.
- *A second LLM pass as verifier* — correlated errors, no independent ground truth, and it spends
  scarce GPU time to produce another uncalibrated opinion.

## Revisit when

Model confidence becomes demonstrably calibrated against the golden set (see the calibration
metric in [[EVAL_AND_GOLDEN_SET]] §3) — and even then, only to add signal, not to override a gate.
