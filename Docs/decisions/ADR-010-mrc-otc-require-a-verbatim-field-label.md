---
status: accepted
owner: Adeen
last_reviewed: 2026-08-10
version: 1.0.0
---

# ADR-010 — `mrc`/`otc` require a verbatim field label in the source text, not just a plausible number

**Status:** accepted · **Decided:** 2026-08-10
**Supersedes:** — · **Related:** [[ADR-005-mrc-otc-relationship-unspecified]], [[ADR-009-omission-is-invisible-to-the-gate-layer]], [[JOURNAL]] 2026-08-08 (both entries)

## Context

`JOURNAL.md`'s 2026-08-08 entries record `invoice_1_simple.txt` — a one-time equipment invoice with
no MRC/OTC billing at all — hallucinating both fields: the pre-fix baseline copied `subtotal` into
`mrc` and `tax` into `otc`, reusing the same `source.raw_text` for both. Two candidate fixes were
tried live and compared: (a) a few-shot example plus an explicit "don't infer from a nearby field"
rule added to `extract_v1.txt`, and (b) `description` fields added to `mrc`/`otc` in
`Docs/EXTRACTION_SCHEMA.json`. (a) fixed the target defect with no regressions. (b) caused invoice 1
to fail outright on two of three attempts — the model nested `line_items` inside `fields`, which
`additionalProperties: false` correctly rejects, and repeated the mistake on the repair retry both
times. (a) was kept; (b) was reverted. Confirmed in this session: the current schema still carries a
bare `$ref: money_field` for both, no description.

This session re-ran the same fixture under the current, fix-(a) prompt — `evals/repro.py`, N=20,
several times, pinned and unpinned to different OpenRouter providers (`Phala`, `Together`). The
hallucination is reduced but not eliminated: the Phala-pinned N=20 run (`seed=0`,
`evals/history/invoice_1_simple_phala-pinned_20260810T054014Z.jsonl`) shows `otc` populated with
`"5000.00"` in 15/20 reps and correctly `null` in 5/20. Every one of those 15 populated reps carries
the identical `source.raw_text`:

```
Installation Charges         1      5000.00      5000.00
```

