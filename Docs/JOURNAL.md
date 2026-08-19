---
status: active
owner: Adeen
last_reviewed: 2026-08-05
version: 1.0.0
---

# JOURNAL.md — working log

Append-only. **Newest entry first** — new entries go directly below this line, never at the
bottom. Never edit or delete a past entry; if it was wrong, say so in a new one.

One entry per session. Keep each to what a future reader needs: what changed, why, and what
broke. Not a changelog of commits — git already has that.

Entry format:

```
## YYYY-MM-DD — one-line summary

**Touched:** INV-n · files or areas
**Did:** what actually happened
**Learned / broke:** the thing that was not obvious beforehand
**Next:** the open thread, if any
```

---

<!-- newest entry goes here -->

## 2026-08-19 — multi-page PDFs are read in full, one extraction call over every page (ADR-016)

**Touched:** no INV directly (closes the open question in [[PROJECT_CONTEXT]] §7) ·
`CodeBase/backend/app/core/config.py` (+`max_pdf_pages`, +`hosted_llm_max_input_tokens`),
`CodeBase/backend/app/core/errors.py` (+`DOCUMENT_TOO_LARGE`), `CodeBase/backend/app/pipeline/ocr/paddle.py`
(+`PaddleLatinOCR.page_count()`), `CodeBase/backend/app/pipeline/orchestrator.py` (`OCRReader.page_count`,
`_run_ocr` loops every page, +`DocumentTooLargeError`, input-token-budget check in `extract()`),
`CodeBase/backend/app/pipeline/llm/prompt_builder.py` (`--- Page N ---` markers, single-page prompt
unchanged), `CodeBase/backend/app/workers/tasks.py` (`DocumentTooLargeError` branch populates
`document.error`), `CodeBase/backend/.env.example` (+`HOSTED_LLM_MAX_INPUT_TOKENS`, +`MAX_PDF_PAGES`),
`Docs/decisions/ADR-016-multi-page-pdfs-are-one-extraction-not-a-merge.md` (new), `Docs/ARCHITECTURE.md`
§2/§4/§7, `Docs/API_CONTRACT.md` (0.3.8 → 0.3.9), `Docs/PROJECT_CONTEXT.md` §7/§8, `Docs/INDEX.md`,
branch `multipage-pdf-support`, off `master`.

**Did:** `_run_ocr` previously called `ocr.read(path, page=1)` unconditionally — a multi-page PDF
silently extracted page 1 only, with no signal anywhere that later pages existed
(`a87f681`). `PaddleLatinOCR.read()` already supported reading an arbitrary page; nothing upstream
ever asked for more than one. Fixed: `page_count()` (new, via `pypdfium2`) is called first; a count
over `max_pdf_pages` (default 50) raises `DocumentTooLargeError` before any OCR call; otherwise every
page `1..count` is OCR'd and all regions collected in page order. `build_prompt` groups regions by
page with a `--- Page N ---` marker (byte-identical output for single-page documents). `extract()`
adds a second fail-fast check after OCR: estimated input tokens (`len(text)//4`) over
`hosted_llm_max_input_tokens` (default 20000) also raises `DocumentTooLargeError`, before the LLM is
ever called. `provenance.py` needed no change — it already required a matched quote's regions to
share one page. Everything downstream of OCR (prompt building past `build_prompt`, the LLM call,
provenance, gates, `needs_review` routing, ADR-015's truncation salvage) is unchanged in logic.
Follow-up commit `b74d091` fixed `tests/contract/conftest.py` and two integration test files whose
`OCRReader` test doubles didn't implement the widened Protocol's new `page_count()` method
(`AttributeError`, both suites broken since `a87f681`).

Recorded the two design decisions in [[ADR-016-multi-page-pdfs-are-one-extraction-not-a-merge]]: one
LLM call over all pages' OCR text, not per-page extraction+merge (N× cost, fragments page-spanning
content) and not a page-relevance filter (risks silently reintroducing the original bug); and no new
field-conflict/arbitration mechanism, because a single-call design produces no per-page candidates to
arbitrate in the first place — `check_arithmetic` remains the only backstop, unchanged. Flagged
`hosted_llm_max_input_tokens=20000` explicitly as an unmeasured engineering estimate (Qwen2.5-7B's
32768-token window minus the ~3000-token prompt template and the 4000-token output reserve), not a
measurement like ADR-015's output-token range — revisit once the deployed vLLM `--max-model-len` is
known.

**Learned / broke:** widening a `Protocol` (`OCRReader.page_count`) breaks every structural
implementer silently at runtime, not at import time — `mypy --strict` over `app/` doesn't catch a
test double under `tests/` failing to implement it, so the two broken suites only surfaced on a live
`pytest` run, not statically.

**Next:** frontend (`DocumentReview.jsx`) still never reads `field.source.page` and still shows PDFs
as a download fallback — no page-count API field, no per-page image endpoint, no page-switcher UI.
`source.page` is correct end-to-end in the API response now; nothing displays it yet.

## 2026-08-18 — truncated LLM output is detected via finish_reason, salvaged instead of retried, and forced to needs_review (ADR-015)

**Touched:** no INV directly (fallible-check discipline, same class as INV-2/ADR-012) ·
`CodeBase/backend/app/pipeline/llm/transport.py` (+`TruncatedResponseError`, `max_tokens` default
2000→4000), `CodeBase/backend/app/pipeline/orchestrator.py` (`_salvage_truncated_output`,
`ExtractionOutcome.truncated`, forced `needs_review`, `document.error` in `run_and_persist`),
`CodeBase/backend/app/core/config.py` (+`hosted_llm_max_tokens`), `CodeBase/backend/app/core/errors.py`
(+`LLM_OUTPUT_TRUNCATED`), `CodeBase/backend/app/workers/tasks.py`, `CodeBase/backend/.env`/`.env.example`,
`CodeBase/backend/pyproject.toml` (+`json-repair`), `CodeBase/backend/tests/unit/test_transport.py`,
`CodeBase/backend/tests/unit/test_orchestrator.py`, `CodeBase/backend/tests/integration/test_worker_errors.py`,
`CodeBase/frontend/documind-ai/src/components/screens/DocumentReview.jsx`,
`Docs/decisions/ADR-015-truncated-llm-output-is-salvaged-not-repaired.md` (new), `Docs/ARCHITECTURE.md` §7,
`Docs/API_CONTRACT.md` (0.3.7 → 0.3.8), `Docs/PROJECT_CONTEXT.md` §8, `Docs/INDEX.md`, branch
`fix/llm-truncation-detection`, off `master`

**Did:** Diagnosed before touching anything, per instruction. Traced the exact path: `HostedChatTransport
.__call__` returned only `content`, discarding the response body `finish_reason` lived in — the same
"discarded until `complete_full()` was built for the eval harness" pattern JOURNAL 2026-08-10 already
named for `provider`/`id`, except production never adopted `complete_full()`. A truncated response's
`json.JSONDecodeError` was indistinguishable from genuine malformation and triggered the same
repair-prompt retry, which resends the original prompt plus the entire truncated output plus an error
string — a *longer* request with the same odds of truncating again. Measured real hosted-LLM calls
against a dense document (17 fields, 5 line items): 4 of 5 direct `complete_full()` calls returned
`finish_reason: "length"` at exactly `completion_tokens: 2000`; natural (uncapped) completions ranged
1340–3201 tokens across 13 real calls — the 2000 ceiling sat below the observed maximum, the direct
cause of the ~45% failure rate. A 2329-token natural response correctly enumerated all 5 real line
items; capped/truncated responses enumerated only 2 — the ceiling wasn't just failing outright, it was
rewarding incomplete extractions that happened to fit.

Fixed in three parts, all evidence-driven per instruction to diagnose before deciding: (1)
`HostedChatTransport.__call__` now raises `TruncatedResponseError(content)` on `finish_reason ==
"length"`, using the field that was already being computed and discarded — no new API call. (2)
`orchestrator.py::extract()` catches it *around* `complete_with_repair()`, not inside it, so
truncation never enters the repair-retry loop. (3) `_salvage_truncated_output()` runs `json_repair`
(new dependency — a hand-rolled truncated-JSON/escaped-string parser was rejected as too risky for a
reviewer-facing path) to close out whatever the model had actually finished, then re-validates every
field/line-item entry individually against its own `$defs/field`/`$defs/money_field` schema fragment,
dropping anything left with holes (missing `confidence`/`verified`/`source`) rather than keeping a
guess. If nothing survives, it fails exactly as any other unrecoverable response does
(`ExtractionFailedError`). If something survives, the extraction is **forced** to `needs_review` —
never promoted to `complete` even if every recovered field happens to gate-verify — with
`review.reason: "llm_output_truncated"` and `document.error` populated (`LLM_OUTPUT_TRUNCATED`), the
first case where `/status.error` is non-null on a document that is not `failed`.
`hosted_llm_max_tokens` is now a `Settings` field defaulted to 4000 (roughly 2x typical, headroom over
every sample observed), externalized like the other hosted-LLM knobs rather than left as a dataclass
literal — the whole point being that an unmeasured hardcoded number at this layer is what caused the
problem. `DocumentReview.jsx` now fetches `GET .../status` after a successful `needs_review` load
too (previously only on the `NOT_READY` fallback path) and renders `error.message` distinctly when
`review.reason` is present.

