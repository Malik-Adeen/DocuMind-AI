---
status: accepted
owner: Adeen
last_reviewed: 2026-08-22
version: 1.0.0
---

# ADR-017 — An LLM-classified `document_type.value` outside the schema's closed enum is coerced to `"unknown"`, not discarded

**Status:** accepted · **Decided:** 2026-08-22
**Supersedes:** — · **Related:** [[ADR-015-truncated-llm-output-is-salvaged-not-repaired]],
[[ADR-016-multi-page-pdfs-are-one-extraction-not-a-merge]]

## Context

Running the real pipeline against a real 12-page PTCL–DTMS service addendum ([[ADR-014-hosted-processing-exception-for-two-named-documents]]),
with the multi-page fix ([[ADR-016-multi-page-pdfs-are-one-extraction-not-a-merge]]) already reading
every page: OCR read all 12 pages, well under the input token budget, and the model classified the
document as `"addendum"` — an accurate read of what the document actually is. `"addendum"` is not a
member of `document_type.value`'s closed enum (`invoice | purchase_order | contract | quotation |
billing_sheet | unknown`), and the entire otherwise-valid, otherwise-gate-verifiable extraction was
discarded.

`_validate_model_output` (`orchestrator.py`) validates the whole LLM response as one JSON Schema
instance via a single `Draft202012Validator`. An enum miss on `document_type` fails the same way a
missing required key in `fields.total` does — the validator does not distinguish "one field guessed
outside a closed set" from "the response is structurally broken." `complete_with_repair` retries the
whole response on any validation error and, after `max_retries + 1` attempts, discards it entirely.
This runs before provenance attachment and before gates, so a real extraction with 16 correct,
gate-verifiable fields never got that far over one classification label.

This is not the gap [[ADR-015-truncated-llm-output-is-salvaged-not-repaired]] already closed:
`TruncatedResponseError` fires only on `finish_reason == "length"`, detected before parsing — a
complete-but-locally-wrong response never enters `_salvage_truncated_output` at all, and that
function's own per-entry leniency only ever covered `fields`/`line_items`. `document_type` had no
partial-credit path anywhere, including inside salvage.

## Decision

**Coerce an unrecognized `document_type.value` to `"unknown"`** — already a member of the enum,
already the `documents.document_type` column's `server_default`, already satisfying the
`documents_type_valid` `CheckConstraint` (`db/models.py`) — preserve every sibling key on the object
and every other field in the response untouched, and record the model's original string in
`review.reason` as `document_type_unrecognized:<value>`. Coercion runs at two call sites that both
funnel through one new `_coerce_document_type(parsed)` helper: the repair-loop validation path (via a
small closure wrapping `_validate_model_output`, so `repair.py` stays domain-agnostic) and inside
`_salvage_truncated_output`, before its own internal schema check, so a truncated response whose only
remaining defect after salvage is `document_type` is no longer discarded either.

Coercion forces `status` to `needs_review`, the same way truncation does — never silently promoted to
`complete` just because every other field happens to gate-verify. When both truncation and coercion
occur on the same response, `review.reason` concatenates both causes with `;`, truncation segment
always first: `"llm_output_truncated;document_type_unrecognized:addendum"`. This is additive, not
either/or — dropping either cause silently would hide a real fact about how the extraction was
produced.

**Whether `"addendum"` (or any other real classification the model produces) should become a first-class
enum member is a separate, deferred question** — explicitly not decided here.

## Reason

Discarding a 16-of-17-field-correct, gate-verifiable extraction over one classification label outside
a closed set is a worse outcome than accepting it with the anomaly surfaced — the same "a fallible
check must not be authoritative enough to block a real result, but must never be silently trusted
either" reasoning [[ADR-012-provenance-merge-was-dead-code]] and
[[ADR-015-truncated-llm-output-is-salvaged-not-repaired]] both already established for provenance
matching and truncation salvage respectively. `"unknown"` was chosen over any other coercion target
because it costs nothing new: no schema change, no DB migration, no export-column change — it is
already the safe default everywhere this value flows.

Coercing rather than widening the enum to accept `"addendum"` outright keeps the decision of whether
a new classification is real and worth adding as a permanent category with a human, informed by
`review.reason`, rather than letting any string the model happens to emit silently become
ground truth the moment it is first seen.

## Consequences

**Accepted:**

- A real extraction is no longer discarded over an out-of-enum `document_type` guess; the 16 other
  fields, provenance, and gate verdicts all survive exactly as they would have otherwise.
- `review.reason` now has a second cause and an established `;`-joined, order-stable convention for
  when future causes need to co-occur.
- `DocumentReview.jsx`'s truncation alert used `===` exact equality against `review.reason` — safe
  only while exactly one cause could ever be set. That assumption broke the moment two causes could
  concatenate; fixed to `reason?.startsWith('llm_output_truncated')` in the same commit, since
  truncation is always the leading segment by convention.
- Whether `"addendum"` deserves to become a real enum member is left open, on purpose — this ADR
  fixes the discard bug, not the taxonomy.

**Rejected alternatives:**

- *Widen the enum to include every string the model might emit.* Rejected: reactive and unbounded —
  every new label the model invents would need another schema edit, and it conflates "the model can
  describe a new category" with "the model's raw classification is trustworthy enough to promote to
  a permanent value without a human confirming it."
- *Keep the unrecognized value as-is, un-coerced.* Rejected: violates the DB `CheckConstraint` and the
  schema's own closed-enum contract for everything downstream (export columns, any enum-driven
  frontend treatment) — this codebase does not let raw LLM output reach persistence unvalidated.
- *A bespoke leniency rule for `document_type` inside `_salvage_truncated_output` only, separate from
  the repair-loop path.* Rejected: would duplicate the same logic at two call sites. One
  `_coerce_document_type` helper, called from both, mutating `parsed` in place before validation, is
  the smaller and more coherent change.

## Revisit when

- Real-world classifications outside the enum (`"addendum"` or others) recur often enough to warrant
  an actual decision about widening `document_type.value`'s enum — this ADR defers that question, it
  does not answer it.
- A future `review.reason` cause needs to carry more than a single `<label>` or `<label>:<value>`
  segment — the `;`-join convention this ADR establishes would need revisiting.
