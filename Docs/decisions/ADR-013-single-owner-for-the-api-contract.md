---
status: accepted
owner: Adeen
last_reviewed: 2026-08-14
version: 1.0.0
---

# ADR-013 — `API_CONTRACT.md` moves to a single owner; the co-ownership gate is retired

**Status:** accepted · **Decided:** 2026-08-14
**Supersedes:** — · **Amends:** [[PROJECT_CONTEXT]] §4 (team split), [[AGENT_RULES]] §2 (trigger table)
**Related:** —

## Context

[[PROJECT_CONTEXT]] §4 has described this project as a two-person split since it was written: Adeen
on backend, a separate frontend developer on frontend, with `API_CONTRACT.md` as the co-owned
document between them. [[AGENT_RULES]] §2's trigger table added an explicit extra gate on top of the
normal docs-in-the-same-commit rule for any endpoint/status/error-code change: **"Both owners agree
first. Tell the frontend dev — the contract is co-owned."**

That gate has been unresolved since it was first needed. `API_CONTRACT.md`'s banner has carried a
"Not agreed" notice since 0.2.0 (`gates[].passed` removed) and 0.3.0 (`data_classification` required)
— both breaking changes the frontend dev has never reviewed — and every additive change since
(0.3.1–0.3.4) has landed behind the same unresolved banner rather than waiting for it, because
waiting was not an option: backend work does not stop for a sign-off nobody is available to give.

**The split ended. Adeen now owns both sides of [[PROJECT_CONTEXT]] §4's team split.** There is no
longer a second party for the gate to wait on.

## Decision

**`API_CONTRACT.md`'s owner becomes Adeen alone, and the co-ownership extra gate in
[[AGENT_RULES]] §2 no longer applies to it.** A change to an endpoint, status, or error code now
follows the ordinary rule already stated in the trigger table's own header row — update the document
in the same commit, bump the version — with no separate agreement step and no one to tell.

**The outstanding "Not agreed" banner is removed, not resolved as if a second review had happened.**
0.2.0 and 0.3.0 were never read by a second person, and this decision does not manufacture that
review after the fact — it removes the structural requirement that was waiting for it, because the
role the requirement depended on (a second owner) no longer exists. A gate that checks for agreement
between two roles held by one person is not a stricter version of that gate; it is a tautology
wearing the old gate's name, and leaving it in place would either block forever or train whoever
reads it to rubber-stamp their own change, which is worse than no gate at all.

**[[PROJECT_CONTEXT]] §4 is updated to match:** the team-split description now names Adeen as owner
of both the pipeline and the frontend surfaces §4 lists, and the "neither side changes it
unilaterally" line — which describes a two-party negotiation that no longer has two parties — is
replaced with the ordinary same-commit rule.

## Reason

An invariant, a gate, or a review step that depends on a role nobody occupies does not fail closed —
it just stops meaning anything while still looking like it does. `API_CONTRACT.md`'s banner has
already demonstrated this for two release cycles: it did not block 0.3.1–0.3.4 from shipping, it just
sat there accumulating debt nobody was positioned to pay down. Removing it honestly is better than
leaving a governance step that reads as active but has been dead since the split ended.

This is not a claim that co-review was a bad idea when there were two people. It is a claim that a
process control should describe the organization that actually exists, and updating the doc the
moment that stops being true is the same discipline [[AGENT_RULES]] §1 already requires of code: "If
you discover a doc is *already* wrong before you start, fix it first."

## Consequences

**Accepted:**

- **Every subsequent `API_CONTRACT.md` change needs only a version bump**, per the ground rules
  already in the file (§ Ground rules, rule 4) — additive change, minor/patch bump, no coordination;
  removing or renaming a field, major bump, still no second party to agree with, but still recorded
  as a deliberate breaking change in the same way 0.2.0 and 0.3.0 were.
- **[[AGENT_RULES]] §2's trigger table row for `backend/app/api/**`** drops its extra-gate column
  entry. The base rule — update `API_CONTRACT.md` and bump its version, in the same commit — still
  applies undiminished.
- **[[PROJECT_CONTEXT]] §4** no longer describes a role split that isn't real. If a second frontend
  owner joins later, that is itself a decision worth its own ADR, not a silent reversion of this one.
- **The historical banner content is not deleted from the record.** This ADR is the place that says
  0.2.0 and 0.3.0 shipped without a second reviewer, so a future reader auditing what got reviewed and
  what didn't has an honest answer instead of a banner that quietly vanished.

**Rejected alternatives:**

- *Leave the banner in place until someone reads 0.2.0 and 0.3.0.* Rejected: there is no one left in
  the frontend-owner role to do that reading. The gate would wait forever for an event that cannot
  occur, which is a way of pretending the gate still works.
- *Have Adeen "approve" the contract as the frontend owner, to satisfy the letter of the old rule.*
  Rejected: an approval from the same person who wrote the change is not a review, and recording it as
  one would be less honest than removing the gate outright.
- *Silently drop the banner without an ADR.* Rejected: AGENT_RULES §2 requires a new ADR for reversing
  any past decision, and the co-ownership model was a decision (implicit in [[PROJECT_CONTEXT]] §4
  since the file's first version), not an incidental detail.

## Revisit when

A second frontend owner joins the project. At that point co-ownership of `API_CONTRACT.md` is a new
decision to make deliberately — not a default to fall back into because it was once the arrangement —
and it should account for everything that shipped single-owner in the meantime.
