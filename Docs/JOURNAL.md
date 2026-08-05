---
status: active
owner: Adeen
last_reviewed: 2026-08-04
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
