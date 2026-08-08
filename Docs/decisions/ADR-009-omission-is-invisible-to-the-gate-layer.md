---
status: accepted
owner: Adeen
last_reviewed: 2026-08-08
version: 1.0.0
---

# ADR-009 — Field omission is invisible to the gate layer; the eval harness, not a gate, has to catch it

**Status:** accepted · **Decided:** 2026-08-08
**Supersedes:** — · **Related:** [[ADR-004-format-only-gate-state]], [[ADR-005-mrc-otc-relationship-unspecified]], [[EVAL_AND_GOLDEN_SET]]

## Context

The first live run against a real hosted LLM ([[JOURNAL]] 2026-08-08) surfaced a concrete case of a
gap that was always there in the design but had never been exercised against real model output.

`invoice_3_dense_layout.txt`, one of the three hand-authored synthetic invoices, states an IBAN —
deliberately given a wrong checksum digit, specifically to exercise `iban_checksum`'s `failed` path
live. Across three independent runs against `qwen/qwen-2.5-7b-instruct` (the original baseline and
two further runs at `temperature=0`, one of which additionally hit a different failure and had to
retry), the model **never once extracted the `iban` field at all** — not misread, not marked low
confidence, simply absent from `fields` every time.

Because the field never reached the gate, `iban_checksum` correctly did what it is designed to do
with an absent field: it returned `format_only` — *"iban field absent; no value to check"* — which is
exactly the same result it would return for a document that genuinely has no IBAN. Nothing in the
`gates` array, the field payload, or the `needs_review` routing decision distinguishes those two
cases. The document this ADR is about looked, in every machine-readable respect, identical to one
where the model correctly recognised there was nothing to extract.

This is not a bug in `check_iban`, or in any gate. Every gate in `pipeline/gates/` treats "field
absent" the same way, on purpose — [[ADR-004-format-only-gate-state]] establishes that a document
with no IBAN is not a document with a broken one, and that absence must return `format_only`, not
`failed`. That rule is correct for the case it was written for: a field genuinely not on the page.
It was never designed to — and structurally cannot — distinguish that from a field that **was** on
the page and the model silently dropped. Both arrive at the gate as the same shape: missing.

INV-1 and INV-5 both protect **precision** — they exist to stop a wrong value from being marked
`verified: true`. Neither protects **recall**. A document could lose every field the model felt
uncertain about and still pass every gate cleanly, contributing nothing but ordinary,
indistinguishable `format_only` results — the same shape a genuinely sparse document produces.
[[EVAL_AND_GOLDEN_SET]] §3 already specifies recall and a hallucination-rate metric, and §2 already
requires the golden-label format to distinguish `null` (field genuinely absent from the document)
from `"__illegible__"` (present but unreadable) — the *convention* needed to catch this already
exists. But `run_eval.py` and `scorers.py` do not exist yet ([[EVAL_AND_GOLDEN_SET]] §5, W12 in the
prototype roadmap), so on the prototype today, an omission like this one is invisible everywhere:
not caught by a gate (by design), and not caught by an eval harness (because none runs).

## Decision

**Field omission is a distinct failure mode from field misextraction, and no gate should be expected
to close this gap.** A gate checks the shape and arithmetic validity of what is present; whether
something that should be present is missing is a different question, answerable only against ground
truth — which is eval's job, not a deterministic validator's.

1. **W12's eval harness (`run_eval.py` / `scorers.py`) must report per-field recall and an
   absent-vs-present breakdown, not precision alone**, fulfilling what [[EVAL_AND_GOLDEN_SET]] §3
   already specifies but nothing yet implements. Concretely, for every field on every golden
   document, the harness must be able to tell apart:
   - present in the document, extracted, correct;
   - present in the document, extracted, wrong;
   - **present in the document, never extracted — a recall miss, this ADR's case**;
   - genuinely absent from the document, correctly not extracted.

   The golden-label format already carries what's needed to make this distinction (`null` vs a real
   value, per §2) — W12 has to use it, not just compute precision over predicted-non-null fields as
   the spec's precision definition alone would allow.