That string is a **real, verbatim substring** of `invoice_1_simple.txt` — it is not a fabricated
quote. But the invoice has no field anywhere labeled `OTC`, `One-Time Charge`, or any recurring/
one-time billing term at all (confirmed by printing the fixture's full raw text this session). The
model is quoting a genuine `Installation Charges` line-item row and attaching it to `otc` — the
grounding is honest, the field association is invented. `mrc` stayed correctly `null` in all 20 reps
of that same run, so the surviving defect is asymmetric between the two fields the prompt rule names
together.

This is the same failure shape named four times already in this repository (`cnic_digit_count`, the
boolean `gates[].passed`, the invented `mrc + otc == subtotal` identity, and now this): a claim about
*shape* — "this text exists verbatim in the document" — standing in for a claim about *truth* —
"this text is what the document calls `otc`." [[ADR-009-omission-is-invisible-to-the-gate-layer]]
already named the adjacent gap and left it undecided: "`source.raw_text` is currently trusted verbatim
from the model and never cross-checked against the actual OCR text server-side... a related but
separate gap, left for a future ADR if pursued." This ADR is that follow-up, scoped to `mrc`/`otc`
specifically, not a general `source.raw_text` verification mechanism.

## Decision

**A populated `mrc` or `otc` value is valid only if the document contains text that itself labels
that specific field** — `MRC`, `Monthly Recurring Charge`, `OTC`, `One-Time Charge`, `Installation
Fee` billed as a *recurring/one-time charge line* (not a generic line item), or a clear local-language
equivalent. A numerically plausible value copied from a differently-labeled line — a line item, the
subtotal, the tax, the total — does not satisfy this rule, regardless of whether the quoted
`source.raw_text` is a genuine, non-fabricated substring of the document. Verbatim-in-the-document and
verbatim-as-this-field are two different claims, and only the second one makes a value correct.

This ADR names the rule as a project decision so it can be scored against. **It does not decide a new
enforcement mechanism.** In particular:

- It does **not** direct that `Docs/EXTRACTION_SCHEMA.json` gain `mrc`/`otc` descriptions. That is
  candidate (b) above, already tried and reverted for a ~2-in-3 hard-failure rate on this exact
  fixture. Retrying it is not ruled out, but any future attempt must be live-tested against invoice 1
  for the nesting failure before it lands — the prior failure mode has never been re-verified as fixed
  under the current prompt, and assuming it's fine now would repeat the mistake this project has
  already made of trusting an untested assumption. Concretely: `prompt_builder.py:24`
  (`schema_json = json.dumps(model_output_schema(), indent=2)`) injects the live
  `EXTRACTION_SCHEMA.json` into the prompt at runtime — a `description` edit there is not a docs-only
  change, it is a prompt change by another name, and it needs the same live N≥20 check any prompt
  change would need before landing, not a lighter one just because the diff lands in a JSON file
  instead of `extract_v1.txt`.
- It does **not** decide a deterministic grounding check (e.g., a gate or orchestrator step that
  cross-references `source.raw_text` against the actual OCR text and rejects an association it can't
  support). [[ADR-009-omission-is-invisible-to-the-gate-layer]] named that direction without deciding
  it; this ADR doesn't decide it either. A same-string-different-label check for `mrc`/`otc`
  specifically would be narrower and might be worth building before the general case, but that's a
  future ADR, not this one.
- The current enforcement remains what it already is: the prompt rule in `extract_v1.txt` (fix (a)).
  This ADR records that it is incomplete, not that it should be replaced.

## Reason

The project exists to stop a confidently wrong number reaching a billing sheet
([[PROJECT_CONTEXT]] §2). A hallucinated `otc` grounded in a real OCR substring is more dangerous than
one grounded in nothing, because a reviewer skimming `source.raw_text` and seeing an exact quote from
the document has every reason to trust it — the quote is real, the field it's attached to is not.
Naming the rule precisely (verbatim label, not verbatim substring) is what makes that distinction
checkable at all, in eval reporting now and in any future gate or schema work later. Leaving the
mechanism undecided is deliberate, matching [[ADR-009-omission-is-invisible-to-the-gate-layer]]'s own
pattern: naming a gap honestly is not the same claim as knowing how to close it, and the one concrete
mechanism tried so far for a related fix already produced a worse failure than the one it fixed.

## Consequences

**Accepted:**

- The residual `otc` hallucination under fix (a) — 15/20 on the most recent pinned run — is now a
  named, scoreable violation of a stated rule, not an unlabeled inconsistency. Future eval runs against
  this fixture can report a "verbatim-label violation rate" for `mrc`/`otc` distinct from raw
  null-vs-value counts.
- No prompt, schema, or gate change lands from this ADR. `extract_v1.txt` is unchanged; the fix-(a)
  rule it already carries is the only enforcement that exists today, and it is known, now explicitly,
  to be incomplete for `otc` on this fixture.
- The asymmetry between `mrc` (0/20 hallucinated in the most recent run) and `otc` (15/20) is recorded
  as observed, not explained — the prompt rule names both fields together and only one still fails at
  this rate on this document. Worth investigating before any future prompt change, not assumed to have
  the same cause.

**Rejected alternatives:**

- *Add `mrc`/`otc` descriptions to `EXTRACTION_SCHEMA.json` now, in this ADR.* Rejected: this is
  candidate (b), already tried and reverted for a documented ~2-in-3 hard-failure rate on this exact
  fixture. Retrying it without a live-fail check first would be choosing not to learn from a specific,
  already-recorded failure.
- *Decide a deterministic `source.raw_text`-vs-OCR-text cross-check gate in this ADR.*
  [[ADR-009-omission-is-invisible-to-the-gate-layer]] already declined to decide the general version of
  this for the same reason it would apply here: it needs real design work (what counts as a matching
  label, how close is "close enough," multilingual labels) that has not been done, and deciding it
  under pressure from one fixture's result would risk the same shape-as-truth mistake this repository
  keeps finding in gates.

## Revisit when

Either (1) someone retries the `EXTRACTION_SCHEMA.json` description approach — it must be live-tested
against `invoice_1_simple.txt` for the nesting failure before landing, and that test's result belongs
in this ADR's revision or a superseding one — or (2) W12's eval harness exists and can report a
verbatim-label violation rate across the full golden set rather than one hand-run fixture, which is
the point at which the asymmetry between `mrc` and `otc` noted above becomes a statistically
meaningful finding rather than a single run's observation.
