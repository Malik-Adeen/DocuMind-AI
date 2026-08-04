---
description: Append a session entry to Docs/JOURNAL.md
argument-hint: [one-line summary]
---

Today: !`date +%Y-%m-%d`

Append an entry to `../Docs/JOURNAL.md` for this session. Summary: $ARGUMENTS

The entry format is documented at the top of `JOURNAL.md` itself — read it and match it exactly.
**Newest first:** the new entry goes directly below the `<!-- newest entry goes here -->` marker,
above every existing entry. Never edit or delete a past entry.

Fill `Learned / broke` with the thing that was not obvious before this session started. If that
line would be empty, the entry is a changelog and git already has one.
