---
status: accepted
owner: Adeen
last_reviewed: 2026-08-04
version: 1.0.0
---

# ADR-005 — The MRC/OTC-to-total relationship is unspecified; the gate stays format_only

**Status:** accepted · **Decided:** 2026-08-04
**Supersedes:** —
**Related:** [[ADR-004-format-only-gate-state]]

## Context

While implementing the arithmetic reconciliation gate, a third sub-check was written asserting
`mrc + otc == subtotal`. **Nobody specified that rule.** It was inferred from the field names and
implemented without being proposed.

It is also not true in general:

- A telecom invoice may bill the one-time charge plus a *single month* of the recurring charge, so
  the subtotal is `otc + mrc` only for a one-month period and only when nothing else is billed.
- A **contract or quotation** may state an MRC with no total at all — it describes a rate, not an
  amount due.
- **Multi-month billing breaks it outright.** Three months at 20,000 with a 5,000 connection fee
  gives a subtotal of 65,000, while `mrc + otc` is 25,000. The rule reports a failure on a
  perfectly correct document.
- Pro-rated first periods, credits, and discounts each break it again.

The severity is not that the rule produces false failures. It is the direction of the error.
`arithmetic_reconciliation` is a gate that **can** set `verified: true`
([[ADR-004-format-only-gate-state]]). An invented rule inside a verifying gate can mark a wrong
number as confirmed whenever a document happens to satisfy the invented identity for the wrong
reason. That is INV-1 defeated by code, which is the same failure [[ADR-004-format-only-gate-state]]
found in the schema — a format-shaped claim being recorded as a verified one.

The two arithmetic sub-checks are unaffected and remain as written. `line_items` summing to
`subtotal`, and `subtotal + tax == total`, are **arithmetic identities**, not business rules. They
are true of any document that uses those fields at all, for any period, in any currency.

## Decision

**The MRC/OTC sub-check returns `format_only` unconditionally.** It reports which of `mrc` and
`otc` are present and states in its detail that the relationship to the totals is undetermined. It
never returns `passed` and never returns `failed` on the basis of an arithmetic relationship.

It is retained rather than deleted so that the reviewer still sees these fields listed as
unconfirmed rather than silently unexamined, and so that the sub-check has somewhere to live if a
real rule is established.

A malformed `mrc` or `otc` value still returns `failed` — "this is not a decimal amount" is a
statement about the data, not about a business relationship.

**This stays `format_only` until the relationship is verified against real PTCL documents.**
Not until it seems reasonable; until it is checked against the golden set.

## Reason

A gate may only assert what is deterministically true. `subtotal + tax = total` is arithmetic.
`mrc + otc = subtotal` is a guess about how one company bills, and it was a wrong guess. The cost
of `format_only` is that a reviewer looks at two more fields. The cost of the invented rule is a
confirmed wrong number, which is the one outcome this system exists to prevent
([[PROJECT_CONTEXT]] §2).

## Consequences

**Accepted:**

- `mrc` and `otc` have **no deterministic backstop**. They reach the reviewer unverified, always.
  That is honest: they currently have none.
- Gate coverage for the two most commercially significant fields on a telecom invoice is a known
  gap, not an oversight. Recorded as an open question in [[PROJECT_CONTEXT]] §7.
- Any future MRC/OTC rule must be derived from the golden set and land with its own ADR — including
  the billing period, since every counter-example above is a period problem.

**Rejected alternatives:**

- *Keep the rule, downgrade only on mismatch.* Rejected: it still returns `passed` when the
  identity holds, which is precisely the case that would mark a coincidence as verification.
- *Delete the sub-check.* Rejected: the fields would then appear unexamined rather than
  explicitly unconfirmed, and the gap would stop being visible in the gate output.
- *Make it configurable per document type.* Rejected: a configurable rule is still an unverified
  rule, and it would spread the guess across a config file instead of recording it as unknown.

## Revisit when

The golden set contains enough real PTCL invoices, contracts and quotations to establish whether a
period-aware relationship holds — for example `subtotal == otc + (mrc × months)` with `months` read
from `billing_terms`. That would need `months` to be an extracted field, so it is a schema change
and a new ADR, not an edit to this one.
