---
status: accepted
owner: Adeen
last_reviewed: 2026-08-19
version: 1.0.0
---

# ADR-016 — Multi-page PDFs get one extraction call over every page's OCR text, not one call per page merged afterward

**Status:** accepted · **Decided:** 2026-08-19
**Supersedes:** — · **Related:** [[ADR-002-two-stage-ocr]], [[ADR-012-provenance-merge-was-dead-code]],
[[ADR-015-truncated-llm-output-is-salvaged-not-repaired]]

## Context

[[PROJECT_CONTEXT]] §7 carried this as an open question since the file existed: *"Multi-page
documents: one extraction per file, or per logical document?"* In the meantime, the actual behavior
was neither answer — it was a bug. `orchestrator.py::_run_ocr` called `ocr.read(document.storage_path,
page=1)` unconditionally. `app/pipeline/ocr/paddle.py`'s `PaddleLatinOCR.read()` already accepted an
arbitrary `page` argument and could rasterize and OCR any page of a PDF; nothing upstream of it ever
asked for page 2 or beyond. A multi-page PDF upload silently extracted page 1 only, with no signal
anywhere in the API response that later pages existed or were skipped
(`API_CONTRACT.md` §2, now corrected by this change).

Fixed by: `PaddleLatinOCR.page_count(path)` (new — returns the real PDF page count via
`pypdfium2`, or `1` for a non-PDF image); `_run_ocr` now calls it first and loops `1..count`,
collecting every page's regions in page order; `build_prompt` groups those regions by page and
inserts a `--- Page N ---` marker between groups (a single-page document's prompt is byte-identical
to before — the marker only appears when there is more than one page); and a new fail-loud path,
`DocumentTooLargeError`, that can now fire in two places before any OCR or LLM cost is spent: page
count exceeding `Settings.max_pdf_pages` (default 50), or estimated OCR-text token count (`len(text)
// 4`) exceeding `Settings.hosted_llm_max_input_tokens` (default 20000).

Two design questions came with fixing this, addressed below. Everything downstream of OCR — prompt
building past `build_prompt`, the LLM call, provenance attachment, gates, `needs_review` routing,
[[ADR-015-truncated-llm-output-is-salvaged-not-repaired]]'s truncation salvage — is unchanged in
logic; it now simply runs over more input text than before.

## Decision

**A. One LLM call reading every page's OCR text at once — not one call per page merged afterward,
and not a page-relevance filter that decides which pages to send.**

`extract()` still calls `build_prompt_fn` → `complete_with_repair` → `attach_provenance` → gates
exactly once per document, unchanged in shape from the single-page pipeline. The only change is
what `text_regions` contains going in.

**B. No new field-conflict/arbitration mechanism is built, and none should be.** The extraction
schema (`EXTRACTION_SCHEMA.json`) models one value per field, not a list of per-page candidates.
Because Decision A keeps extraction a single call reading the whole document at once, there is no
"page 3 says X, page 9 says Y" moment in the *data* to arbitrate — the model resolves it with full-
document context, the way a human reviewer would. The existing `check_arithmetic` gate
(`orchestrator.py`, unchanged by this ADR) remains the safety net for the fields it covers: if the
chosen `total` doesn't reconcile with `subtotal`/`tax`/`line_items`, that gate fails and routes to
`needs_review` regardless of which pages backed which number — zero new code. Ungated fields
(`customer_name`, `cnic`, dates, and others with no deterministic cross-check) have no backstop for
a cross-page conflict today — but that is not a gap multi-page support introduces; single-page
extraction never had one either, for the same fields.

**Open assumption, not a measured fact:** `hosted_llm_max_input_tokens=20000` is a conservative
default chosen without knowing the deployed vLLM `--max-model-len` — it is not configured anywhere
in this repo, and is presumably set at deploy time. Reasoning: Qwen2.5-7B-Instruct's native context
window is 32,768 tokens; the fixed prompt template plus injected JSON schema is ~10.7 KB, estimated
at the same `chars // 4` rate as ~3000 tokens; `hosted_llm_max_tokens` (the output reserve,
[[ADR-015-truncated-llm-output-is-salvaged-not-repaired]]) is 4000. 20000 leaves comfortable headroom
under both reservations against a 32768-token window. **This is an engineering estimate, not a
measurement**, unlike ADR-015's measured 1340–3201 output-token range — revisit once the real
deployed context window is confirmed (see Revisit when).

## Reason

