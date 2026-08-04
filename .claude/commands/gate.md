---
description: Add a deterministic validation gate
argument-hint: [gate-name]
---

Add the gate `$ARGUMENTS` to `CodeBase/backend/app/pipeline/gates/`.

Read first: `Docs/ARCHITECTURE.md` §5 for the existing gate list and why gates never
auto-correct, and `CodeBase/backend/CLAUDE.md` for the gate rules. Do not restate them here — follow them.

Non-negotiable for this change:

- One module, one pure function, `(extraction) -> GateResult`. No I/O, no model calls.
- Three states, not two: `passed`, `failed`, `format_only`. If the check has no checksum it is
  `format_only` and can never set `verified: true`.
- Unit tests both ways: a case that passes and a case that fails. A gate with only a passing test
  is untested.
- Update the gate list in `Docs/ARCHITECTURE.md` §5 in the same commit — `Docs/AGENT_RULES.md` §2.

If this gate changes the philosophy in ADR-003 rather than adding to it, stop and write an ADR
instead — `/adr`.
