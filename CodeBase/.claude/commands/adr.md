---
description: Write a new ADR in Docs/decisions/
argument-hint: [decision in a few words]
---

Existing ADRs: !`ls ../Docs/decisions/`

Write an ADR for: $ARGUMENTS

Take the next free number from the listing above and match the filename convention exactly
(`ADR-00N-kebab-title.md`). Follow the structure of the most recent existing ADR — read it first
rather than inventing a template.

Then link it from `../Docs/PROJECT_CONTEXT.md` §8 and add its row to `../Docs/INDEX.md`, in the
same commit.

If this reverses a decided ADR, do not edit that ADR. Supersede it: state which one, and say what
changed in the world to justify it — `../Docs/AGENT_RULES.md` §2.