**Learned / broke:** The salvage is a second instance of exactly [[ADR-012-provenance-merge-was-dead-code]]'s
pattern — a fallible recovery check that must never be authoritative — and ADR-015 says so explicitly
rather than re-deriving the reasoning from scratch. Per-entry schema re-validation (not just "does
`json_repair` return a dict") was necessary in practice, not paranoia: `json_repair` happily returns a
field object with only `{"value": "..."}` when generation stops mid-object, missing the three other
required keys — without dropping those, a "recovered" field could reach a reviewer with no
`confidence`/`verified`/`source` at all, silently violating INV-2 the same way the pre-ADR-012 bug did.

**Next:** `evals/run_eval.py` still does not exist (ADR-012's own open item, still open) — truncation
rate and salvage-recovery rate belong there as a golden-set-level signal once it does, not just the
per-request log line this ships with. If a document is ever observed naturally exceeding 4000 output
tokens (not just hitting the old 2000 cap), the ceiling needs re-measuring against that evidence, not
another instinct-driven bump.

## 2026-08-17 — `source.unmatched` surfaces fabricated provenance quotes to the API and UI (schema 0.3.1)

**Touched:** INV-2 (extended, not reversed) · `CodeBase/backend/app/pipeline/provenance.py`,
`Docs/EXTRACTION_SCHEMA.json` (0.3.0 → 0.3.1), `CodeBase/backend/app/db/models.py` (`SCHEMA_VERSION`),
`CodeBase/backend/app/db/migrations/versions/0003_schema_version_0_3_1.py` (new),
`CodeBase/backend/app/db/fixtures.py`, `CodeBase/backend/tests/unit/test_provenance.py`,
`CodeBase/backend/tests/unit/test_orchestrator.py`, `CodeBase/backend/tests/integration/conftest.py`,
`CodeBase/backend/tests/contract/test_api_contract.py`, `Docs/ARCHITECTURE.md` §2 (Stage 5b),
`Docs/API_CONTRACT.md` §4 (0.3.5 → 0.3.6),
`CodeBase/frontend/documind-ai/src/components/screens/DocumentReview.jsx`, branch
`feat/status-error-and-contract-ownership`, off `master`

**Did:** The earlier session's live run against `Azeem.jpeg`/`Azeem.pdf` surfaced a real LLM
hallucination — a fabricated line item with a `raw_text` quote that doesn't exist anywhere in the
source. Checked whether that class of failure (a claimed quote that provenance-merge can't find in
the OCR text) reaches the API at all: it didn't. `attach_provenance()` computed
`ProvenanceReport.unmatched_claims` correctly, but the orchestrator only used it for logging and the
`needs_review` decision — it was never attached to the field it belonged to, so the API and UI had
no way to distinguish "no gate covers this field" from "the model's own cited evidence for this
field is fabricated." Fixed at the source: `_attach_field` now sets `source.unmatched = true` on the
exact field/line-item entry whose claim didn't match, and clears any pre-existing value otherwise —
authoritatively, the same way `verified`/`gate`/`gate_error` are orchestrator-owned regardless of
what the model output. Because `fields`/`line_items` are mutated in place and referenced directly by
`orchestrator.py`'s `result` dict, no orchestrator.py change was needed at all — the fix is entirely
inside `provenance.py`. Added the property to `EXTRACTION_SCHEMA.json` (`$defs/source`, optional,
present only when `true`), which meant bumping `schema_version` 0.3.0 → 0.3.1 per this project's own
"additive change → version bump" convention, which meant a new migration for the DB's
`extractions_schema_version_current` CHECK constraint, which meant re-seeding `fixtures.py` and every
test that pinned the literal `"0.3.0"`. Rendered it in `DocumentReview.jsx` as its own
`UnmatchedClaimBadge` (destructive/`AlertTriangle`), additive alongside — never replacing — the
existing Verified/Unverified badge, since a field can be gate-verified on its value while its
citation is unmatched, or vice versa; the two are orthogonal signals.

**Learned / broke:** The three local Postgres databases this project's test layers use
(`ptcl_test`, `ptcl_contract`, and the dev `ptcl` DB) are never dropped between sessions — only
`TRUNCATE`d per-test at best — so a new CHECK constraint that tightens an existing column (here,
`schema_version`'s exact-match check) fails to apply via `alembic upgrade head` the moment any of
those databases holds even one older row, with an error that looks like a broken migration rather
than what it is: stale local state. Confirmed via `git stash -u` that the unrelated
`test_download_export_returns_binary[real]` failure pre-dates this session's changes (still fails
identically on unmodified `master`) — not a regression, left unfixed as out of scope.

**Next:** The Excel exporter (`app/export/xlsx.py`) never reads `source` at all, so a field that is
gate-verified but provenance-unmatched exports with no amber flag today — confirmed, not fixed;
would need its own scoped change if that gap matters enough to close.

## 2026-08-17 — UploadCenter classification selector shipped; first two real PTCL documents run end to end (ADR-014)

**Touched:** INV-6 (exercised, not changed) ·
`CodeBase/frontend/documind-ai/src/components/screens/UploadCenter.jsx`,
`Docs/decisions/ADR-014-hosted-processing-exception-for-two-named-documents.md` (new),
`Docs/PROJECT_CONTEXT.md` §8, `Docs/INDEX.md`, branch `feat/status-error-and-contract-ownership`

**Did:** `UploadCenter.jsx` hardcoded `data_classification: 'synthetic'` on every upload, which made
INV-6's guard unenforceable from the UI — any file, real or not, went out the door pre-classified
"safe." Replaced it with a required `<select>` (`public` / `synthetic` / `restricted`, no default;
`""` is not a valid option) that gates the dropzone and Browse button until a value is chosen.
`API_CONTRACT.md` §2 already documented `data_classification`'s allowed values and default-deny
behavior in full from the prior session's work — nothing to add there. Wrote
[[ADR-014-hosted-processing-exception-for-two-named-documents]] recording that `Azeem.jpeg` (a Road
Master → PTCL purchase order, scanned/stamped/signed) and `Azeem.pdf` (a 12-page PTCL–DTMS addendum)
are uploaded `public` under verbal authorization for a one-off hosted-profile test — per-document,
not a category, INV-6's code untouched. Then started the real stack (Postgres, Redis, `uvicorn`,
`vite`) and ran both documents through it: one via `curl`, one through the live UI (confirming the
new selector actually gates upload and the `public` value reaches the API), both landing on
`needs_review` with no errors.

**Learned / broke:** The `line_item_sum` gate is not decorative — it caught a real LLM hallucination.
`Azeem.jpeg`'s line-items table has one priced row (CPU, $533) and four rows with blank price cells
(RAM/Storage/Public IP/Network Bandwidth); the model invented a second priced row ("RAM 16 GB",
qty 20, unit $27.68, total $553.60 — none of these numbers appear anywhere in the source) complete
with a fabricated `raw_text` quote, and the gate flagged the resulting sum mismatch
(533.00 + 553.60 = 1086.60 ≠ subtotal 533.00) exactly as designed. Separately, `vendor_name`/
`customer_name` came back as Road Master / PTCL — likely reversed, since a same-session read of
`Azeem.pdf` page 4 shows PTCL explicitly named "Vendor" supplying compute/storage/RAM to a
"Customer," the same category of line items as the PO — and the prompt (`extract_v1.txt`) has zero
guidance on how to tell buyer from seller on a purchase order, only invoice-shaped assumptions.
Provenance-merge resolved 8/17 claimed quotes on the skewed jpeg scan vs. 1/1 on the clean PDF
render — no deskew stage exists in the pipeline today, and the one PDF page rasterized (the cover)
carried effectively no extractable fields; the other eleven pages, including the one stamped
"Confidentiality Statement," were never read. Full finding-by-finding writeup handed to Adeen for
review before any of it gets fixed.

**Next:** Awaiting Adeen's decision on which findings to fix (OCR/deskew, prompt PO-role guidance,
missing `po_date`-shaped field, line-item hallucination guardrail) — nothing has been changed yet
per instruction.

## 2026-08-14 — API_CONTRACT ownership consolidates to Adeen (ADR-013); `/status.error` populated for two failure causes

**Touched:** no INV directly · `Docs/decisions/ADR-013-single-owner-for-the-api-contract.md` (new),
`Docs/API_CONTRACT.md` (owner, banner removed, 0.3.3 → 0.3.5), `Docs/PROJECT_CONTEXT.md` §4/§7/§8,
`Docs/AGENT_RULES.md` §2/§5, `Docs/INDEX.md`, `CodeBase/backend/app/db/models.py` (+`Document.error`),
`CodeBase/backend/app/db/migrations/versions/0002_document_error.py` (new),
`CodeBase/backend/app/core/errors.py` (+`HOSTED_ENDPOINT_REFUSED`),
`CodeBase/backend/app/workers/tasks.py`, `CodeBase/backend/app/services/documents.py`
(`status_payload`), `CodeBase/backend/tests/integration/test_worker_errors.py` (new),
`CodeBase/backend/tests/unit/test_status_payload.py` (new),
`CodeBase/frontend/documind-ai/src/components/screens/DocumentReview.jsx`, branch
`feat/status-error-and-contract-ownership`, off `master`

**Did:** Two independent follow-ups.

**(a) Ownership.** The backend/frontend split described in [[PROJECT_CONTEXT]] §4 ended — Adeen owns
both sides now. Wrote [[ADR-013-single-owner-for-the-api-contract]] recording that the co-ownership
gate in [[AGENT_RULES]] §2 (endpoint/status/error-code changes needing both owners to agree) is
retired, not satisfied — the ADR is explicit that this does not retroactively mean 0.2.0/0.3.0 got a
second review, only that the role the gate depended on no longer exists. Removed `API_CONTRACT.md`'s
"Not agreed" banner, changed its owner to Adeen alone, and updated every other doc that named the
two-party split as current (`PROJECT_CONTEXT` §4, `AGENT_RULES` §2's trigger table and §5's area-rule
table, `INDEX.md`'s two owner columns). Left the historical record alone: ADR-007's text and every
JOURNAL entry that says "the frontend dev has not been told" are append-only and were true when
written — this session doesn't edit them, it explains why the sentence stops applying going forward.

**(b) `/status.error`.** Was hardcoded `None` regardless of cause (`PROJECT_CONTEXT` §7's recorded
gap). Populated for exactly two causes, per explicit scope — not every `OrchestratorError` subclass:
`HostedEndpointRefusedError` (INV-6 refusing a `restricted` document at extraction) and the
unclassified `except Exception` catch-all in `extract_document`. New nullable `documents.error` JSONB
column (migration `0002`, `CHECK` constraint requiring `code`/`message`/`retryable` keys when
non-null), populated via `app/core/errors.py`'s existing `envelope()` so the shape can't drift from
the HTTP error envelope's. `HostedEndpointRefusedError`'s message is used verbatim — ADR-006 already
constrains it to the document id and classification label, no document content, and
`test_llm_guard.py` already proves that. The catch-all does **not** use `str(exc)` — an unclassified
exception's text is an unknown quantity and could contain anything a downstream library embedded in
an error message — instead it logs the real exception server-side under a fresh `trace_id` and
returns a fixed generic message naming only that id. `status_payload()` now returns `document.error`
instead of the hardcoded `None`. `DocumentReview.jsx`'s failure state (previously "still processing"
for a terminal `failed` document — same bug independently found and fixed on the unrelated
`fix/demo-rehearsal-issues` branch, redone here since this branch forked from `master` before that
fix existed) now falls back to `GET /status` on a `NOT_READY` catch and, when `status.error` is
present, renders its `message` directly instead of a generic placeholder.

**Learned / broke:** Confirmed by tracing the call chain, not assumed: `HostedEndpointRefusedError` is
a plain `RuntimeError`, not an `OrchestratorError` subclass, and `llm/repair.py`'s
`complete_with_repair` only wraps `json.loads`/`validate` in `try/except` — the `complete()` call
itself is unguarded — so the refusal propagates through `extract()` and `run_and_persist()` completely
unwrapped and reaches `workers/tasks.py`'s exception handling exactly once, in the right shape to
catch specifically. `tests/contract/`'s fake LLM client (`conftest.py`'s `_fake_llm_client`) is
deliberately built with `Endpoint.LOCAL`, so the real contract suite can never exercise
`HOSTED_ENDPOINT_REFUSED` — coverage for it lives in the new integration test, which builds its own
`Endpoint.HOSTED` client and monkeypatches `worker_tasks.build_llm_client`/`build_ocr_reader` directly.
`tests/mock_server.py`'s `/status` still hardcodes `"error": None` — left alone, since the mock has no
path to reach `status: "failed"` at all through its own upload/progression flow, so there's nothing
for it to populate; the response *shape* (`error: null | object`) still matches the real app either
way.

**Next:** The other three `OrchestratorError` subclasses (`OCRFailedError`, `ExtractionFailedError`,
`GateCoverageError`) still leave `error: null` — `PROJECT_CONTEXT` §7 now names this precisely instead
of describing the field as unconditionally null. `test_download_export_returns_binary[real]`'s
pre-existing timing bug (diagnosed and fixed on `fix/demo-rehearsal-issues`, unrelated to this branch)
still reproduces here since this branch forked from `master` before that fix landed — not touched,
out of scope for this session. Branch `feat/status-error-and-contract-ownership` has both fixes,
nothing committed.

## 2026-08-13 — demo-rehearsal punch list: five fixes plus a mock-fidelity gap in the export contract test, `fix/demo-rehearsal-issues`

**Touched:** no INV directly (see Learned/broke for what each protects) · `dev.sh` (Celery pool),
`CodeBase/frontend/documind-ai/src/components/screens/DocumentReview.jsx` (confidence-badge
suppression on human correction; failed-vs-still-processing distinction), `CodeBase/backend/app/core/errors.py`
(+`DOCUMENTS_NOT_EXPORTABLE`), `CodeBase/backend/app/services/exports.py` (`create_export` now
validates before enqueueing), `CodeBase/backend/tests/integration/test_exports.py` (new),
`Docs/API_CONTRACT.md` (0.3.3 → 0.3.4, §6, §8), `CodeBase/frontend/documind-ai/src/components/screens/Login.jsx`
(placeholder domain), `CodeBase/backend/tests/contract/test_api_contract.py`
(`test_download_export_returns_binary` now polls to terminal status)

**Did:** Five issues surfaced by a demo rehearsal, fixed in order with review between each, branch
off `master`, nothing committed yet:

1. `dev.sh` started Celery with the default `prefork` pool — three documents processed in parallel
   during the rehearsal, contradicting ARCHITECTURE §1's "serialised GPU stage." Added `--pool solo`.
   Distinct from §3's "concurrency is a config value" (that's a production worker-*count*, tuned by
   a load test that doesn't exist yet); `--pool solo` just forces one task at a time in the dev
   worker.
2. A human-corrected field rendered `Score: 0% · Verified · Human` simultaneously. Root cause:
   `db/queries.py`'s correction-merge CTE overlays `value`/`verified`/`source`/`gate` but leaves the
   original model `confidence` untouched. Fixed in the UI, not the backend —
   `EXTRACTION_SCHEMA.json` requires `confidence` as a non-nullable `[0,1]` number, so there is no
   valid reset value that wouldn't fabricate a model score that was never computed. `EditableFieldRow`
   now hides the Score badge when `source.origin === "human"`. Checked `app/export/xlsx.py`
   separately — it never reads or styles on `confidence` (only `value` and `verified`/`gate_error`),
   so the same contradiction cannot reach the xlsx output; no export-side change needed.
