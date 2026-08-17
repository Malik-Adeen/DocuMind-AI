---
status: accepted
owner: Adeen
last_reviewed: 2026-08-17
version: 1.0.0
---

# ADR-014 — Hosted processing exception for two named documents, not a change to INV-6

**Status:** accepted · **Decided:** 2026-08-17
**Supersedes:** — · **Amends:** —
**Related:** [[PROJECT_CONTEXT]] §6 INV-6, [[ADR-006-two-deployment-profiles]], [[ADR-007-classification-on-the-document-record]]

## Context

[[PROJECT_CONTEXT]] §6's INV-6 is unconditional: **a real PTCL document never reaches a hosted
API.** `data_classification` has exactly three values — `public`, `synthetic`, `restricted` — and
only the first two may leave the machine, on any profile, ever. There is no fourth value and no
override path in code; the guard in `app/pipeline/llm/client.py` reads the classification off the
document record and refuses before the request is built ([[ADR-007-classification-on-the-document-record]]).

Two real PTCL documents need to go through the pipeline on the `prototype` profile (hosted LLM) for
a one-off end-to-end test, ahead of the `production`/all-local profile existing:

- `Azeem.jpeg` — a Road Master purchase order. Scanned, skewed, stamped and signed, USD amounts,
  a handwritten date.
- `Azeem.pdf` — a multi-page PTCL–DTMS service addendum.

Neither document is `synthetic` — both are real. Neither is `public` in the ordinary sense the
contract describes it (§2: "a blank form, a published tariff") — they are real commercial
paperwork, just not documents containing a third party's confidential data beyond PTCL's own
business terms. Adeen has verbal authorization to process specifically these two documents via the
hosted endpoint. The classification vocabulary has no category that honestly describes "real,
authorized-for-this-one-test, not generally shareable" — forcing a choice between inventing a
fourth value (a code and schema change) or making an explicit, recorded, per-document exception
using the vocabulary that exists.

## Decision

**These two named documents, and only these two, are uploaded with `data_classification: public`
for this test.** No new classification value is added. No code path in the INV-6 guard changes —
`assert_releasable` still reads the classification off the document record and still refuses
anything not `public` or `synthetic`, exactly as before this ADR.

**This is a per-document authorization, not a policy change.** It covers `Azeem.jpeg` and
`Azeem.pdf` as uploaded for this test and nothing else — not "documents like these," not "documents
from this source," not a standing exception any future uploader can invoke by analogy. Re-running
this test with a different real document requires the same verbal authorization and, if it recurs
routinely enough to need one, its own ADR — not a citation of this one.

**INV-6 itself is unchanged.** The invariant still reads exactly as [[PROJECT_CONTEXT]] §6 states
it: a real PTCL document never reaches a hosted API by default, enforced by a guard that trusts the
document record over any caller. What differs here is the classification decision made by a human,
at upload, for two specific files — the same decision point INV-6 has always deferred to
([[ADR-007-classification-on-the-document-record]]: classification lives on the record, set at
upload, immutable afterwards). This ADR records that the decision was made deliberately and with
authorization, not that the mechanism was bypassed.

## Reason

The alternative to an explicit exception is a silent one: hand-editing the database, adding a debug
flag, or teaching the guard to trust an environment variable. Each of those is strictly worse than
what this ADR does, because each either weakens the guard for every future document or leaves no
record of why a real document was ever hosted-eligible. Using the existing `public` value and
writing down, by name, which two documents and under what authorization keeps the guard's logic
untouched and makes the exception auditable — a future reader of the `documents` table who finds
these two rows classified `public` has this ADR as the explanation, rather than an unexplained
anomaly that looks like a bug or, worse, like a precedent.

Restricting this to two named documents rather than a general "real documents may be tested as
public" rule is deliberate: INV-6's value is that it fails closed by default and requires a positive,
attributable act to override for any given document. A rule broad enough to cover future documents
by category would recreate exactly the gap INV-6 exists to close — an uploader could always argue
their document fits the category.

## Consequences

**Accepted:**

- `Azeem.jpeg` and `Azeem.pdf` are processed through the `prototype` profile's hosted LLM endpoint
  when uploaded with `data_classification: public`, selected explicitly via the upload form (no
  default — see the upload-center classification selector this ADR's Step 1 also introduces).
- The `documents` table will carry two rows for real documents classified `public`. Anyone auditing
  classifications later has this ADR as the reason; no other row should match this pattern without
  its own equivalent record.
- INV-6's code, its default-deny behavior, and [[ADR-006-two-deployment-profiles]] /
  [[ADR-007-classification-on-the-document-record]] are all unchanged by this decision.

**Rejected alternatives:**

- *Add a fourth classification value (e.g. `authorized`).* Rejected: a schema change for a two-document,
  one-off test is disproportionate, and a new value that means "real but cleared" invites exactly the
  category-based reasoning this ADR is trying to avoid — the next uploader would ask why their
  document doesn't also qualify.
- *Bypass the guard directly (env flag, DB edit, code path).* Rejected: this either weakens INV-6 for
  every document processed while the bypass exists, or leaves no record distinguishing an authorized
  exception from an unexplained one. Using `public` through the ordinary upload path keeps the guard
  fully intact and the exception fully auditable.
- *Wait for the `production` (all-local) profile instead of testing on `prototype` now.* Rejected by
  the person requesting the test — the point of this run is to see real extraction behavior against
  real documents before the all-local profile exists, and that requires the hosted profile.

## Revisit when

A third real document needs hosted-profile testing, or this becomes a recurring need rather than a
one-off — either signals the exception is becoming a pattern, which INV-6's design deliberately
does not want handled by precedent. At that point, decide explicitly whether a real, general
mechanism (e.g. a documented human-sign-off flow, or accelerating the `production` profile) is
warranted, rather than reusing this ADR's authorization for a document it doesn't name.
