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
