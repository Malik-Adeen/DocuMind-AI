---
status: accepted
owner: Adeen
last_reviewed: 2026-08-11
version: 1.0.0
---

# ADR-011 — Terminal status must be derived from positive evidence of verification, not the absence of contradiction

**Status:** accepted · **Decided:** 2026-08-11
**Supersedes:** — · **Related:** [[ADR-004-format-only-gate-state]], [[ADR-009-omission-is-invisible-to-the-gate-layer]]

## Context

`app/pipeline/orchestrator.py`'s `_needs_review` decided routing like this:

```python
def _needs_review(fields: Mapping[str, Any]) -> bool:
    populated = [entry for entry in fields.values() if entry.get("value") is not None]
    return not all(entry.get("verified") for entry in populated)
```

`populated` filters `fields` down to entries the model actually returned a non-null value for. The
function then asks whether every one of those is `verified`. The intent is legible for the ordinary
case: if the model extracted five fields and a gate confirmed all five, nothing here should force a
human to look at it.

The gap is in what happens when `populated` is empty — an extraction that found nothing at all.
`all()` over an empty iterable is `True` in Python; there is nothing left in the sequence to falsify
it. So `_needs_review` returned `not True`, i.e. `False`, and `extract()` set
`status = "complete"`, `review["required"] = False` — for a document with `fields: {}`, no line
items, and every gate reporting `format_only` because there was nothing to check. This was found
live: a document uploaded through the real pipeline produced exactly this shape and reached
`complete` with zero populated fields and zero `verified: true` fields anywhere in the result.

The consequence: an extraction that found and verified everything, and an extraction that found
nothing, both routed to `complete`, both set `review.required` to `false`. Nothing in the API
response distinguishes "a human doesn't need to look at this" from "nothing was extracted, so there
was nothing here for a human to disagree with." A reviewer scanning the documents list for anything
needing attention would never see this one.

This is the same shape of bug the project has hit repeatedly — see [[ADR-004-format-only-gate-state]]
(a format check standing in for a real verification) and [[ADR-009-omission-is-invisible-to-the-gate-layer]]
(an omitted field looking identical to a genuinely absent one). Here the failure is one level up:
not a single gate mistaking shape for truth, but the routing function mistaking *the absence of any
unverified field* for *the presence of verification* — because vacuous truth makes those look the
same in code, even though they mean opposite things about how much a reviewer should trust the
result.

## Decision

**`_needs_review` now treats zero populated fields as needing review, not as satisfying the
verified-everything condition:**

```python
def _needs_review(fields: Mapping[str, Any]) -> bool:
    populated = [entry for entry in fields.values() if entry.get("value") is not None]
    if not populated:
        return True
    return not all(entry.get("verified") for entry in populated)
```

The general rule this fix encodes: **a terminal status of `complete` must be earned by positive
evidence — at least one field that was both populated and confirmed by a gate — never granted by
the mere absence of a counterexample.** `all()` over an empty set, `not any(failures)`, `not
unverified_count` — anything of that shape is a trap for exactly this case, because it reads as "no
problems found" when the honest state is "nothing was checked." An empty result is the *least*
trustworthy outcome the pipeline can produce, not the most: it means either the document had nothing
extractable, or the model silently dropped everything — and the routing decision must not treat
those the same as a document that was actually examined and cleared.

Three unit tests in `tests/unit/test_orchestrator.py` pin this: zero populated fields routes to
`needs_review`; all populated fields verified routes to `complete`; some populated and unverified
routes to `needs_review`.

## Reason

[[PROJECT_CONTEXT]] §2 states the failure this project exists to prevent: confidently wrong numbers
reaching a billing sheet. An empty extraction reaching `complete` is the same failure wearing a
different shape — not a wrong number, but a *missing* one, marked with the same "nothing to see
here" status as a fully verified document. A downstream consumer of `needs_review_count` or the
documents list has no way to tell these apart without opening the extraction and noticing `fields`
is empty — exactly the blind spot [[ADR-009-omission-is-invisible-to-the-gate-layer]] already named
for individual fields, now shown to apply to the routing decision as a whole.

## Consequences

**Accepted:**

- Any extraction where the model returns no fields at all — a blank page, a wholly unreadable scan,
  a model that failed to produce any structured output the schema validator didn't already reject —
  now surfaces as `needs_review` instead of silently passing as `complete`. That is more review
  traffic for genuinely empty documents, which is the correct trade: a human confirming "yes, this
  page is blank" costs little; a document that was never actually looked at reaching `complete`
  costs a real number missing from a billing sheet with nothing to flag it.
- No gate changed. This is a routing-layer fix; `format_only`, `passed`, and `failed` mean exactly
  what [[ADR-004-format-only-gate-state]] says they mean. The bug was in how the orchestrator read
  the *absence* of unverified fields, not in any gate's verdict.

**Rejected alternatives:**

- *Require a minimum field count instead of checking for zero.* Rejected: choosing any threshold
  above zero requires a ground-truth field model per document type, which does not exist yet — the
  same reasoning [[ADR-009-omission-is-invisible-to-the-gate-layer]] already used to reject a
  completeness gate. Checking specifically for *zero* populated fields needs no such model: it is
  the one threshold that requires no assumption about what a document "should" contain.
- *Treat this as an eval-harness concern rather than a code fix*, on the reasoning that
  [[ADR-009-omission-is-invisible-to-the-gate-layer]] deferred field-completeness detection to eval.
  Rejected: that ADR is about telling a real omission apart from a genuine absence, which needs
  ground truth. This bug needed no ground truth — an extraction with literally zero populated fields
  is never legitimately "verified," regardless of what the document actually contains. That is a
  code defect, not a labeling question.

## Revisit when

If a future golden-labeled eval pass shows genuinely blank/unreadable documents flooding
`needs_review` at a rate that makes the queue unusable, revisit whether a distinct terminal status
(e.g. an explicit "nothing extracted" state, separate from a normal review queue) is warranted rather
than folding it into `needs_review`. Not a reason to revert this fix — `complete` for an empty result
was never correct.