2. **This ADR does not decide a run-time detection mechanism** for omission before a golden label
   exists (i.e. outside the eval harness, on a real document with no ground truth to compare
   against). One direction worth naming without deciding: `source.raw_text` is currently trusted
   verbatim from the model and never cross-checked against the actual OCR text server-side, so a
   model can claim a quote that was never in the document and nothing catches that either — a
   related but separate gap, left for a future ADR if pursued.

## Reason

The project exists to prevent confidently wrong numbers reaching a billing sheet
([[PROJECT_CONTEXT]] §2). A silently omitted field is the mirror failure: not a wrong number reaching
the sheet, but a real one never reaching it at all, with nothing on screen to say so — and unlike a
wrong value, which at least has a chance of being caught by a gate that checks it, an omitted value
was never given that chance. A reviewer looking at `needs_review` with a full-looking `gates` array
of `format_only` results has no signal that one of them means "not on the page" and another means
"the model didn't try."

A gate cannot fix this without inventing what "should" be on a document type — which is exactly the
mistake this repository has already made three times (`cnic_digit_count`, the boolean
`gates[].passed`, the invented `mrc + otc == subtotal` identity): treating a claim about *shape* as a
claim about *truth*. Deciding a document must have an IBAN, or must have N fields, without a ground
truth to check against, is a business assumption wearing a validator's clothes. Eval, against labeled
documents, is the only place that distinction is answerable honestly.

## Consequences

**Accepted:**

- **[[EVAL_AND_GOLDEN_SET]] §3 is amended**: the release-gate table already lists a recall gate
  (`≥ 0.90`) and a hallucination-rate gate, but nothing enforced that the harness computing them can
  actually separate a recall miss from a true negative. This ADR makes that separation an explicit
  requirement of W12's implementation, not an incidental nice-to-have.
- No gate changes. `check_iban`, `check_arithmetic` and every future format-only gate keep exactly
  the absent-field behaviour [[ADR-004-format-only-gate-state]] specified — that behaviour is correct
  for what gates are for. This ADR names the boundary of that correctness, it does not move it.
- Until W12 exists, an omission like invoice_3's IBAN is not detectable at all on the prototype,
  because there is no golden label to compare against and no gate designed to catch it. That is a
  known, accepted gap for the prototype phase, not a silent one — recorded here so it is chosen
  rather than discovered again later the way the last three shape-vs-truth bugs were.

**Rejected alternatives:**

- *Have a gate fail when a field "commonly expected" on a document type is absent.* Rejected: a gate
  has no deterministic way to know what's "commonly expected" without inventing a document-type field
  model — the same mistake [[ADR-005-mrc-otc-relationship-unspecified]] already made and reversed. A
  missing IBAN on a cash invoice with no bank details is correct; a missing IBAN on a document that
  states one is a miss. A gate cannot tell these apart without ground truth.
- *Have the orchestrator compare the LLM's field count against a per-document-type expected minimum.*
  Rejected for the same reason — it encodes a business assumption with no deterministic basis, the
  exact shape-as-truth failure this repository has hit three times already.
- *Add a field-completeness gate now.* Deferred, not rejected outright. It would need a real
  ground-truth field list per document type, which does not exist — that is the FBR SRO 1006(I)/2021
  mapping question already open in [[PROJECT_CONTEXT]] §7. Worth reconsidering once that mapping
  exists; not before.

## Revisit when

W12's `run_eval.py`/`scorers.py` are actually built — at that point this ADR's requirement becomes
testable and should be checked against, not just asserted. Also revisit once the FBR SRO
1006(I)/2021 field mapping exists, since that is the missing ingredient for any deterministic
field-completeness check to become possible without inventing one.
