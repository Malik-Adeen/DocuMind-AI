---
status: accepted
owner: Adeen
last_reviewed: 2026-08-04
version: 1.0.0
---

# ADR-002 — Two-stage OCR: PaddleOCR PP-OCRv5 then Qaari-0.1-Urdu

> **Amended 2026-08-05 — one premise below is factually wrong.** The decision stands; the reasoning
> is untouched, per the append-only rule. But this ADR says *"Whatever runs here has to yield boxes,
> not just text"* and then selects Qaari. **Qaari does not yield boxes.** It is a PEFT/LoRA adapter
> on Qwen2-VL-2B — a vision-language model prompted for plain page text — and it returns no
> coordinates of any kind. The two-stage design survives because PaddleOCR supplies every box and
> Qaari only replaces the *string* inside one; "merged by bounding box" means merged by
> *PaddleOCR's* bounding box. See [[ARCHITECTURE]] §4 and [[DATASETS]] §4 for the verified detail.
> The consequence this ADR did not anticipate: an Urdu region PaddleOCR fails to *detect* is
> invisible to the entire pipeline, because nothing else produces regions.

**Status:** accepted · **Decided:** date not recorded; extracted from the decision log in [[PROJECT_CONTEXT]] §8 on 2026-08-04
**Supersedes:** —

## Context

Incoming documents are Latin, Urdu, or mixed. The golden set targets ≥ 30% Urdu or mixed content
([[EVAL_AND_GOLDEN_SET]] §2), so Urdu is a primary case, not an edge case.

No single available OCR engine covers both well:

- **PaddleOCR PP-OCRv5** — strong on Latin text and, critically, produces the layout regions the
  rest of the pipeline depends on. Weak on Urdu script.
- **Qaari-0.1-Urdu** — Urdu-specialised, but it is not a general layout engine.

Every extracted field must carry a source span — page plus bounding box (INV-2). Whatever runs
here has to yield boxes, not just text.

## Decision

Run **both engines in sequence**, as Stages 1 and 2 of the pipeline ([[ARCHITECTURE]] §2):

1. PaddleOCR runs first over the whole page and produces text plus layout regions.
2. Regions whose script is detected as Urdu are re-read by Qaari.
3. Results are merged by bounding box. **Qaari wins on overlap inside Urdu regions.**

## Reason

A single engine handles Urdu poorly. Splitting the job lets each engine do what it is good at:
PaddleOCR owns layout and Latin text, Qaari owns Urdu glyphs, and the layout structure survives
because it comes from the engine that produces it.

## Consequences

**Accepted:**

- **Two model loads resident on one GPU**, alongside Qwen2.5-7B ([[ADR-001-local-llm]]). This
  tightens the memory budget that already forces serial GPU processing.
- **The merge step is a known sharp edge.** Reconciling two engines' bounding boxes can duplicate
  or drop text at region boundaries. [[ARCHITECTURE]] §8 names this as the most likely source of
  silent text corruption in the system — the failure mode that produces plausible-looking wrong
  output rather than an error.
- **The merge requires its own unit tests with overlapping-box fixtures.** This is not optional
  coverage; it is the mitigation for the risk above.
- Latency increases for any page containing Urdu. Acceptable under the correctness-over-latency
  constraint in [[ARCHITECTURE]] §1.
- Script detection becomes a dependency: a mis-detected Urdu region is never sent to Qaari.

**Rejected alternatives:**

- *PaddleOCR alone* — unacceptable Urdu accuracy against a corpus that is ≥ 30% Urdu.
- *Qaari alone* — no general layout engine, so no reliable regions and no provenance for INV-2.

## Revisit when

A single engine handles both scripts with layout at acceptable accuracy, or the merge boundary
proves to be a recurring source of eval regressions rather than a bounded, tested risk.
