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