3. Export silently dropped documents with no extraction row (`document.status == "failed"` never
   gets a persisted `Extraction` — `run_and_persist` raises before the insert, and
   `workers/tasks.py`'s except-block only sets `document.status`). `write_workbook` skipped them with
   `if view is None: continue`, no warning anywhere. Chose to refuse the whole export over
   include-and-flag: `create_export` now checks every `document_id` for a `current_extraction` before
   creating the `Export` row, and raises `DOCUMENTS_NOT_EXPORTABLE` (422, not retryable) naming each
   excluded document by filename + status if any are missing. New error code registered in the closed
   `CODES` table, documented in `API_CONTRACT.md` §6/§8, version bumped to 0.3.4 and added to the
   existing "not agreed with frontend dev" banner — **not shipped to the frontend dev yet, per
   AGENT_RULES §2's extra gate on endpoint/error-code changes.** `ExportCenter.jsx` needed no change;
   it already renders `ApiError.message` in an `Alert`.
4. A failed document showed "still processing" in `DocumentReview.jsx`. Traced one layer past the
   component: `extraction_payload()` (`app/services/documents.py`) raises `NOT_READY` both for a
   genuinely in-progress document and for a terminal `failed` document with no extraction row —
   the frontend can't tell these apart from the extraction call alone. Fixed by having
   `DocumentReview.jsx` fall back to `GET /status` (which returns `document.status` verbatim) only
   when it catches `NOT_READY`, and rendering a distinct "extraction failed, no detail available"
   alert when that status is `failed` — consistent with `/status.error` always being `null`
   (recorded gap, PROJECT_CONTEXT §7): no cause to show, so the copy doesn't imply one exists or
   that waiting helps.
5. Login placeholder (`sarah.jenkins@company.com`) didn't match the seeded `@ptcl.internal` domain.
   Changed to a generic `name@ptcl.internal` — not one of the three real seeded addresses.

**Learned / broke:** `tests/contract/test_api_contract.py::test_download_export_returns_binary[real]`
was failing on `master` independent of the five fixes above (`git stash` + rerun confirmed). Diagnosed
before touching it: `create_export` genuinely runs export generation on a background thread
(`_run_export_soon` sleeps 0.05 s, then the eager Celery task writes the xlsx), and the test
downloaded the file immediately after `POST /exports` with no wait — `GET .../file` correctly
returned `409 NOT_READY` because the artifact wasn't there yet. **The real finding isn't the
assertion, it's why only `[real]` caught it: `tests/mock_server.py` generates exports synchronously
— `EXPORTS[export_id] = {...}` and done, no thread, no delay — so the mock target passed a case the
real target could not.** The contract suite runs every test against both servers specifically so a
mock/real gap can't hide; this one only stayed hidden because the test itself assumed synchronous
completion, which happened to be true of the mock's fake and false of the real pipeline it exists to
model. Fixed the test, not the endpoint: added `_wait_for_export_complete()`, a bounded (5 s) poll of
`GET /exports/{id}` that fails loudly via `pytest.fail` on timeout rather than hanging or racing the
409. The endpoint's `409 NOT_READY` while queued is unchanged and correct.

**Next:** Tell the frontend dev about 0.2.0, 0.3.0, and 0.3.4 (API_CONTRACT banner) — nothing in this
list should ship until that happens. Branch `fix/demo-rehearsal-issues` has all six fixes.

## 2026-08-13 — INV-2 provenance was dead code since ADR-002; fixed with a soft-fail merge stage (ADR-012)

**Touched:** INV-2 · `CodeBase/backend/app/pipeline/provenance.py` (new), `orchestrator.py`
(`attach_provenance` wired in, `_needs_review` now also triggered by an unmatched claim, `_log_provenance`),
`tests/unit/test_provenance.py` (new), `tests/unit/test_orchestrator.py` (+4 tests),
`Docs/decisions/ADR-012-provenance-merge-was-dead-code.md` (new), `Docs/ARCHITECTURE.md` §2 (Stage 5b
+ routing), `Docs/PROJECT_CONTEXT.md` §8

**Did:** A request to spec bbox-highlighting in `DocumentReview.jsx` turned up that no real
extraction has ever carried `source.page`/`source.bbox` — `TextRegion.as_source()` existed and was
unit-tested but was never called; `build_prompt()` discards regions down to plain text before the
LLM ever sees them. Confirmed via `backend/evals/history/*.jsonl` (zero `bbox`/`page` occurrences
across 5 real hosted-LLM run logs) and via a fresh 15-rep real run against the hosted LLM (`evals/repro.py`,
unmodified) across all 3 synthetic invoice fixtures with the new merge applied: 277/283 (97.9%)
claimed quotes resolved to a real bbox. Wrote `attach_provenance()` (exact substring match of a
field's `raw_text` against the reconstructed OCR text, offset-tracked per region) and wired it into
`extract()` right after gates. First design used a hard `raise` on an unmatched claim, mirroring
INV-1's `_assert_money_fields_gated` — reverted before landing per explicit direction: the match is
itself a fallible check and must not be authoritative over the document, same logic as a
`format_only` gate (ADR-004). An unmatched claim is now logged and added as one more path into
`_needs_review()`, never a hard failure.

**Learned / broke:** The one invoice with real misses (`invoice_3_dense_layout`, 103/109) showed the
failure mode is not a whitespace/case mismatch normalization would fix — the model stitched a
non-adjacent column header (`"Qty"`) and a data-row value (`"1"`) into one fabricated-looking quote
that never appears contiguously in the source OCR text. The exact-substring check correctly refused
it. Deferred fuzzy/normalized matching rather than building it speculatively — this run gave no
evidence it would help.

**Next:** `DocumentReview.jsx` bbox-highlight UI is now buildable against real data — not started.
`backend/evals/run_eval.py` still doesn't exist; a golden-set-level coverage regression threshold
(ADR-012's "Revisit when") needs it first.

## 2026-08-12 — frontend wired end-to-end against the real API; `_needs_review`'s vacuous `all()` fixed (ADR-011); full real path reverified clean to `needs_review`

**Touched:** no INV directly (see Learned/broke for what ADR-011 protects) ·
`CodeBase/frontend/documind-ai/**` (API client, Login, UploadCenter, ProcessingQueue polling,
DocumentHistory, DocumentReview incl. source-file preview + in-place PATCH correction, shadcn/ui
restyle), `CodeBase/backend/app/main.py` (CORS middleware), `CodeBase/backend/app/api/v1/documents.py`
(`GET /documents/{id}/file`), `CodeBase/backend/app/pipeline/orchestrator.py`
(`document.document_type` now persisted post-extraction; `_needs_review`'s `if not populated: return
True` — ADR-011)

**Did:** Wired `CodeBase/frontend/documind-ai` end to end against the real backend for the first
time: API client, login, upload, processing-queue polling, real document list, and the review
screen rendering real extraction data with a source-file preview and in-place field correction via
`PATCH` — restyled onto shadcn/ui, gate grouping and the verified/confidence badge distinction
preserved. Backend: added `GET /documents/{id}/file` (streams the raw upload via `FileResponse`,
gated only on auth, never on processing status, never writes to `storage_path` — INV-3), added CORS
middleware for the Vite dev origin (`localhost:5173`), fixed `document_type` to persist onto the
`documents` row after extraction (`orchestrator.py` — it was set once at upload as `"unknown"` and
never updated), and fixed `_needs_review`'s `all()` over an empty populated-fields list returning
vacuously `True` (now `[[ADR-011-terminal-status-requires-positive-verification-evidence]]`). With
the frontend now in place, re-ran the full real path — `paddlepaddle==3.0.0` (pinned 2026-08-10
after `3.3.1`'s oneDNN crash, see that entry) still holds — end to end: upload → PaddleOCR → hosted
LLM → gates → persist → rendered in the new review screen. Both line items extracted this run
(2026-08-10's run dropped one); `line_item_sum` and `arithmetic_reconciliation` both passed;
document reached `"needs_review"`.

**Learned / broke:**
- `_needs_review`'s `all(entry.get("verified") for entry in populated)` is vacuously `True` over an
  empty sequence — `all([])` — so an extraction that populated *no* fields at all (not "all fields
  unverified," genuinely none) satisfied the check and reached `"complete"` with
  `review.required: false`. That's backwards: terminal status must come from positive verification
  evidence, not merely the absence of an unverified field. Fixed to require at least one populated,
  gate-verified field before `"complete"` is reachable.
- Clearing a field in the review screen sends `value: null` in the PATCH body, not `""` — traced
  end to end: the frontend maps an emptied input to `null` before sending, and the backend's
  `CURRENT_EXTRACTION_VIEW` query (`app/db/queries.py`, unchanged this session but exercised
  end-to-end for the first time) renders that as JSON `null` via `to_jsonb`, while still stamping
  `verified: true, source.origin: "human"`. A human asserting "this field is genuinely absent" is a
  legitimate verified state, distinct from both "never extracted" and "unverified" — collapsing it
  to an empty string would have made a deliberate human judgment indistinguishable from an untouched
  field.
- A separate agent session working in the same tree left unapproved changes uncommitted — a
  repo-wide `@/...` → relative-import rewrite (the alias was never broken; `vite.config.js` still
  defines it) and an `index.css` rewrite that dropped both `@layer base` wrappers, the global
  `* { @apply border-border }` rule, and the `.animate-laser` keyframe. It sat mixed in with
  approved edits in the same working tree, close enough to riding into a commit that it had to be
  separated out by hand (`git stash`, then reconstructing the approved-only diff file by file, since
  the alias rewrite and the CSS rewrite touched some of the same files as the approved fixes). Read
  the diff before committing, every time — a passing build is not evidence a diff is small or clean.

**Next:** none of today's four known gaps (PDF upload path, silent `/status.error`, unbuildable
NTN/STRN gates, ADR-009's arithmetic-identity blind spot) are fixed — recorded in
`PROJECT_CONTEXT.md` §7 this session, not addressed.

## 2026-08-10 — first full real-path run: real OCR, real hosted LLM, real gates, 34.41s to `needs_review`

**Touched:** no INV · `backend/pyproject.toml`, `backend/uv.lock` (`ocr` group pins
`paddlepaddle==3.0.0`)

**Did:** installed the `ocr` extra (`uv sync --group ocr`) and ran the real path end to end for
the first time — Redis up, `celery -A app.workers worker -l info --pool solo` against it with
`CELERY_TASK_ALWAYS_EAGER=false`, real `uvicorn`, a rendered PNG of `invoice_1_simple.txt`
uploaded through `POST /api/v1/documents`. First attempt (`paddleocr>=3.0`'s resolved
`paddlepaddle==3.3.1`) crashed inside PaddlePaddle's own oneDNN-backed new-executor —
`NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support
[pir::ArrayAttribute<pir::DoubleAttribute>]` — after successfully downloading model files from
HuggingFace but before producing any OCR output. Pinning `paddlepaddle==3.0.0` avoided the crash.
Re-ran: task received, real PaddleOCR ran, real `qwen/qwen-2.5-7b-instruct` call went out, real
gates ran, document reached `"needs_review"` in **34.41s** wall time from upload to terminal
status.

**Learned / broke:** three things this run surfaced that no fixture-text or fake-LLM run could
have:

- `otc` came back `"5000.00"`, sourced from `"Installation Charges\n5000.00"` — the exact
  verbatim-label violation [[ADR-010-mrc-otc-require-a-verbatim-field-label]] was written about,
  now reproduced through a genuinely real OCR→LLM path rather than a fixture read directly as
  text. The defect isn't fixture-specific; it survives real OCR noise.
- `line_item_sum` failed for real: `"line items sum to 20000.00, subtotal is 25000.00"` — the
  model extracted only the `Fibre Link 100 Mbps` line item and dropped `Installation Charges`
  entirely from `line_items`, even though it separately (and wrongly) surfaced that same line's
  value as `otc`. A dropped line item and a misattributed field from the same missing information,
  in the same run — the gate caught the arithmetic consequence live, which is exactly what
  `line_item_sum` is for.
- Real PaddleOCR misreads appeared that no synthetic-text fixture run would ever produce:
  `"Bill Tα Karachi Textile Mills"` (`To` → `Tα`) and `"PTCL Fiber Solutions (Pyt) Ltd"` (`Pvt` →
  `Pyt`) — artifacts of Pillow's rendered font, not the pipeline, but a reminder that every
  fixture-text run this session ran the LLM stage only, never the OCR stage, and OCR has its own
  error surface layered on top.

**Next:** `paddlepaddle==3.3.1`'s oneDNN crash was not root-caused inside PaddlePaddle itself —
pinning to `3.0.0` was the smallest change that unblocked OCR here, not a diagnosis of why `3.3.1`
fails on this machine specifically. `otc`'s verbatim-label violation and the dropped line item are
both now confirmed live, not just diagnosed from static text — worth prioritizing over further
infra work once prompt/schema tuning resumes, since [[ADR-010-mrc-otc-require-a-verbatim-field-label]]
already named the rule and this run shows it still fails at the same rate under real conditions.

## 2026-08-10 — W7: extract_document Celery task wired to the real orchestrator; a real bug found by running the real path

**Touched:** no INV · `backend/app/workers/{__init__,celery_app,tasks}.py` (new),
`backend/app/services/documents.py` (`enqueue_extraction` no longer a no-op),
`backend/app/core/config.py` (`celery_broker_url`, `celery_result_backend`,
`celery_task_always_eager`), `backend/pyproject.toml` (`celery.*` mypy override),
`backend/tests/contract/conftest.py` (fake OCR/LLM factories installed for `real_app`,
`MOCK_ONLY` emptied)

**Did:** `extract_document` fetches the `Document`, sets `status="extracting"`, calls
`run_and_persist` (the existing orchestrator, untouched) with OCR/LLM built from swappable
module-level factories, and lands on a terminal status. `enqueue_extraction` dispatches through
it instead of doing nothing. `celery_task_always_eager` **defaults to `True`** — no broker or
worker is deployed anywhere yet ([[ADR-006-two-deployment-profiles]]) — so under the default,
`test_status_progresses_queued_to_complete[real]` exercises in-process execution via a tracked
background thread in `enqueue_extraction`, joined at test teardown before the next test's DB
truncate, **not a real broker**. That thread only runs on the eager path; it is never reached
when `celery_task_always_eager=False`.

**The real path was verified manually, not just asserted:** `backend-redis-1` started, `celery -A
app.workers worker -l info` run against it with `CELERY_TASK_ALWAYS_EAGER=false`, real `uvicorn`
against real Postgres, a synthetic invoice (rendered PNG of `invoice_1_simple.txt`) uploaded
through the real API. Worker log confirmed task receipt
(`Task app.workers.extract_document[...] received`) and the document reached a terminal status —
`"failed"`, because `paddleocr` is not installed in this environment (the same gap already named
in the prior session's step 4 report), not a defect in this change.

**Learned / broke:** that manual run caught a real bug the contract-test fakes never could —
`ModuleNotFoundError` from the OCR loader is not an `OrchestratorError`, so the original `except
OrchestratorError` in `extract_document` never fired, and the document was left stuck at
`"extracting"` forever with no terminal status and no recorded error. `backend/CLAUDE.md`'s
"assume the worker will die mid-task" line was not fully honored on the first pass. Fixed with a
catch-all `except Exception` that sets `"failed"`, commits, logs, and re-raises so Celery still
records the failure. `ruff`/`mypy`/`281 passed` reconfirmed clean after the fix, then the manual
run repeated and reached `"failed"` cleanly instead of hanging.

**Next:** the eager-thread mechanism stays in place — removing it would regress
`test_status_progresses_queued_to_complete[real]` back to the earlier bug, since the contract
suite has no Redis or worker process of its own. Making it unnecessary would mean giving the
contract suite real broker/worker infrastructure, which is a bigger change than this session's
scope and wasn't requested. `paddleocr` remains uninstalled here, so no real-OCR run has ever
reached `"complete"` in this environment — only the fake-backed contract test has, and only
because its fake extraction populates solely a gate-covered field (`iban`) by design (per
`_needs_review`'s all-populated-fields-must-be-verified rule, `"complete"` is unreachable for any
real document today given current gate coverage — the 2026-08-08 entry already found every real
run routes to `needs_review`, and nothing here changes that).

## 2026-08-10 — hand-derived golden labels for the three synthetic fixtures; NTN has no schema field

**Touched:** no INV · `backend/evals/golden/dev/labels/invoice_1_simple.json`,
`invoice_2_recurring_service.json`, `invoice_3_dense_layout.json` (new — content produced this
session, files placed by Adeen; see Learned/broke)

**Did:** hand-derived all 17 `EXTRACTION_SCHEMA.json` `fields` values for each of the three synthetic
invoice fixtures, reading only the fixture text — no model run, no `evals/history/*.jsonl` consulted.
Applied `ADR-010-mrc-otc-require-a-verbatim-field-label`: `mrc`/`otc` are `null` on invoice 1 and
invoice 3 (no verbatim label in either document) and populated on invoice 2 (`MRC:`/`OTC:` both
explicitly labeled). One field was flagged ambiguous rather than guessed — invoice 2 carries no
explicit `Vendor:` label, only an unlabeled header (`PTCL Corporate Billing`); Adeen resolved it,
choosing the header string as `vendor_name`. Dates normalized to ISO per
[[EVAL_AND_GOLDEN_SET]] §3's matching rule (`01-Feb-2026` → `2026-02-01`, etc. — invoice 1 and 3 were
already ISO in source). IBAN normalized (whitespace stripped, uppercased). Invoice 3's OCR-noise
internal spaces in `po_number`/`invoice_number`/`service_type`/`notes` collapsed to single spaces as
a transcription judgment call, not a value correction.

**Learned / broke:** `EXTRACTION_SCHEMA.json`'s `fields` block has **no `ntn` or `strn` field**, even
though the gate registry enum names `ntn_format_check` and `strn_format_check`
(`EXTRACTION_SCHEMA.json` line 142) and `invoice_3_dense_layout.txt` carries a real NTN value
(`1234567-8`). Those two gates can never fire on any document, real or synthetic, because nothing in
the schema extracts a value for them to check — a gate exists with no field to feed it. Not fixed
here, per instruction; recorded so it isn't mistaken for an oversight later, and so it's visible
before anyone next touches the gate registry or NTN/STRN handling.

Separately: `evals/golden/**` is Read/Edit/Write-denied for Claude Code sessions in
`.claude/settings.json`. The three label files above could not be written directly this session —
their content was handed to Adeen, who placed them. Worth naming as a positive result, not just an
obstacle: `EVAL_AND_GOLDEN_SET` §2's held-out rule (nothing that might tune against golden data
touches it casually) is enforced by that deny rule literally, and it held.

**Next:** same open items as the entry above (frontend PR blocked on API_CONTRACT 0.2.0; orphan
`backend-celery_*` compose containers to check before W7). Additionally: the `ntn`/`strn` schema gap
means no golden label can ever score those two gates until the schema gains the fields — a second,
more specific blocker on top of W12's harness still not existing to consume these three `dev` labels
at all.

## 2026-08-10 — repro harness persists raw N=20 runs; ADR-010 names the verbatim-label rule; earlier null/modal report retracted

**Touched:** no INV · `backend/app/pipeline/llm/transport.py`, `backend/evals/repro.py`,
`backend/evals/history/*.jsonl`, `backend/tests/unit/test_repro.py`,
`Docs/decisions/ADR-010-mrc-otc-require-a-verbatim-field-label.md`, `Docs/AGENT_RULES.md` §2,
`Docs/INDEX.md`, `Docs/PROJECT_CONTEXT.md` §8

**Did:** built the repro harness with persisted per-rep raw responses — every rep's raw content, `id`,
and `provider` (and, for the last two runs, the full response body) now land in
`evals/history/*.jsonl` instead of only ever reaching an in-memory summary. `HostedChatTransport`
gained optional `seed` and `provider_order` fields, sent as `seed` and
`{"provider": {"order": [...], "allow_fallbacks": false}}` when set, with a new `complete_full()`
method returning content plus the full body so `id`/`provider` survive to the caller;
`__call__`'s existing `Callable[[str], str]` contract, and `client.py`, were left untouched. ADR-010
written, naming the verbatim-label rule for `mrc`/`otc` without deciding an enforcement mechanism.

**Learned / broke:**

- `prompt_builder.py:24` injects `EXTRACTION_SCHEMA.json` into the prompt at runtime via
  `model_output_schema()` — a `description` edit there is a prompt change, not a docs change, and
  needs a live N≥20 check before landing, same as any other prompt change would.
- `seed` was never echoed back in the response body across 21 calls spanning both OpenRouter
  providers seen this session (Together, Phala) — no `seed` field, no stable `system_fingerprint`,
  on any of them. Pinning the provider narrowed the `otc` null/`5000.00` flip (Together: 1/20; Phala:
  5/20) but did not remove it. `ADR-006`'s determinism-banner amendment stands as written.
- The earlier "16/20 null, 4/20 5000.00, 80% modal" report had no persisted run behind it — the
  original harness never wrote raw responses anywhere, and no log or journal entry from that run
  exists either. Retracted as unfounded, not reconciled against fresh data.

**Next:** the frontend PR is blocked on API_CONTRACT 0.2.0 gate rendering — the frontend dev still has
not confirmed reading it. Orphan `backend-celery_*` compose containers need checking before W7 lands.
Zero golden labels still blocks every accuracy claim in `EVAL_AND_GOLDEN_SET`.

## 2026-08-08 — three fixes from the live baseline: schema-aware repair, a chosen prompt fix, an ADR-006 banner

**Touched:** INV-2, INV-6 (indirectly, via the ADR-006 banner) · `backend/app/pipeline/orchestrator.py`
(`_format_validation_error`, new), `backend/tests/unit/test_orchestrator.py` (two new tests),
`backend/app/pipeline/llm/prompts/extract_v1.txt`, `backend/tests/unit/test_prompt_builder.py` (one
new text-presence guard), `Docs/decisions/ADR-006-two-deployment-profiles.md` (banner only)

**Did — Fix 1, schema-aware repair:** `_validate_model_output`'s error message used to read
`['fields', 'mrc', 'source', 'raw_text']: None is not of type 'string'` — Python list-repr path,
jsonschema's raw phrasing. `_format_validation_error` now produces `fields.mrc.source.raw_text must
be of type string, got null` for `type` failures (dotted path, `json.dumps(instance)` so `None`
reads as `null` inside an otherwise-JSON prompt) and falls through to jsonschema's own `.message` for
every other validator kind. `repair.py` needed no change — `validate()`'s raised message already
flows straight into the repair prompt via `str(exc)`. Two new orchestrator tests exercise the
schema-valid-but-rejected repair/exhaust pair with the real validator, next to the existing
malformed-JSON pair — "test both paths separately" from the request, now both covered.

**Did — Fix 2, the mrc/otc/billing_terms hallucination, tried one at a time as instructed:**

- **(a) few-shot example + explicit "don't infer from a nearby field" rule, added to
  `extract_v1.txt`.** Live run, all three fixtures: invoice 1's `mrc`/`otc` went from hallucinated
  (copied from subtotal/tax) to correctly `null` — **fixed**. Invoice 2's genuinely-present
  `mrc`/`otc`/`iban` stayed correct — **no regression**, the thing asked to watch for. Invoice 3
  unchanged (already correct). `billing_terms` was *not* fixed by (a) despite being named in the
  instruction text — still duplicated from `notes`. One notable, not-fully-explained side effect:
  invoice 3's IBAN, dropped in every prior run (baseline and both temperature=0 reps), was extracted
  this run and its deliberately-bad checksum correctly failed `iban_checksum` — the scenario that
  fixture was built to test, finally exercised live. Reported as observed, not claimed as caused by
  (a) — the endpoint's non-determinism (documented in the entry below) means one run isn't enough to
  attribute this to the prompt change specifically.
- **(b) `description` fields added to `mrc`/`otc` in `Docs/EXTRACTION_SCHEMA.json`** (additive-only,
  flows into the prompt automatically via `model_output_schema()`, no `schema_version` bump — a
  `description` changes no validation behavior, confirmed via `Draft202012Validator.check_schema`
  before and after). Live run: **invoice 1 failed outright**, twice out of three attempts across two
  follow-up reps — a new failure mode never seen in any prior run (baseline, either temperature=0
  rep, or candidate (a)): the model nested `line_items` *inside* `fields`, which
  `additionalProperties: false` on `fields` correctly rejects. Fix 1's repair message was readable
  (`fields: Additional properties are not allowed ('line_items' was unexpected)`) and repair was
  attempted, but the model repeated the same structural mistake on the retry both times it happened.
  On the one rep that succeeded, `mrc`/`otc` were correctly omitted — so (b) *can* fix the target
  defect, but at an observed ~2-in-3 hard-failure rate on invoice 1 that (a) never showed once.
- **Kept: (a). Reverted: (b).** Not because (b) can't work, but because (a) achieved the same fix
  with zero observed failures against (b)'s unreliability — and (a) is the only one that even
  attempts `billing_terms`, which neither fully solved. `billing_terms` hallucination is unresolved
  and not otherwise in scope of this session; worth its own pass.
- New test: `test_build_prompt_text_still_warns_against_inferring_mrc_otc_from_nearby_fields` in
  `test_prompt_builder.py` — explicitly a text-presence guard against accidental deletion, not a
  claim about model behavior. Live-run evidence is what proves behavior; that evidence lives in this
  entry, not in a unit test's assertions.

**Did — Fix 3:** amendment banner added to `ADR-006-two-deployment-profiles.md`, matching ADR-002's
self-contained precedent — no new ADR file, Decision/Reason/Consequences sections untouched, frontmatter
version left at `1.0.0` (same precedent ADR-007's banner set: banners don't bump the amended file's
own version). Records that `temperature=0` does not give determinism on OpenRouter and is explicit
that INV-6 and the DB's append-only structural guarantee are unaffected — what's undercut is the
weaker, informal expectation that same-`pipeline_version` extractions are value-comparable, which was
never INV-4's literal claim but is an assumption this finding disproves for the hosted-endpoint case.

**Verification, evidence quoted:**
```
ruff check .            → All checks passed!
ruff format --check .   → 51 files already formatted
mypy                     → Success: no issues found in 30 source files
pytest tests/unit tests/contract -q  → 270 passed, 1 skipped, 1 warning in 12.24s
pytest tests/integration -q          → 41 passed in 2.54s
```

**Learned / broke:** the A/B procedure earned its keep — (b) looked like the smaller, safer change
(pure metadata, no prompt bloat) and would have been the natural first choice on paper. Only running
it live, and specifically re-running the one document that mattered when the first result looked
odd, surfaced that it was the less reliable of the two. "Which change is smaller in the diff" and
"which change is safer in practice" are not the same question for a stochastic dependency, and this
session is the concrete case for why the instruction to test one variable at a time, live, mattered.

**Next:** `billing_terms` hallucination remains open. Whether invoice 3's IBAN extraction under (a)
was prompt-caused or coincidental non-determinism is unresolved — would need repeated reps to settle,
not done here since it wasn't the target defect. Prompt/schema tuning beyond fix 2's kept change is
still out of scope until asked for.

## 2026-08-08 — temperature=0 confirms one defect, disproves another as noise; ADR-009; a stale merge conflict found committed on master

**Touched:** no INV directly (eval/gate design questions only) · `Docs/decisions/ADR-009-omission-is-invisible-to-the-gate-layer.md`
(new), `Docs/PROJECT_CONTEXT.md` §3 (merge-conflict resolution), §8, `Docs/INDEX.md`,
`Docs/EVAL_AND_GOLDEN_SET.md` §3

**Did:** `HostedChatTransport.temperature` already defaulted to `0.0` — the original baseline run was
already at temperature 0, nothing needed changing there. Ran `tools/run_demo_extraction.py` twice
more, fresh, to compare against that baseline and against each other.

**Findings — one defect confirmed reproducible, one confirmed as real (not sampling) non-determinism:**

- **Invoice 1's `mrc`/`otc`/`billing_terms` hallucination is fully deterministic**, byte-for-byte
  identical across all three runs (baseline, and both new ones): `mrc: "25000.00"` copied from
  `subtotal`, `otc: "4250.00"` copied from `tax`, `billing_terms` duplicated from `notes` — same
  values, same (wrong) `source.raw_text` quotes, every time. This rules out sampling noise as the
  explanation and points at the prompt or the model's prior, not luck.
- **Invoice 3's dropped IBAN also survived all three runs** — the model never once extracted `iban`
  for that document, including a run where it had a repair retry and still didn't produce it.
  Reproducible, not noise.
- **But invoice 3 was not deterministic overall.** The second fresh run failed outright:  both the
  original attempt and its one repair retry emitted `"raw_text": null` for the absent `mrc`/`otc`/
  `billing_terms` fields — literal JSON `null`, not a string and not an omitted key — which
  `$defs/source` has always required to be a string when present. Schema validation rejected both
  attempts, `complete_with_repair` exhausted, and the whole document failed with no extraction at
  all. The baseline and the first fresh run both handled the identical absent-field case correctly,
  quoting a short label (`"MRC"`, `"OTC"`, `"Billing Terms"`) as `raw_text` instead. Same prompt, same
  model, same `temperature=0`, three different behaviours on the same document — confirming the
  premise of the ask: this provider does not guarantee determinism at `temperature=0`.
- Invoice 2 was clean and identical across all three runs, as before.

**ADR-009 written**, per instruction, on the separate design question the dropped IBAN exposed:
gates only ever see what's present in `fields`, so a field the model silently drops is
indistinguishable, at the gate layer, from a field genuinely absent from the document —
`iban_checksum` returned `format_only` both times, for opposite reasons, and nothing downstream could
tell which. INV-1/INV-5 protect precision, not recall; closing this gap is W12's job (per-field
recall and a present-vs-absent breakdown), not a new gate — inventing a "field X should be present"
rule without ground truth is the same shape-as-truth mistake this repo has already made three times.
`EVAL_AND_GOLDEN_SET.md` §3 amended accordingly: a precision-only eval report does not satisfy the
harness's own stated purpose.

**Learned / broke — a real problem found while starting this task, not caused by it:** before running
anything, `git status`/`git log`/`git reflog` showed the branch had moved from `chore/agents-file` to
`master` and picked up two squash-merged PRs, entirely outside this session — expected, that work
belongs on GitHub. What was not expected: `Docs/PROJECT_CONTEXT.md` §3, as committed on `master` (and
already pulled from `origin/master`), contained **literal, unresolved `<<<<<<< HEAD` / `=======` /
`>>>>>>> origin/master` conflict markers**, mixing this repository's current, ADR-006/007-consistent
stack description with a stale one describing a real L20 and a local-only LLM — hardware and a
deployment shape ADR-006 explicitly says never existed. Somewhere in a PR's merge, a conflict was
left unresolved and got committed (likely squashed) as literal file content rather than fixed before
commit. Resolved by keeping the current, correct version and deleting the stale one and the markers;
swept the rest of `Docs/` and `CodeBase/` for the same pattern and found nothing else. Worth a general
lesson: `git status` reporting "clean" says nothing about whether a *committed* file still contains
unresolved conflict text — that only shows up by reading the file.

**Next:** prompt tuning is still explicitly deferred — nothing about the hallucination, the dropped
IBAN, or the `raw_text: null` schema violation has been fixed. When tuning does start, the `raw_text:
null` case is probably the cheapest first fix (the schema could simply allow `null` as well as
omission, or the prompt could be more explicit that omitting the key is mandatory) — but that is a
decision for the tuning session, not this one. W12 remains unwritten; ADR-009's requirement is not
enforceable until it exists.

## 2026-08-08 — W4/W5: real hosted transport, real prompts, first live run — unimproved baseline

**Touched:** INV-1, INV-2, INV-5, INV-6 · `backend/app/pipeline/llm/transport.py` (new),
`backend/app/pipeline/llm/repair.py` (new), `backend/app/pipeline/llm/prompt_builder.py` (new),
`backend/app/pipeline/llm/prompts/extract_v1.txt` (new — first real file in a directory that was
`.gitkeep` only), `backend/app/schemas/extraction.py` (`model_output_schema()`, shared, non-circular),
`backend/app/pipeline/orchestrator.py` (wired to the two above, replacing the placeholder prompt and
direct-parse call), `backend/app/core/config.py` (`hosted_llm_*`, `llm_max_repair_retries`),
`backend/.env.example`, `backend/tests/fixtures/invoices/` (three hand-authored synthetic invoices,
new), `backend/tools/run_demo_extraction.py` (new, dev-only), `Docs/ARCHITECTURE.md` §2

**Did:** `HostedChatTransport` is a thin OpenAI-compatible chat-completions caller (`httpx.Client`
injected, `max_tokens` capped at 2000) sitting under the existing, untouched INV-6 guard —
`assert_releasable` still runs inside `LLMClient.complete` before any transport call, and the guard's
own tests were not touched. `complete_with_repair` retries exactly once on malformed JSON or a
schema-validation failure, building a repair prompt that quotes the bad output and the error back to
the model; a guard refusal or a raw transport error is deliberately **not** caught by that loop and
propagates immediately — retries are for the model's output, not for infrastructure or INV-6. The
prompt is a real file now (`prompts/extract_v1.txt`), interpolated with the OCR text and the *live*
`EXTRACTION_SCHEMA.json` (via a new shared `model_output_schema()` in `schemas/extraction.py`, reused
by both the prompt and the orchestrator's own validator) so the two can never disagree.

Three English invoices written by hand as OCR-text fixtures (not rendered images — real image
generation is ADR-008/W0, not this session): a simple one-off equipment invoice, an MRC/OTC recurring
service invoice, and a deliberately noisy/misaligned layout carrying a CNIC, an NTN, and an IBAN whose
checksum digit is wrong on purpose (`PK70BANK...`, the same known-bad IBAN used in
`test_iban_gate.py`) — meant to exercise a live `iban_checksum` failure.

**First live run, `qwen/qwen-2.5-7b-instruct` via OpenRouter, unmodified prompt, as instructed — not
tuned:**

- The configured slug (`Qwen/Qwen2.5-7B-Instruct`, copied from the `VLLM_MODEL` convention) does not
  exist on OpenRouter; resolved by querying `/models` — the real slug is lowercase and hyphenated,
  `qwen/qwen-2.5-7b-instruct`. Confirmed with a 10-token round trip before spending the real prompt.
- All three JSON responses were valid on the **first** attempt — `complete_with_repair`'s retry path
  never fired against a real model in this run, so it remains verified only against fakes.
- **Invoice 1 hallucinated `mrc` and `otc`.** The document has no MRC/OTC billing at all (a one-time
  equipment invoice), but the model copied `subtotal` into `mrc` and `tax` into `otc`, reusing the
  same `source.raw_text` for both pairs — not a misread, an invented field association. The prompt
  explicitly says to omit or null a field that is not present; the model did that correctly for
  `mrc`/`otc` on invoice 3 (no MRC/OTC line there either) and incorrectly on invoice 1. Same missing
  data, two different behaviors in the same run — worth naming as it happened, not smoothed over.
  Invoice 1 also invented a `billing_terms` value by duplicating `notes`, another field genuinely
  absent from the source.
- **Invoice 3 dropped the IBAN entirely.** The line `Bank   IBAN :  PK70 BANK 0000 0012 3456 7890` is
  present and was correctly read for every other adjacent field (CNIC, NTN, dense multi-column
  layout survived intact) — but `iban` never appears in `fields`, so the gate that was supposed to be
  exercised live (`iban_checksum` → `failed` on the deliberately-bad checksum) instead saw an absent
  field and returned `format_only`. The scenario this fixture was built to test did not run.
- **Invoice 2 was clean** — every field correct, including `mrc`/`otc`/`iban` all present and correct,
  `iban_checksum` passed for real. This is the useful negative control: it rules out "the model can't
  handle mrc/otc" as an explanation for invoice 1's hallucination — it's document-shape-dependent, not
  universal.
- Money formatting, decimal places, and every gate-computable arithmetic identity were correct on all
  three documents — the model did not fabricate a wrong total anywhere it was checked. The 7B model
  was reliable on arithmetic transcription and unreliable on knowing what wasn't there.
- **Every document routed `needs_review`, on all three runs** — not because anything failed, but
  because `po_number`, `customer_name`, `vendor_name`, `cnic`, `service_type`, dates, `notes` etc.
  have no registered gate, so they can never be `verified: true`, and `extract()`'s routing rule
  requires *every* populated field verified to reach `complete`. Expected given today's two-gate
  registry (`iban_checksum`, `arithmetic_reconciliation`) — not a defect in this session's code, but
  it means "complete" will stay rare until W9/W10's gates exist.
- **Cost:** 3 calls, 10,097 tokens total, **$0.0030** for all three documents (OpenRouter-reported,
  not estimated). `HostedChatTransport`'s `max_tokens=2000` cap was not hit by any response.

**Learned / broke:** nothing was fixed on purpose. Per instruction, this is the unimproved baseline —
prompt content, `source.raw_text` grounding (real OCR-substring quotes, not fabricated bounding
boxes), and the retry-on-malformed-JSON path are all still exactly as first written. The two live
defects (mrc/otc hallucination, dropped IBAN) and the routing-is-almost-always-`needs_review`
consequence of sparse gate coverage are now recorded facts to prompt-tune or gate-build against next,
not guesses.

**Next:** prompt tuning against these three documents (still not the real generator — that's W0);
decide whether `source.raw_text` should be cross-checked against the actual OCR text server-side
(the model could quote text that was never in the document, and nothing currently catches that); the
repair-retry path has never fired against a real model and should be forced once, deliberately, to
confirm the second attempt behaves as designed; W9/W10's gates are what will make `complete` reachable
at all for a normal document.

## 2026-08-07 — the orchestrator: first code that connects OCR, LLM and gates

**Touched:** INV-1, INV-2, INV-4, INV-5, INV-6 · `backend/app/pipeline/orchestrator.py` (new),
`backend/tests/unit/test_orchestrator.py` (new), `backend/tests/integration/test_orchestrator_e2e.py`
(new), `backend/app/db/documents.py` (`DocumentRecord.storage_path`, new field),
`backend/tests/unit/test_document_record.py`, `backend/pyproject.toml` (`jsonschema` and
`types-jsonschema` moved out of the dev-only group), `Docs/ARCHITECTURE.md` §2,
`Docs/PROJECT_CONTEXT.md` §3, `CodeBase/backend/CLAUDE.md`

**Did:** built the piece the 2026-08-05 sessions kept finding absent — nothing previously called
`paddle.py`, `llm/client.py`, `gates/iban.py` or `gates/arithmetic.py` outside each module's own unit
test, and every `Extraction` row in the database had been put there by the seeder, never by the app.
`extract()` is a pure function (`DocumentRecord` in, `ExtractionOutcome` out — OCR, LLM and the gate
registry all injected); `run_and_persist()` wraps it with a `Session`, writes the `Extraction` row and
sets `documents.status`. It does not import Celery and does not know a worker will eventually call it.

Schema validation runs on the LLM's raw JSON (`document_type`/`language`/`fields`/`line_items` only)
against a schema built from `EXTRACTION_SCHEMA.json`'s own `$defs`, before `document_id`,
`pipeline_version`, `status` and `gates` are stitched on — a field missing `source` or `confidence`
fails the whole stage, not just that field. Every field's `verified` is force-reset to `false` after
validation regardless of what the LLM claimed; only a `passed` gate result can set it back. The gate
registry (`DEFAULT_GATES`) is an explicit tuple, not import-scanning — appending to it is the whole
integration cost for a new gate module. Before persisting, every top-level money field (read off the
schema's `money_field` refs, not hand-listed) must carry a non-null `gate`, or `run_and_persist`
refuses to write the row. Routing is `complete` only if every populated top-level field ends up
verified, else `needs_review`.

167 unit tests (12 new), 41 integration tests (3 new) against real Postgres — including a same-document
rerun proving two independent rows, not an update, and an unmodified `app/export/xlsx.py` reading the
orchestrator's own output correctly. `ruff check` / `ruff format --check` / `mypy` / `pytest tests/unit
tests/contract` all clean: `238 passed, 1 skipped in 9.26s` (the one skip is the pre-existing, documented
`test_status_progresses_queued_to_complete` real-app skip — unrelated to this change).

**Learned / broke:** `jsonschema` had been a dev-only dependency since the contract suite adopted it —
correct at the time, since nothing shipped used it. It now has to run inside `app/` at request time
(schema validation is a pipeline stage, not a test), so it moved to a real dependency; `types-jsonschema`
went with it for `mypy --strict`. A dependency's classification is a claim about who calls it, and that
claim changed the moment the orchestrator did.

The harder design question was what "every field carries confidence and a source span" (INV-2) and "no
money value is persisted without a gate verdict" (INV-1) mean operationally, since neither gate module
annotates anything below the top-level `fields` object. Resolved by scope, not by extending the gates:
`write_workbook` only exports top-level fields, never `line_items`, so INV-1's "reaches Excel unchecked"
is about top-level money fields specifically, and the coverage check is scoped there. A field with two
gates touching it (e.g. `subtotal`, touched by both `line_item_sum` and `arithmetic_reconciliation`)
resolves `verified` as the AND of every touching gate's verdict, and `gate` names whichever ran last —
tested, not left implicit.

**Next:** the orchestrator is real but unreached — nothing calls `run_and_persist` from the API or a
worker yet, so an uploaded document still never leaves `queued` in the running app (Celery, W7 in the
prototype roadmap). `llm/prompts/` is still empty; `build_prompt` is a minimal placeholder that joins OCR
region text and asks for JSON — real prompt engineering, and grounding `source.bbox` back onto OCR
regions rather than trusting whatever the LLM claims, is separate future work. Only `iban_checksum` and
`arithmetic_reconciliation` are registered in `DEFAULT_GATES`; `date_parse`, `currency_consistency`,
`cnic_format_check`, `ntn_format_check`, `strn_format_check` don't exist as modules yet, so any document
carrying those fields will always route to `needs_review` regardless of correctness — expected given the
project's bias toward flagging over guessing, but worth naming so it isn't mistaken for a bug later.

## 2026-08-05 — documentation pass: Synthdog-RTL verified, ADR-008, DATASETS, staleness sweep

**Touched:** no INV directly · `Docs/DATASETS.md` (new),
`Docs/decisions/ADR-008-synthetic-generation-is-a-component.md` (new),
`Docs/decisions/ADR-002-two-stage-ocr.md` (amendment banner), `Docs/PROJECT_CONTEXT.md` §3 §7 §8,
`Docs/ARCHITECTURE.md` §1 §2 §4, `Docs/EVAL_AND_GOLDEN_SET.md` §2 §4 §5, `Docs/INDEX.md`,
`CodeBase/backend/CLAUDE.md`, `CodeBase/backend/.env.example`

No code changed. Documentation only.

**Did:** cloned Synthdog-RTL at `15e9d1f` and read all 528 lines rather than the README. Wrote
ADR-008 (requested as 007 — that number was taken earlier the same day) and `DATASETS.md`. Swept
every doc against the code as it now stands.

**Learned / broke — four findings, three of which change what we thought.**

**Synthdog-RTL does none of the three things it was being planned around.** No field boxes: the only
geometry it computes is the page quad at `template.py:70`, and `save()` binds it and never writes
it; per-token layers are destroyed by `Group(...).merge()` at `textbox.py:42`. No structured JSON:
`keys=["text_sequence"]` at `template.py:99` — it emits Donut's `gt_parse` *envelope* around a
single flat string, which is almost certainly why one source read it as "Donut-style JSON". Not even
line-level: `label = " ".join(texts)` concatenates every textbox on the page. And no bidi at all —
`get_display` is imported at `template.py:15` and never called, RTL is a right-to-left *word
advance* that would reverse English word order in a mixed line, the shipped corpus has zero Latin
characters, and the fonts are Nastaliq-only. **The `bidirectional: 0` in the configs is a shadow
effect parameter**, which is the likeliest single cause of the three-way disagreement: it reads
exactly like a text-direction switch.

**The Qaari news dataset is missing the letter آ.** Entirely. Zero occurrences across 11 sampled
rows while dozens of words require it — `مارشل رٹ` for `مارشل آرٹ`, `کسیجن` for `آکسیجن`, `رڈیننس`
for `آرڈیننس`, `ئل` for `آئل`. ؤ (U+0624) looks affected too. This matters more than the
contamination worry that prompted the check: a CER against these labels *rewards* dropping a common
Urdu character, and if Qaari trained on them it has learned to drop it. Sample size is 11 rows and a
full count was not run — that count is the first thing anyone using this corpus should do.

**The contamination hypothesis was half wrong and the conclusion survived anyway.** The model card
says the training set was 10,000 *synthetic* images; the news dataset is 35.9 K *real news*. They
cannot be the same corpus. Recorded in `DATASETS` §4 as a conflict rather than resolved. But the
card names **no evaluation set at all** for its headline 0.048 WER, so the number was never
attributable regardless — which is a better reason than the one we started with.

**Qaari yields no bounding boxes, and ADR-002 assumed it does.** ADR-002 says "whatever runs here
has to yield boxes, not just text" and then selects Qaari, which is a LoRA adapter on Qwen2-VL-2B
prompted for plain page text. The two-stage design survives — PaddleOCR supplies every box, Qaari
replaces only the string inside one — but the unanticipated consequence is that **an Urdu region
PaddleOCR fails to detect is invisible to the whole pipeline**, because nothing else produces
regions. ADR-002 got a banner; its reasoning is untouched.

**Staleness found and fixed:** `.env.example` pointed `QAARI_MODEL` at `NAMAA-Space/Qaari-0.1-Urdu`,
an org that does not exist — the model is `oddadmix/Qaari-0.1-Urdu-OCR-VL-2B-Instruct`. Nobody would
have noticed until the first Urdu run failed to download. `backend/CLAUDE.md`'s layout block
predated `app/services/`, `app/main.py` and half of `app/db/`. `ARCHITECTURE` §2 listed four tables
where there are six. `EVAL` §4's load test is specified against an L20 that does not exist, and §5
describes a harness — `run_eval.py`, `scorers.py` — that has never been written, while
`backend/CLAUDE.md` lists it as a runnable command. That last one is the sharpest: **no number this
project produces is quotable yet under EVAL §1, because the thing that would make one quotable does
not exist.**

**Found already correct** and left alone: `ARCHITECTURE` §6 (six tables, both triggers, the TRUNCATE
escape hatch, `seq` ordering, the no-money-column reasoning), `API_CONTRACT` 0.3.0 throughout
including the computed `needs_review_count` and the dual-target contract suite, INV-1 … INV-6 in
`PROJECT_CONTEXT` §6, `EXTRACTION_SCHEMA` 0.3.0, and every ADR's reasoning.

**Next:** `DATASETS.md` §7 is a stub — the three research responses it was meant to merge were never
supplied to me, so anything they found outside Hugging Face (Kaggle, university pages, LDC/ELRA,
paper supplements) is missing. Paste them and §7 fills in. Separately, ADR-008 item 3 names FBR SRO
1006(I)/2021 as the generator's field schema and **that SRO has not been read into this repository**
— the mapping onto `EXTRACTION_SCHEMA.json` does not exist, so that item is a decision with no
implementation behind it.

## 2026-08-05 — the mock is now backed by a real app; contract suite runs against both

**Touched:** INV-3, INV-4, INV-6 · `backend/app/db/{models,session,queries,seed,fixtures}.py` (new),
`backend/app/db/migrations/` (new), `backend/app/{main.py,api/,core/,services/,export/,schemas/}`
(new), `backend/docker-compose.yml` (new), `backend/alembic.ini` (new),
`backend/tests/integration/` (new), `backend/tests/contract/conftest.py`,
`backend/tests/mock_server.py`, `backend/pyproject.toml`, `backend/CLAUDE.md`,
`Docs/ARCHITECTURE.md` §6, `Docs/API_CONTRACT.md` §2 §7 §9

Three commits, plus one baseline commit that landed the previous sessions' work — HEAD was still at
the scaffold, so nothing had a coherent tree to sit on.

**Did:** Postgres 16 with six tables. INV-4 and INV-6 are **triggers**, not conventions: every
`UPDATE`/`DELETE` on `extractions`, `corrections` and `audit_log` raises `restrict_violation`, and an
`UPDATE` changing `documents.data_classification`, `storage_path` or `sha256` raises too. A
`before_flush` listener raises first with a message naming the invariant, so the ORM path fails
readably; both layers are tested separately. The current view — latest extraction plus newest
correction per field — is one SQL statement.

Nine real endpoints, JWT with three roles, uploads content-addressed on disk and `chmod 0444`.
Enqueue is a stub as instructed. Contract suite parameterised over `mock` and `real`: **the same 36
tests run against both, and `test_api_contract.py` was not edited by a single character.**

**Learned / broke:** three things, all found by things failing rather than by reading.

**"Latest" was a coin flip.** `ORDER BY created_at DESC, id DESC` looks obviously correct and is
not: `now()` is *transaction start time*, so two rows written in one transaction tie exactly, and
the tiebreak then falls to a random UUID. The current view would have returned an arbitrary one of
two extractions, silently, with no error and no test failure — a wrong number reaching a billing
sheet by way of a `bigint` nobody thought about. Ordering is now an `IDENTITY` sequence. This is the
same family as the money-in-float rule: do not let a value that must be exact depend on a
representation chosen for a different purpose.

**`TRUNCATE` walks straight past both triggers.** Row-level triggers do not fire on truncate, so the
append-only guarantee is only as strong as the grants. The test suite relies on this to reset
between cases, which means the escape hatch is *in daily use* — it needs to be a revoked privilege
in any real deployment, and that is now written into `ARCHITECTURE` §6 rather than left as a
property of the code nobody would think to check.

**One contract test cannot pass against the real app, and it should not.**
`test_status_progresses_queued_to_complete` asserts an upload reaches `complete`. The mock does that
on a fake clock; the real app cannot, because enqueue is a stub with no Celery behind it. The
temptation was to weaken the assertion so both sides go green — which would have deleted the only
test that will notice when the worker lands and does not work. It is skipped for `real` with the
reason spelled out, and the skip is in `conftest.py`, not in the test file, so the target stays
exactly as written.

Also worth recording: the fixtures existed twice — once in `mock_server.py`, once as whatever the
real app would seed. Running the suite against both would then have been comparing two copies of the
same hand-maintained data and calling it agreement. They now come from one module,
`app/db/fixtures.py`, which the mock imports and the seeder writes. `needs_review_count` was
hardcoded `3/2/0` in the mock and had no definition anywhere; it is now defined in `API_CONTRACT`
§7 and computed, which changed the fixture numbers to `6/4/0`.

Smaller: `JWT_SECRET` defaulted to `change-me`, nine bytes, and PyJWT warned about it on every
decode. The listing endpoint exposed `from_` rather than the contract's `from`.

**Next:** two things the frontend dev needs, on top of 0.2.0 and 0.3.0 which he still has not been
told about. **An uploaded document on the real server never leaves `queued`** — there is no worker,
so the review screen has to be built against the three seeded fixture documents or against the mock.
And the export endpoint renders inline inside the POST handler; it returns `202 queued` per the
contract while having already finished, which is a lie the contract currently requires and which
stops being one when Celery lands.

Nothing in the pipeline is wired to any of this yet: `paddle.py` has still never run against a real
model, and no extraction is ever produced by the application — every extraction in the database was
put there by the seeder.

## 2026-08-05 — first real pipeline stage: PaddleOCR wrapper and a synthesised degradation ladder

**Touched:** INV-2 · `backend/app/pipeline/ocr/paddle.py` (new), `backend/tools/degrade.py` (new),
`backend/tests/unit/test_degrade.py` (new), `backend/tests/unit/test_paddle_ocr.py` (new),
`backend/pyproject.toml`, `backend/CLAUDE.md`, `Docs/ARCHITECTURE.md` §2 §4,
`Docs/PROJECT_CONTEXT.md` §3, `Docs/EVAL_AND_GOLDEN_SET`.md §2

Second entry today. The session was gated into two reviewable halves; the first is below.

**Did:** `paddle.py` wraps PP-OCRv5 and returns `TextRegion`s — text, per-region confidence, bbox
normalised to 0..1 in the shape of the schema's `source` object. No merge logic: Qaari and the merge
are separate stages. The loader is lazy and injectable, so 22 unit tests run with a fake engine and
need neither the model nor a GPU. `paddleocr` is an optional dependency group (`uv sync --group
ocr`) rather than a default dependency; Pillow is a real one, for page size.

`degrade.py` synthesises a 6-step ladder (L0 original .. L5 worst realistic scan): skew, contrast
loss, Gaussian blur, downsample to 100–150 dpi, JPEG artefacts, in scan order. Deterministic per
seed, jittered per level so one seed gives one reproducible sample and different seeds give
different ones. CLI writes PNGs so no *further* JPEG loss is added on top of the modelled loss.
CORD is clean and we have no degraded Latin invoices, so this is what makes the ≥ 25% degraded slice
measurable at all.

No CORD download, no OCR run — as instructed. 153 unit tests, 61 contract tests.

**Learned / broke:** three things, two of them found by tests failing.

**Edge sharpness is not monotonic across the ladder, and the reason matters.** L1 measured *higher*
edge energy than L0 (67.2 vs 64.9). JPEG ringing around sharp black-on-white edges adds
high-frequency detail, so at low degradation the artefacts add edge energy faster than blur removes
it. Monotone loss only takes over from L2. This is exactly the shape of trap that would make a CER
curve get misread later — "L1 scored better than L0, the ladder is broken" — so it is now two named
tests rather than a footnote: one asserting the fall from L2 down, one asserting the non-monotonic
top so that if it ever *becomes* monotone somebody has to decide that deliberately.

**The jitter bands were wider than the gaps between levels.** ±25% on skew makes L4 (1.8° ± 0.45)
overlap L5 (2.5° ± 0.63), so a seed could produce a level 5 less skewed than its level 4 — a ladder
whose rungs cross. Caught by the monotonicity test on seed 0. The bands are now bounded by the
tightest adjacent pair: skew ±15%, blur ±10%, contrast ±2%, quality ±4. A "deterministic given a
seed" ladder is not the same claim as "ordered by severity", and only the second one is useful.

Third: PNG stores resolution as pixels-per-metre, so a 110 dpi write reads back as 110.0074. Only a
test assertion, but it is the same class of thing as money-in-float — a unit conversion that looks
lossless and is not.

**Next:** `paddle.py` has never been run against a real image or a real model — every test injects a
fake engine, so the wrapper is verified against *the documented* PP-OCRv5 output shape, not the
actual one. `rec_polys` / `rec_scores` / `rec_boxes` handling is the part most likely to be wrong,
and it will show up as either an exception or an empty region list on first contact. Adeen is
running it against real images and reporting CER; that run is the first real evidence any of this
works. `evals/run_eval.py` does not exist yet, so the CER numbers from that run are **not quotable**
under §1 of [[EVAL_AND_GOLDEN_SET]] — they are a diagnostic, and the harness is what makes them a
measurement.

## 2026-08-05 — classification moved onto the document record; profile stamped in `pipeline_version`

**Touched:** INV-6, INV-3, INV-4 · `Docs/decisions/ADR-007-classification-on-the-document-record.md`
(new), `Docs/EXTRACTION_SCHEMA.json` (0.2.0 → 0.3.0), `Docs/API_CONTRACT.md` (0.2.0 → 0.3.0),
`Docs/PROJECT_CONTEXT.md` §6 §8 §10, `Docs/ARCHITECTURE.md` §1 §6 §7, `Docs/INDEX.md`,
`Docs/decisions/ADR-006-two-deployment-profiles.md` (amendment banner only),
`backend/app/db/documents.py` (new), `backend/app/pipeline/llm/client.py`,
`backend/tests/unit/test_document_record.py` (new), `backend/tests/unit/test_llm_guard.py`,
`backend/tests/mock_server.py`, `backend/tests/contract/test_api_contract.py`

**Did:** `data_classification` is no longer an argument to `LLMClient.complete`. It is a field on a
frozen `DocumentRecord`, set at upload, immutable after, defaulting to `restricted`; the guard reads
it off the record. The argument is **removed, not kept as an override** — an override is the same
defect with a better name. `reclassify()` returns a new record with a new `document_id` and refuses
to reuse the old one. Third enum value renamed `customer` → `restricted` (ADR-007 argues the rename:
`restricted` names the handling rule, which is the thing a *default* can honestly say; `customer`
names a belief about contents, which a default cannot).

Upload now **requires** `data_classification` — the choice is named in API_CONTRACT §2 rather than
left implied. Both required-and-rejected and optional-with-a-default are default-deny, so it is not
a safety difference; it is about where the human decision gets recorded. A default makes an uploader
that never sends the field indistinguishable, in the table, from documents someone actually
classified. Two new error codes: `INVALID_CLASSIFICATION` and `IMMUTABLE_FIELD`.

`pipeline_version` gains a required `profile`. Schema to 0.3.0, mock fixtures and contract tests
follow. 128 tests pass.

**Learned / broke:** the previous session shipped a guard that fails closed on a *malformed*
classification and called INV-6 enforced. It was not. Default-deny catches the typo and the missing
value; it cannot catch a caller that confidently passes `"synthetic"` for a real invoice, and every
call site was free to pass whatever it liked. The guard was load-bearing on the assumption that the
argument arriving at it was correct — which is the assumption the guard existed to remove. This is
the fourth time in this repo the same shape has appeared: a mechanism that checks *form* being read
as a mechanism that checks *truth* (`cnic_digit_count`, boolean `gates[].passed`, the invented
mrc/otc identity, now a validated argument standing in for a recorded decision).

The tell was in the code's own shape and nobody looked at it: a function whose correctness depends
on its caller has moved the problem, not solved it. Persisting the value does not make it *true* —
a human can still classify a real invoice as synthetic at upload — but it makes the decision
singular, attributable, and immutable, instead of re-made silently on every call.

`ARCHITECTURE` §6 now carries the `NOT NULL DEFAULT 'restricted'` / no-`UPDATE` requirement for the
`documents` column, because there is no DB layer yet — `app/db/` has no models, session or
migrations — and this record is a frozen dataclass standing in for a table that does not exist. That
is a gap worth naming rather than a design: the immutability is currently Python-level only.

**Next — still the blocking one, and it is now two versions deep.** **The frontend dev has still not
been told about 0.2.0 or 0.3.0.** Neither has been agreed by both owners, which §4 ground rule 4
requires and which was already outstanding when 0.2.0 shipped. What he needs, in order:

1. **0.2.0:** `gates[].passed` is gone; `gates[].result` is three-state; `format_only` renders as
   unconfirmed, grouped with `failed`, never with `passed`.
2. **0.3.0, upload:** `data_classification` is a **required** form field with three values. It is a
   control the user fills in — hard-coding `"synthetic"` in the upload helper makes the form submit
   and defeats INV-6 the first time a real document goes through.
3. **0.3.0, results:** `pipeline_version.profile` is required and is part of a run's identity;
   `schema_version` is `"0.3.0"`.

A banner saying so is now at the top of `API_CONTRACT.md`; it comes off when he has read both and
agreed, not when the code is written.

## 2026-08-04 — ADR-006: two profiles, and INV-6 enforced in code

**Touched:** INV-6 (new) · `Docs/decisions/ADR-006-two-deployment-profiles.md` (new),
`Docs/PROJECT_CONTEXT.md` §3 §6 §8, `Docs/ARCHITECTURE.md` §1 §2 §7, `Docs/INDEX.md`,
`backend/app/pipeline/llm/client.py` (new), `backend/tests/unit/test_llm_guard.py` (new)

**Did:** recorded that there is no L20. `prototype` runs on an RTX 3060 Ti with both OCR models
local and the LLM hosted; `production` is the L20 with all three local. Added INV-6 — a real PTCL
document never reaches a hosted API — and enforced it: `assert_releasable` raises
`HostedEndpointRefusedError` before the transport is invoked, default deny, so an absent or
misspelled classification is refused rather than allowed. `LLMClient` also refuses to *construct*
with `profile=production, endpoint=hosted`. 26 guard tests.

Docs no longer claim hardware we do not have. `ARCHITECTURE.md` §1 carries a VRAM budget for both
cards, explicitly labelled estimates rather than measurements. Removed three `.gitkeep` files from
directories that now hold real code; the two under `evals/golden/` stay, since those directories
are still empty and gitignored.

**Learned / broke:** INV-6 is not like the other five. INV-1 through INV-5 are all *detectable
after the fact* — a wrong number in Excel can be traced, an overwritten row shows in the audit
trail, a bad IBAN fails its checksum on the next run. A customer CNIC sent to a hosted API produces
no error, no failing test, and no log entry that says anything went wrong. There is no "after the
fact" in which to catch it, which is why it is the one invariant that had to be a guard rather than
a rule, and why the guard fails closed on unrecognised input rather than falling through.

The realistic failure was never someone deciding to send customer data. It is someone testing the
prototype with one real invoice to see whether it works, which is the obvious thing to do and takes
one drag-and-drop.

Also worth recording: the docs asserted an L20 that never existed, and every capacity statement
built on it read as fact. The VRAM table replacing it is honest about being estimates — but it is
the same class of claim, and it should be measured before anything is decided on it.

**Next:** the profile is not yet recorded in `pipeline_version`, so two extractions of the same
document under different profiles would compare as if equivalent — that is an
`EXTRACTION_SCHEMA.json` change and therefore an `API_CONTRACT.md` bump, not done here.
`data_classification` currently lives only as an argument to the LLM client; it is not persisted on
the document record, so nothing yet stops a document being reclassified between runs. Both need
deciding before the prototype ingests anything.

## 2026-08-04 — invented MRC/OTC rule removed (ADR-005); mock server and contract tests land

**Touched:** INV-1 · `backend/app/pipeline/gates/arithmetic.py`,
`backend/tests/unit/test_arithmetic_gate.py`, `backend/tests/mock_server.py` (new),
`backend/tests/contract/` (new), `Docs/decisions/ADR-005-mrc-otc-relationship-unspecified.md` (new),
`Docs/ARCHITECTURE.md` §5, `Docs/API_CONTRACT.md` §9, `Docs/PROJECT_CONTEXT.md` §7 and §8,
`Docs/INDEX.md`, `backend/pyproject.toml`

**Did:** the mrc/otc sub-check no longer asserts `mrc + otc == subtotal`. It returns `format_only`
for any well-formed value and `failed` only for a malformed amount. ADR-005 records why. Added the
credit-note failure cases that were missing — a wrong negative total, a wrong negative line-item
sum, and a sign error — so negatives are tested in both directions, not just the passing one.

Mock server implements all nine endpoints of API_CONTRACT 0.2.0 with three fixture documents, one
per review state. 60 tests: 39 unit, 21 contract. Contract tests validate against
`EXTRACTION_SCHEMA.json` with a real JSON-Schema validator, plus a test that the validator rejects
known-bad payloads — otherwise a validator that accepts everything also produces a green run.

**Learned / broke:** the rule was written from the field names alone. `mrc` and `otc` sit next to
`subtotal` in the schema, so `mrc + otc == subtotal` looked like arithmetic. It is a claim about how
one company bills, and it is false for multi-month invoices, for contracts with no total, and for
any pro-rated period. Three months at 20,000 plus a 5,000 connection fee is a correct document that
the rule reported as broken.

The dangerous direction was the other one. `arithmetic_reconciliation` can set `verified: true`, so
whenever a document satisfied the invented identity by coincidence, a wrong number would have been
marked confirmed. This is the third time the same failure has appeared in this repo — a claim about
*shape* recorded as a claim about *correctness* — after `cnic_digit_count` and the boolean
`gates[].passed`. The first two were in the schema. This one was in code, which is worse, because no
document review catches it.

It also survived one round of self-review: I flagged the assumption in a draft report that was never
sent, and treated that as having raised it. A caveat that only exists in an unsent message is not a
caveat. The tolerance question in the same task was correctly escalated *before* implementing; the
business rule was not, and they are the same category of decision.

**Next:** `ARCHITECTURE.md` §5 now carries an explicit warning against reinstating the rule, since
"can fail but never pass" reads as an unfinished gate. `jsonschema` was added as a dev dependency —
not recorded in `PROJECT_CONTEXT.md` §3, which describes product stack rather than test tooling;
say if it should be. The frontend dev still has not been told about 0.2.0.

## 2026-08-04 — arithmetic reconciliation gate implemented and verified

**Touched:** INV-1 · `backend/app/pipeline/gates/arithmetic.py`, `backend/tests/unit/test_arithmetic_gate.py`, `Docs/JOURNAL.md`

**Did:** Verified and completed the arithmetic reconciliation gate (`check_arithmetic`) and its unit tests. Renamed exception class `_MalformedAmount` to `_MalformedAmountError` to comply with Ruff N818 rule. Formatted files and ran pre-push checks (`ruff check`, `ruff format --check`, `pytest`).

**Learned / broke:** `ruff check` flagged rule N818 (`_MalformedAmount` exception naming). All 34 tests passed with exact Decimal arithmetic throughout (no float, no arbitrary tolerances), missing operands mapped strictly to `FORMAT_ONLY`, and failure reporting per-check with exact field attribution (`affected_fields`).

**Next:** None.

---

## 2026-08-04 — ADR-004 supersedes ADR-003; API_CONTRACT 0.2.0; toolchain fixed

**Touched:** INV-1, INV-5 · `Docs/decisions/ADR-004-format-only-gate-state.md` (new),
`ADR-003-deterministic-gates.md` (superseded), `Docs/PROJECT_CONTEXT.md` §8, `Docs/INDEX.md`,
`Docs/API_CONTRACT.md` (0.1.1 → 0.2.0), `CodeBase/backend/pyproject.toml`

**Did:** three `pyproject.toml` fixes — `pythonpath = ["."]`, `explicit_package_bases = true`,
`addopts = "-q"` removed. All four pre-push checks now run as written in `backend/CLAUDE.md`, with
no env prefixes: `All checks passed!` · `5 files already formatted` · `18 passed in 0.02s` ·
`Success: no issues found in 2 source files`.

ADR-004 written and ADR-003 marked superseded — status and a pointer banner only, its reasoning
untouched. API_CONTRACT §4 documents the three-state `gates[].result` replacing the boolean
`gates[].passed`.

**Learned / broke:** ADR-003 was not wrong about its principle, which is why the error survived
review. It said deterministic validators outrank model confidence — correct — and then listed
`cnic_digit_count` next to `iban_checksum` as though both produced the same kind of answer. The
defect was one entry in a list inside a document whose headline claim was sound. A boolean
`passed` then made the two indistinguishable in the wire format. Nothing in the pipeline would have
flagged a misread CNIC arriving in Excel as `verified: true`; the design read as careful the whole
way down.

**Next — this is the blocking one.** `API_CONTRACT.md` is co-owned and is now at 0.2.0 with a
**breaking** change: `gates[].passed` is gone. **The frontend dev has not been told.** He must know
before he builds the review screen, not after:

1. `gates[].passed` (boolean) no longer exists — `gates[].result` is a three-value enum.
2. `format_only` must render as unconfirmed, grouped with `failed`, never with `passed`. A UI that
   treats it as a pass puts an unverified CNIC in front of a reviewer looking confirmed.
3. That is three visual states in the review screen, not two — and `verified: false` still has to
   stay visually distinct from low confidence, which was already true at 0.1.x.

Both owners have to agree per §4 ground rules; only one of them has seen this so far.

## 2026-08-04 — first gate implemented: `iban_checksum`

**Touched:** INV-5 · `backend/app/pipeline/gates/{base,iban}.py`,
`backend/tests/unit/test_iban_gate.py`, `Docs/ARCHITECTURE.md` §5

**Did:** `GateState` (`PASSED` / `FAILED` / `FORMAT_ONLY`) and a frozen `GateResult` in `base.py`;
`check_iban` in `iban.py` as a pure function, stdlib only. PK shape via
`PK[0-9]{2}[A-Z]{4}[0-9]{16}`, then mod-97. Input is normalised — whitespace stripped, uppercased —
because OCR emits IBANs grouped in fours and in mixed case. 18 unit tests, `18 passed in 0.03s`.

**Learned / broke:** three things, none of them the checksum.

`ARCHITECTURE.md` §5 listed `iban_checksum` as `passed`/`failed`, but an absent IBAN is neither —
it is `format_only`, because a document with no IBAN is not a document with a broken one. §5 now
says so: the states column describes a *present* field, and any gate can return `format_only` when
its field is missing. Writing the gate is what surfaced the gap; reading the table did not.

The toolchain does not run the documented commands. `app/` has no `__init__.py` and
`[tool.uv] package = false`, so `app` is on no import path: `uv run pytest tests/unit -q` fails at
collection with `ModuleNotFoundError: No module named 'app'`, and `uv run mypy` fails with "Source
file found twice under different module names". Both were worked around at the command line
(`PYTHONPATH=.`, `--explicit-package-bases`), not fixed — `pyproject.toml` was outside this task's
scope.

`addopts = "-q"` in `pyproject.toml` plus the `-q` in the documented command makes `-qq`, which
suppresses the summary line that `backend/CLAUDE.md` "Before pushing" requires you to quote. The
instruction to quote it and the command that hides it shipped in the same repository.

**Next:** three one-line `pyproject.toml` fixes, all unmade: `pythonpath = ["."]` under
`[tool.pytest.ini_options]`, `explicit_package_bases = true` under `[tool.mypy]`, and dropping `-q`
from `addopts`. Until then no documented test command works as written.

## 2026-08-04 — four validation claims corrected; CNIC was never verifiable

**Touched:** INV-1, INV-5 · `Docs/ARCHITECTURE.md` §5, `Docs/EXTRACTION_SCHEMA.json` (0.1.0 →
0.2.0), `Docs/EVAL_AND_GOLDEN_SET.md` §2 and §4

**Did:** `cnic_digit_count` → `cnic_format_check`, joined by `ntn_format_check` and
`strn_format_check`. Added the third gate state `format_only` to the schema: `gates[].passed`
(boolean) is replaced by `gates[].result` (`passed` / `failed` / `format_only`). Recorded that
`iban_checksum` is the only identifier gate that can verify. Added the Urdu OCR caveat to
`EVAL_AND_GOLDEN_SET.md` §2.

**Learned / broke:** CNIC has no check digit. The last digit is a gender parity marker, so it
constrains nothing about the preceding twelve — a "valid" CNIC is only a well-shaped one. NTN and
STRN have no checksum either. The docs had been carrying `cnic_digit_count` alongside
`iban_checksum` as if the two were the same kind of thing, and a boolean `passed` would have
recorded a format match as verification. That is INV-1 and INV-5 defeated by a schema field: a
transcription error in a CNIC would have reached a billing sheet marked `verified: true`.

The second correction is the same shape. Qaari's 0.048 WER is a clean-text number; Urdu accuracy on
the degraded scans that are ≥ 25% of the golden set has never been measured. Both cases are a
number that is true about something other than what it appears to be about.

**Next:** `Docs/decisions/ADR-003-deterministic-gates.md` still lists `cnic_digit_count` — left
untouched, since a decided ADR is superseded, never edited. It needs an ADR-004 to reconcile the
record. `EXTRACTION_SCHEMA.json` 0.2.0 is a breaking change and `API_CONTRACT.md` has not been
bumped: that is a co-owned edit and the frontend dev has not been told.

## 2026-08-04 — Stop hook removed

**Touched:** no INV · `.claude/settings.json`, `.claude/hooks/` (deleted), `Docs/INDEX.md`

**Did:** removed the docs-reminder Stop hook. The nesting was wrong first, then once that was
fixed the output surfacing could not be confirmed. Not worth more time. Deleted
`.claude/hooks/docs_reminder.py`, removed the now-dangling `hooks` block from
`.claude/settings.json`, and dropped the hook from the `.claude/` row in `INDEX.md`.

**Learned / broke:** the enforcement was never the hook. Doc discipline is carried by the
`AGENT_RULES.md` §2 trigger table, which is read by whoever is doing the work — a hook would only
have been a reminder to consult it. An unverifiable reminder is worse than none: it invites the
assumption that silence means the check passed, when silence also means the check never ran.

## 2026-08-04 — `.claude/` moved to the repo root; it had been in a place that never loaded

**Touched:** no INV · `.claude/` (from `CodeBase/.claude/`), `Docs/INDEX.md`, `.gitignore`

**Did:** moved the workspace config up one level. Rewrote every path in the five slash commands —
they were written relative to `CodeBase/` and now resolve from the repo root. Gitignored
`.claude/settings.local.json`, which is per-developer approval state, not shared config.

**Learned / broke:** the config had been sitting one directory below the project root, where
Claude Code never reads it, so none of it had ever taken effect. Worth noting what did *not* need
fixing: `${CLAUDE_PROJECT_DIR}` in `settings.json` and `git rev-parse --show-toplevel` in the hook
both re-resolve on their own. Hard-coded relative paths were the only casualties — which is the
argument for using those two mechanisms instead of relative paths in the first place.

**Next:** the Stop hook's wiring is still unverified (see the entry below). It cannot fire in this
repo until the scaffold is committed: with `Docs/` itself uncommitted, every run takes the
"docs changed" branch and passes silently.

## 2026-08-04 — `.claude/` workspace added; Stop-hook wiring unverified

**Touched:** no INV · `Docs/AGENT_RULES.md` (new), `CodeBase/CLAUDE.md`, `Docs/INDEX.md`,
`CodeBase/.claude/`

**Did:** extracted the shared rules out of `CodeBase/CLAUDE.md` into `Docs/AGENT_RULES.md` (§2 is
the trigger table `backend/CLAUDE.md` was already citing as "root §2"), reduced `CodeBase/CLAUDE.md`
to a pointer, and added `CodeBase/.claude/` — permission allowlist, a non-blocking Stop hook that
warns when `backend/app/` or `backend/tests/` changed with no `Docs/` change, and five commands.

**Learned / broke:** two things. First, the Stop hook cannot use "files this session edited" —
Claude Code documents no transcript schema and no per-session edited-file list, so the hook reads
the git working tree instead, which answers a broader question. Second, `git status --porcelain`
collapses untracked directories to a single entry, which silently defeated the path matching until
`-uall` was added; the failure mode was a hook that always passed. **The hook's logic is verified
against the documented Stop payload, but its wiring is not** — no Stop hook fired in any headless
`claude -p` run, including a minimal probe, in either a scratch repo or this one.

**Next:** verify the hook fires in a real interactive session (`/hooks`, or `claude --debug`) and
record the result here. Until then, treat the docs warning as absent, not as passing.

## 2026-08-04 — API_CONTRACT §9 named no module; mock could have landed in `app/`

**Touched:** no INV · `Docs/API_CONTRACT.md` §9 (0.1.0 → 0.1.1), `CodeBase/backend/README.md`

**Did:** §9 required a mock server but named neither a module nor a command, so the scaffold's
README guessed `app/mock.py`. Pinned it to `backend/tests/mock_server.py` with the explicit
`uv run uvicorn tests.mock_server:app --reload --port 8000`, in both §9 and the README.

**Learned / broke:** an underspecified doc does not stay underspecified — it gets resolved by
whoever writes code next, silently and possibly wrong. `app/mock.py` would have put a test double
inside the shipped package and under mypy-strict, and nothing in the docs would have contradicted
it. The fix is naming the artifact in the contract, not trusting reviewers to catch it.

**Next:** `tests/mock_server.py` and the `tests/fixtures/` payloads are still unwritten — they are
the first code this repo should get, before any pipeline work. API_CONTRACT is co-owned; the
frontend dev has not yet been told about the 0.1.1 bump.
