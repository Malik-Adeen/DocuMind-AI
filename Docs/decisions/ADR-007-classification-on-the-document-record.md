---
status: accepted
owner: Adeen
last_reviewed: 2026-08-05
version: 1.0.0
---

# ADR-007 — `data_classification` belongs to the document, not to the call

**Status:** accepted · **Decided:** 2026-08-05
**Supersedes:** — · **Amends:** [[ADR-006-two-deployment-profiles]] (INV-6 wording and enum)
**Related:** INV-3 (raw uploads immutable), INV-4 (append-only)

## Context

[[ADR-006-two-deployment-profiles]] enforced INV-6 with a guard in
`backend/app/pipeline/llm/client.py`. The guard was correct and fails closed. But the value it
guarded arrived as a **per-call argument**:

```python
client.complete(prompt, document_id=..., data_classification=...)
```

So INV-6 held only if every caller passed the right value, on every call, forever. That is a
convention wearing a guard's clothes. Default-deny catches an *absent* or *misspelled*
classification; it cannot catch a caller that confidently passes `"synthetic"` for a real invoice,
and it cannot catch a reprocessing path that passes a different value from the one the uploader
chose. An invariant whose correctness is delegated to its callers is not an invariant — it is a
code review item with an exception type.

The [[JOURNAL]] entry for 2026-08-04 recorded the same gap from the other side: nothing stopped a
document being reclassified between runs, because there was no place a classification persisted to
be changed *from*.

## Decision

**`data_classification` is a column on the document record, set once at upload, immutable
thereafter — the same treatment the raw file already gets under INV-3.**

1. **Set at upload, immutable after.** The record is frozen. Assignment or deletion raises. The
   classification is written at the moment a human decides it and never again.
2. **The LLM client reads it from the record.** `LLMClient.complete` takes the document record and
   reads `document.data_classification`. The argument is **removed entirely, not retained as an
   override.** An override is the original defect with a more responsible name: the one caller who
   passes it is the one caller who gets it wrong, and that caller is the incident.
3. **Reclassification is a new document, never an `UPDATE`.** `reclassify()` returns a new record
   with a new `document_id` and refuses to reuse the old one. This is the shape INV-4 already
   requires of extractions and corrections, applied to the one field on `documents` that carries a
   data-egress consequence.
4. **The third value is renamed `customer` → `restricted`**, and is the default. An absent,
   empty, misspelled, or non-string value is `restricted`.
5. **The upload endpoint requires it.** Not optional-with-a-default. See below.

### Why `restricted` rather than `customer`

`customer` names a *belief about the contents* — that this document contains customer data. That is
the wrong question at classification time, and it invites the wrong answer: a vendor quotation with
no customer name in it is not `customer` by that reading, so someone reasonably marks it
`public`, and it leaves the machine.

`restricted` names the *handling rule*, which is the thing the record actually needs to carry: this
document may not leave this machine. It is also what the default has to mean. `restricted` is
correct for anything that is not affirmatively public or affirmatively synthetic — including
documents nobody has looked at yet, which is exactly the state a default applies to. Calling that
state `customer` would be asserting a fact nobody has checked.

The substance of INV-6 is unchanged: only `public` and `synthetic` reach a hosted endpoint, on any
profile, ever. Only the label of the denied class changes, and it changes to the one the default can
honestly wear. [[PROJECT_CONTEXT]] §6 and [[ARCHITECTURE]] §7 are updated to match; ADR-006's own
text is left as decided.

### Why the API requires it rather than defaulting to `restricted`

Both are default-deny. The difference is *where the human decision is recorded*.

If the upload endpoint defaults, an integration that never sends the field produces a stream of
documents that are all `restricted` and all silently unprocessable on the `prototype` profile. The
failure surfaces later, at extraction, as a refusal — far from its cause, and looking like a bug in
the guard rather than a missing field in the uploader. Worse, it is indistinguishable from a
correctly-classified restricted document, so nobody can tell the two apart in the table.

Requiring the field makes the client state the classification explicitly, and a missing one is a
`422` at the moment the upload is attempted, naming the field. ADR-006 already rejected redaction on
the grounds that *classifying the whole document is a decision a human can make correctly* — this is
that decision, so the contract should insist it was actually made rather than inferred from silence.

**The record still defaults to `restricted`.** The API is not the only way a record gets created —
fixtures, migrations, replays and workers all construct records directly — and the default is what
makes those paths fail closed. Required at the boundary, default-deny at the record: they answer
different questions and the record's answer is the one INV-6 depends on.

## Consequences

**Accepted:**

- **`API_CONTRACT.md` goes to 0.3.0 and the change is breaking.** An upload without
  `data_classification` now returns `422 INVALID_CLASSIFICATION`. The contract is co-owned and the
  frontend dev has not agreed to it, or to 0.2.0 before it.
- **A new error code, `IMMUTABLE_FIELD`**, because `PATCH .../extraction` has to refuse a correction
  naming `data_classification` rather than quietly accepting one.
- **Reclassification costs a re-upload and a re-extraction.** Deliberate: the audit trail then shows
  two documents with two classifications and two extraction histories, instead of one row whose
  meaning changed at an unrecorded moment.
- **The DB column does not exist yet.** `app/db/` has no models, session or migrations, so this ADR
  lands as a frozen `DocumentRecord` in `app/db/documents.py`. The first migration must create
  `documents.data_classification` as `NOT NULL DEFAULT 'restricted'` with no `UPDATE` path;
  [[ARCHITECTURE]] §6 records that requirement so it is not rediscovered.
- `app/pipeline/llm/` now imports from `app/db/`. The pipeline reads the document record; that is
  the dependency direction this decision is made of.

**Rejected alternatives:**

- *Keep the argument, add the record as a fallback.* Rejected: two sources of truth for the one
  value that has no detector when it is wrong. The fallback is never the one that is wrong.
- *Keep the argument as an explicit override for tests.* Rejected: tests construct the record. If
  the test setup cannot express the state, the state is wrong, not the test.
- *Make the record mutable and audit the changes.* Rejected: an audit log tells you a document was
  reclassified after the fact, which is the one thing INV-6 has no use for — by then the extraction
  under the old classification has already run and already sent.
- *Default the API field to `restricted`.* Rejected: see above. It converts a missing field into a
  document that looks classified.

## Revisit when

The first migration lands, at which point the column's `NOT NULL` and the absence of an `UPDATE`
path stop being a note in [[ARCHITECTURE]] §6 and become schema. Also when the `prototype` profile
is retired per ADR-006 — `restricted` stops gating anything the day no hosted endpoint is
configurable, but the field should outlive the profile, because retention and export will want it.
