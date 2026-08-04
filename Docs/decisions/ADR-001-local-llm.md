---
status: accepted
owner: Adeen
last_reviewed: 2026-08-04
version: 1.0.0
---

# ADR-001 — Local Qwen2.5-7B instead of a hosted GPT/Claude API

**Status:** accepted · **Decided:** date not recorded; extracted from the decision log in [[PROJECT_CONTEXT]] §8 on 2026-08-04
**Supersedes:** —

## Context

The extraction stage needs an instruction-following model that turns assembled OCR text into JSON
matching [[EXTRACTION_SCHEMA.json]]. Two routes were available: call a hosted frontier API
(GPT/Claude), or run an open-weights model on hardware we already own.

The inputs are real business documents — invoices, purchase orders, contracts — containing
customer names, IBANs, CNICs and billing figures. Sending them to a third party is a data
residency question, not a technical preference.

Available compute is one L20 with 48 GB GDDR6, already bought. See [[ARCHITECTURE]] §1.

## Decision

Run **Qwen2.5-7B-Instruct locally** on the L20. No hosted LLM API calls in the extraction path.

Hosted GPT/Claude API calls are listed as explicitly out of scope in [[PROJECT_CONTEXT]] §3.

## Reason

- **Data residency.** Document contents never leave the node. A hosted API would put customer
  identifiers and billing figures on someone else's infrastructure.
- **Fixed cost on owned GPU.** The GPU is a sunk cost. Per-document inference is then free at the
  margin, and cost does not scale with volume — which matters for a tool meant to replace manual
  retyping at whatever volume arrives.

## Consequences

**Accepted:**

- A 7B model is materially weaker than a frontier model on numerically dense documents. This is
  named as a known weakness in [[ARCHITECTURE]] §8 and is the direct reason [[ADR-003-deterministic-gates]]
  exists — we do not trust the model's numbers, we check them.
- The GPU stage is serial: OCR models and Qwen share 48 GB. That constraint forces the queue
  architecture in [[ARCHITECTURE]] §3 rather than a scale-out service.
- Single point of failure at the GPU. Acceptable for an internal single-tenant tool.
- Model upgrades are our operational problem, not a vendor's.

**Rejected alternatives:**

- *Hosted GPT/Claude API* — better raw extraction quality, but fails the residency requirement and
  makes per-document cost variable.
- *A larger local model* — does not fit alongside two OCR models on 48 GB at usable throughput.

## Revisit when

Data residency requirements change (e.g. an approved regional endpoint), the golden-set gates in
[[EVAL_AND_GOLDEN_SET]] §3 prove unreachable with a 7B model, or a second GPU node appears.
