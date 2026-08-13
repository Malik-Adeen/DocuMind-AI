---
status: accepted
owner: Adeen
last_reviewed: 2026-08-13
version: 1.0.0
---

# ADR-012 — Provenance merge was dead code since day one; the fix flags an unmatched claim, it does not fail the extraction

**Status:** accepted · **Decided:** 2026-08-13
**Supersedes:** — · **Related:** [[ADR-002-two-stage-ocr]], [[ADR-004-format-only-gate-state]],
[[ADR-011-terminal-status-requires-positive-verification-evidence]]

## Context

**INV-2** ([[PROJECT_CONTEXT]] §6): *"Every extracted field carries a confidence value and a source
span (page + bbox). A field with no provenance is a bug, not a low-confidence result."* [[ADR-002-two-stage-ocr]]
built the two-stage OCR design specifically to satisfy it: *"Whatever runs here has to yield boxes,
not just text."*

It never reached a field. Traced in code:

- `app/pipeline/ocr/paddle.py`'s `TextRegion.as_source()` computes a real, normalised bbox per
  detected text region and has since the module existed. It is unit-tested in isolation
  (`tests/unit/test_paddle_ocr.py`). **It is never called anywhere in the live pipeline** — confirmed
  by a repo-wide grep for `as_source` outside its own test file.
- `app/pipeline/llm/prompt_builder.py:23`'s `build_prompt()` flattens every `TextRegion` down to
  `region.text` before the LLM ever sees it. Bbox, page, and per-region confidence do not survive
  into the prompt.
- `app/pipeline/llm/prompts/extract_v1.txt:10` accordingly only asks the model for
  `{"origin": "llm_inferred", "raw_text": "<exact quoted substring>"}` — a quote, never a coordinate,
  because no coordinate reaches the prompt to quote.
- `orchestrator.py`'s `extract()` took `parsed["fields"]` verbatim. Nothing re-attached a field's
  `raw_text` back to the `TextRegion` it was quoted from.
- Evidence this was live, not theoretical: every field-level `source` object across
  `backend/evals/history/*.jsonl` (5 files, real hosted-LLM runs, 2026-08-10) has **zero** occurrences
  of `"bbox"` or `"page"`. The only non-null bbox anywhere in the repository was a hardcoded literal
  in `app/db/fixtures.py` — `[0.1, 0.2, 0.5, 0.24]`, identical for every field, used only to seed 3
  demo documents.

No check would have caught this. INV-1 has `_assert_money_fields_gated` / `GateCoverageError`
(`orchestrator.py`). INV-2 had no equivalent, so the gap shipped silently from the moment ADR-002 was
accepted until this ADR.

This surfaced sideways: a request to highlight a field's source bbox in the review UI
(`DocumentReview.jsx`) turned up that the data it would render simply does not exist on any real
extraction.

## Decision

**A new stage, `app/pipeline/provenance.py`, wired into `orchestrator.py::extract()` right after
`fields`/`line_items` are built and before gates run:**

For every field (top-level, and each line item's `description`/`quantity`/`unit_price`/
`line_total`) whose `source.origin == "llm_inferred"` and `source.raw_text` is present, it does an
**exact, case-sensitive substring search** for that quote against the same joined OCR text
`build_prompt` sent the LLM (region texts joined with `"\n"`, offsets tracked per region):

- A match spanning one region → that region's `page`/`bbox` is attached.
- A match spanning several adjacent regions → the bboxes are unioned, page taken from the matched
  regions (they must agree — a match spanning disagreeing pages is treated as no match).
- No match → **`source` is left exactly as the LLM produced it.** No `page`/`bbox` key is added.
  Never a fabricated box, per an explicit constraint on this fix.
- Fields with no `raw_text`, or a non-OCR origin (`human`, `computed`), are untouched — they never
  claimed provenance, so there's nothing to attach or flag.

**An unmatched claim does not fail the extraction.** It is recorded in the returned
`ProvenanceReport.unmatched_claims`, logged (`logger.warning`, one line per extraction naming the
fields), and folded into `_needs_review()` as one more reason the whole extraction routes to
`needs_review` — exactly the same weight as an unverified field or a failed gate. Nothing raises.

## Reason

The first draft of this fix mirrored `_assert_money_fields_gated`: raise and refuse to persist if a
claimed quote didn't resolve. That was wrong, and was corrected before implementation.

**The check itself is fallible, and a fallible check must not be authoritative over the document.**
Exact-substring matching against *reconstructed* OCR text (the same joined string `build_prompt`
built, not the original image) can fail for reasons that have nothing to do with whether the LLM's
underlying answer is correct: the model paraphrasing a quote by one character, joining logic drift,
or — the one this ADR has real evidence for below — a model stitching two genuinely separate, non-
adjacent pieces of OCR text into a single plausible-looking quote. None of those mean the extracted
*value* is wrong. They mean *this specific check* couldn't confirm where it came from.

That is precisely the shape [[ADR-004-format-only-gate-state]] already named for CNIC/NTN/STRN: a
check that can tell you something is *plausibly* right but cannot prove it is *actually* right must
never be allowed to condemn on failure, only to withhold confirmation. `format_only` can flag a field
unverified; it cannot fail the pipeline. The provenance match is the same category of check, so it
gets the same treatment: unmatched → unconfirmed signal → `needs_review`, never a hard stop.

