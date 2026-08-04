---
description: Change API_CONTRACT.md — stop-and-confirm flow
argument-hint: [what changes]
disable-model-invocation: true
---

Proposed contract change: $ARGUMENTS

**STOP. Do not edit `../Docs/API_CONTRACT.md` yet.** It is co-owned by backend and frontend and
neither side changes it unilaterally — `../Docs/PROJECT_CONTEXT.md` §4.

First state, and wait for my confirmation:

1. **The change**, in one sentence, quoting the current text and the proposed text.
2. **Major or minor.** Removing or renaming a field is major and needs both owners to agree
   *before* the edit. Adding an optional field is minor. See the contract's own ground rules §4.
3. **The new version number**, and every place it must change — frontmatter `version`, the
   `**Version:**` line, and `last_reviewed`.
4. **The blast radius:** which of the mock server, `EXTRACTION_SCHEMA.json`, the export columns,
   and the contract tests this breaks.

Only after I confirm: make the edit, bump the version, and add a `/journal` entry.

End by telling me, explicitly, that **the frontend dev has to be told** — and what to tell them.
The commit does not do that for you.