**Decision A.** `paddle.py`'s OCR primitive already read an arbitrary page correctly; the only bug
was that nothing upstream asked for more than page 1. A single call over all pages keeps the
existing pipeline shape unchanged — the same shape [[ADR-012-provenance-merge-was-dead-code]] and
[[ADR-015-truncated-llm-output-is-salvaged-not-repaired]] both already reasoned about and left
intact. The two alternatives were both worse in identifiable ways, not just less convenient:

- *Per-page extraction + merge* costs N LLM calls instead of one, and reintroduces exactly the
  problem Decision B says not to solve: it would fragment a table or clause that spans a page break
  into two partial, possibly-conflicting extractions, and then require inventing a genuine
  conflict-resolution mechanism to reconcile them — which is what Decision B declines to build.
- *A page-relevance filter* (decide which pages "matter" before extracting) risks silently skipping
  the one page that holds the actual answer, which is the original page-1-only bug in a subtler,
  harder-to-notice form — a filter that is wrong looks identical, from the API, to a filter that is
  right.

**Decision B.** Building a per-page-candidate conflict model would be solving a problem that
Decision A's single-call design does not create in the data. There is no moment where the pipeline
holds two competing values for the same field to arbitrate between — the model sees the whole
document and emits one value, the same as it always did for a single-page document. Inventing
arbitration machinery for a conflict that structurally cannot occur here would be the kind of
speculative complexity this repo avoids. The real risk this decision does accept — the model
picking the wrong one of two genuinely different numbers appearing on different pages — is not a
new risk multi-page support introduces; it is the same risk a single dense page with two candidate
numbers already carried, and `check_arithmetic` is the same backstop that already existed for it.

## Consequences

**Accepted:**

- A multi-page PDF now gets every page read and considered, closing the silent-page-1-only bug this
  ADR fixes. `PROJECT_CONTEXT.md` §7's open question is resolved: one extraction per file, all pages
  in a single LLM call.
- A very large PDF (page count over `max_pdf_pages`, or OCR text estimated over
  `hosted_llm_max_input_tokens`) now fails fast and loud, before any LLM cost is spent, with a new
  `DOCUMENT_TOO_LARGE` code (`app/core/errors.py`, `422`, not retryable) and `document.error`
  populated on the `failed` document — unlike the pre-existing generic `OrchestratorError` path,
  which still leaves `document.error = null` ([[PROJECT_CONTEXT]] §7 "Known gaps", unchanged by this
  ADR).
- `provenance.py` needed no change: it already required every region backing one matched quote to
  share a single page, or treats the match as unresolved rather than fabricating a cross-page bbox.
  It simply never had multi-page input to prove that on before this change.
- Ungated fields still have no deterministic cross-page backstop. Named honestly here rather than
  implied fixed — see Decision B.
- The frontend (`DocumentReview.jsx`) is explicitly untouched by this change. `source.page` is now
  correct end-to-end in the API response, but nothing yet *displays* it: no page-count API field, no
  per-page image endpoint, no page-switcher UI, and PDFs still render as a download fallback rather
  than an inline preview. Future work, not silently implied done.

**Rejected alternatives:**

- *Per-page extraction with a merge step.* Rejected per Reason above: N× the LLM calls, fragments
  content spanning a page break, and requires a conflict-resolution mechanism this decision
  otherwise avoids building.
- *A page-relevance filter deciding which pages to send.* Rejected per Reason above: risks silently
  reintroducing the original bug — skipping the page that actually holds the answer — in a form
  that is harder to detect than "page 1 only" was.
- *A new field-conflict/arbitration mechanism (Decision B).* Rejected because Decision A's
  single-call design does not produce a conflict in the data to arbitrate. Building one now would be
  speculative machinery for a problem that does not exist under this design, and would need to be
  reasoned about again from scratch if Decision A is ever revisited.

## Revisit when

- The deployed vLLM `--max-model-len` is confirmed for the `production` profile. Replace the
  20000-token `hosted_llm_max_input_tokens` estimate with a real measured budget, the same way
  [[ADR-015-truncated-llm-output-is-salvaged-not-repaired]] replaced the output-side ceiling with a
  measured range instead of an unmeasured literal.
- A real document is observed where `check_arithmetic` (or the absence of any gate on an ungated
  field) fails to catch a genuine cross-page conflict — that would be the first real evidence for or
  against Decision B's "no arbitration mechanism needed" reasoning, the same way ADR-012 waited for
  a real run before deciding whether fuzzy matching was worth building.
- The frontend work named as future in Consequences actually starts: per-page image endpoint,
  page-count in the API response, and a page-switcher UI in `DocumentReview.jsx`. That is a separate
  change with its own doc updates, not implied by this ADR.
