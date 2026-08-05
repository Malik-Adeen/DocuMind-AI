---
status: accepted
owner: Adeen
last_reviewed: 2026-08-04
version: 1.0.0
---

# ADR-006 — Two deployment profiles, and real documents never leave the machine

**Status:** accepted · **Decided:** 2026-08-04
**Supersedes:** —
**Related:** [[ADR-001-local-llm]] (not reversed — scoped)

> **Amended by [[ADR-007-classification-on-the-document-record]] (2026-08-05).** The decision below
> stands; two details of its INV-6 section have moved on. `data_classification` is no longer a
> per-call argument — it is set at upload on the document record and is immutable — and the third
> value is now named `restricted`, not `customer`. Read ADR-007 for the current wording. Nothing
> else here is changed, and the reasoning is untouched.

## Context

**There is no L20.** The card in [[PROJECT_CONTEXT]] §3 was written as though the hardware existed;
it does not. The prototype runs on a local **RTX 3060 Ti, 8 GB**. An L20 is procured only if the
project is approved.

8 GB does not hold Qwen2.5-7B-Instruct. At fp16 the weights alone are roughly twice the card, and
that is before the KV cache and before two OCR models that also have to be resident. The prototype
therefore has to reach a hosted LLM API for extraction, which is exactly what
[[ADR-001-local-llm]] decided against.

[[ADR-001-local-llm]] chose local inference for data residency: these are real PTCL commercial
documents carrying customer names, CNICs, IBANs and amounts. That reasoning has not weakened. What
has changed is that a prototype does not need real documents to prove a pipeline works — synthetic
documents from SynthDoG + Faker `ur_PK` and publicly available forms exercise every stage.

So the question is not "local or hosted". It is **which data may reach which endpoint**, and the
hardware profile follows from that.

## Decision

Two profiles. The hardware differences are consequences; the data rule is the decision.

| | `prototype` | `production` |
|---|---|---|
| GPU | RTX 3060 Ti, 8 GB | L20, 48 GB |
| PaddleOCR PP-OCRv5 | local | local |
| Qaari-0.1-Urdu | local — 4-bit base if fp16 does not fit | local, fp16 |
| Qwen2.5-7B-Instruct | **hosted API** | local (vLLM) |
| Documents permitted | **public and synthetic only** | real PTCL documents |
| Status | now | only if the project is approved |

### INV-6

**A real PTCL document must never reach a hosted API.**

Added to [[PROJECT_CONTEXT]] §6 as the sixth invariant. Every document carries a
`data_classification` of `public`, `synthetic`, or `customer`. Only `public` and `synthetic` may be
sent to a hosted endpoint. `customer` is local-only, on any profile, forever.

This does **not** reverse [[ADR-001-local-llm]]. That decision stands for every document the
decision was about. This ADR scopes a temporary exception to a class of data that carries no
residency obligation, because it contains no customer information — there is nothing to keep
resident.

### Enforced, not documented

The rule is a guard in `backend/app/pipeline/llm/client.py` that raises
`HostedEndpointRefusedError` before the transport is invoked. It is not a comment, a convention, or
a code review item:

- **Default deny.** An absent, empty, misspelled, or non-string classification is refused. Only the
  two literal releasable values pass. A bug in the calling code fails closed.
- **The prototype cannot be built wrong.** Constructing an `LLMClient` with
  `profile=production, endpoint=hosted` raises `ProfileMisconfiguredError` at construction.
- **The refusal message carries no document content** — the document id and the classification
  label only. An exception that pastes the prompt into a log is the leak it was preventing.
- Tests assert the transport is never called when the guard raises. "It raised" is not the same
  claim as "nothing was sent".

## Reason

A prototype on borrowed hardware is a normal engineering compromise. A prototype that quietly sends
a customer's CNIC and IBAN to a third-party API is a data incident, and it would happen the first
time someone tests with a real invoice "just to see" — which is the most natural thing in the world
to do, and the reason this is a guard rather than a rule.

The failure has no detector. Nothing in the pipeline notices, no gate fails, no test goes red, and
the data is gone. Unlike every other invariant here, INV-6 cannot be caught after the fact, so it
is the one that has to be enforced before the call rather than validated after it.

## Consequences

**Accepted:**

- **No accuracy number from the prototype describes the production system.** Different LLM, possibly
  4-bit OCR, and synthetic documents — all three break comparability. The release gates in
  [[EVAL_AND_GOLDEN_SET]] §3 apply to the production profile only, and the golden set of 150 real
  documents cannot be run on the prototype at all.
- **The golden set cannot be used until the L20 exists.** It is real customer documents, so it is
  `customer`-classified by definition. Prototype evaluation runs on synthetic data and inherits the
  caveat already in [[EVAL_AND_GOLDEN_SET]] §2.
- **`pipeline_version` must record the profile**, or two extractions of the same document under
  different profiles will look comparable when they are not.
- A hosted API contradicts [[PROJECT_CONTEXT]] §3's "explicitly NOT in scope" list, which names
  hosted GPT/Claude API calls. That entry now reads "production profile only" rather than "never".
- Qaari at 4-bit is a quality regression of unknown size on a model whose degraded-Urdu accuracy is
  already unmeasured ([[EVAL_AND_GOLDEN_SET]] §2).

**Rejected alternatives:**

- *Run everything on the 3060 Ti with a smaller LLM.* Rejected: a 1–3B model on numerically dense
  documents produces the confidently-wrong numbers this product exists to prevent, and it would tell
  us nothing about whether the 7B design works.
- *Wait for the L20.* Rejected: approval depends on a working prototype.
- *Rely on a documented rule and reviewer discipline.* Rejected: see Reason. The one invariant with
  no detector is the one that must not depend on someone remembering it.
- *Redact documents before sending them to the hosted API.* Rejected: redaction that works is a
  harder problem than extraction, and a redactor that misses one CNIC has leaked it. Classifying the
  whole document is a decision a human can make correctly.

## Revisit when

The L20 is procured. At that point the `prototype` profile stops being needed for extraction and
should be retired rather than left available — a profile that permits a hosted endpoint is a
standing risk once real documents are in the system. Retiring it is a new ADR, and it should also
record the measured VRAM figures that [[ARCHITECTURE]] §1 currently only estimates.