[[ARCHITECTURE]] §7's failure-mode table backs this reading directly — every row for a check that can
be *wrong about its own inputs* (`Gate fails`, `Gate returns format_only`) resolves to `needs_review`
with the affected field marked unverified. Only structural failures that mean *there is nothing
usable to persist at all* (empty OCR, invalid JSON after repair, a refused hosted call) hard-fail the
extraction. A provenance mismatch is not that: the extraction has a value, a confidence, and an
`origin` — it is missing one further fact this pipeline would like to have and, on this evidence
(below), usually does.

## Evidence: the first real run

Reusing the existing `evals/repro.py` harness (unmodified) against the real hosted LLM
(`HOSTED_LLM_BASE_URL`/`HOSTED_LLM_API_KEY` from `.env`), 5 reps × the 3 synthetic invoice fixtures in
`tests/fixtures/invoices/`, with `attach_provenance()` run against each parsed response:

| Invoice | resolved / claimed |
|---|---|
| `invoice_1_simple` | 99 / 99 (100%) |
| `invoice_2_recurring_service` | 75 / 75 (100%) |
| `invoice_3_dense_layout` | 103 / 109 (94.5%) |
| **Total** | **277 / 283 (97.9%)** |

**97.9% is good enough that exact matching does not need normalization as a first response.** The
one invoice with misses names why: `invoice_3_dense_layout`'s line-item table renders as
`Item····Qty····Unit·Price····Line·Total` — a header row, with each data row's numbers appearing far
below it, not adjacent. One rep's model reconstructed `raw_text: "Qty    1"` and
`raw_text: "Unit Price    80000.00"` — plausible label-plus-value strings that are **not actually
contiguous** in the OCR text; the label and the value are dozens of characters apart. This is not a
whitespace or case mismatch that normalization would fix — the model synthesized a quote that does
not exist verbatim in its own input. The exact-substring check rejected it correctly. That is the
check doing its job, not the check being too strict.

## Consequences

**Accepted:**

- Real extractions now carry real `page`/`bbox` provenance on any field the LLM grounded in an exact
  OCR quote — 97.9% of claimed quotes on this run. The previously-shelved bbox-highlight UI in
  `DocumentReview.jsx` becomes buildable against real data (not part of this ADR or this change).
- An unmatched claim adds one more path to `needs_review`, alongside a failed or `format_only` gate.
  This will increase review traffic slightly on documents with dense tabular layouts specifically —
  the same accepted trade-off [[ADR-011-terminal-status-requires-positive-verification-evidence]]
  already made: more review load beats a document reaching `complete` on an unconfirmed signal.
- No schema or API contract change. `EXTRACTION_SCHEMA.json`'s `source.page`/`source.bbox` were
  already optional and already documented in `API_CONTRACT.md`; this fix populates a shape that was
  already promised, it does not change it.
- **INV-2's wording in [[PROJECT_CONTEXT]] §6 is unchanged.** Read literally it asks for provenance on
  *every* extracted field, which is unreachable without fabrication whenever the model legitimately
  cannot quote exact supporting text (`extract_v1.txt:10` already permits omitting `raw_text` in that
  case). This ADR is the record of what "every field carries a source span" is actually enforced as:
  never fabricate, and any field that *does* claim a quote gets that claim checked and the result
  surfaced to a reviewer — narrower than the literal text, in the same way
  [[ADR-004-format-only-gate-state]] narrowed what a passing gate is allowed to mean, and
  [[ADR-009-omission-is-invisible-to-the-gate-layer]] narrowed what a gate can be expected to catch.

**Rejected alternatives:**

- *Hard-fail the extraction (`raise`) on any unmatched claim*, mirroring INV-1's
  `_assert_money_fields_gated`. Rejected per Reason above: the check can be wrong in ways that have
  nothing to do with the extracted value being wrong, so it must not be authoritative over the whole
  document. INV-1's gate-coverage check is different in kind — "did every money field get *a* gate
  verdict at all" is a structural, always-answerable fact about the pipeline's own bookkeeping, not a
  claim about whether some external text genuinely matches. That distinction is why one gets a hard
  raise and the other doesn't.
- *Fuzzy/normalized matching (case-insensitive, whitespace-collapsed) from the start.* Deferred, not
  rejected outright — the real-run evidence above shows the actual failure mode is not whitespace or
  case, it's the model stitching non-adjacent text into one quote. Normalizing whitespace would not
  have resolved a single one of the 6 misses in this run. Building it speculatively, before seeing
  what actually fails, would have been solving a problem this data doesn't show.

## Revisit when

- A larger real-run sample (this ADR's evidence is 15 reps across 3 fixtures, not a golden set) shows
  the unmatched rate concentrated somewhere normalization *would* actually fix — re-run this same
  check periodically as real documents accumulate.
- `backend/evals/run_eval.py` exists (it does not yet — only `evals/repro.py` and
  `evals/history/*.jsonl` exist today, despite `backend/CLAUDE.md` listing it as a command). Once it
  does, add a golden-set-level `resolved / claimed` regression threshold as a second, CI-level signal
  alongside the per-request log line this ADR ships with.
