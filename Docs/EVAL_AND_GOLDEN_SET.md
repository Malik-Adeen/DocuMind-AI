---
status: active
owner: Adeen
last_reviewed: 2026-08-08
version: 1.2.0
---

# EVAL_AND_GOLDEN_SET.md

The one rule: **no accuracy number is quotable unless it came out of this harness.**
"It looks good on the samples I tried" is not a measurement.

---

## 1. Why per-field, not per-document

Document-level accuracy hides the only failure that matters. A document where the customer name
is right and the MRC is wrong is not 90% correct — it is a wrong invoice.

We therefore report **per-field precision and recall**, and a separate **critical-field exact-match rate**.

**Critical fields:** `po_number`, `customer_name`, `mrc`, `otc`, `total`, `effective_date`, `iban`, `cnic`.
Everything else is non-critical.

---

## 2. Golden set

| Property | Target |
|---|---|
| Size (v1) | 150 real documents minimum |
| Split | 60% invoices, 20% POs, 10% contracts, 10% quotations |
| Language | ≥ 30% Urdu or mixed |
| Quality | ≥ 25% deliberately degraded — skew, low-DPI scan, stamp/signature overlap, handwritten annotation |
| Layouts | ≥ 20 distinct vendor templates |
| Labels | hand-typed by a human reading the document, **not** corrected model output |

**Held-out rule.** Split into `dev` (100) and `sealed` (50). Sealed is opened only before a
release. If you tune prompts against sealed, it is no longer an eval set — it is training data.

**Synthetic data caveat.** SynthDoG + Faker `ur_PK` generates volume, not truth. Synthetic docs
are for training and smoke tests only. **Never report headline accuracy from synthetic data** —
it shares generator biases with nothing in the real world.

**Urdu OCR caveat — revised 2026-08-05, and it was understated.** Qaari-0.1-Urdu's reported
**0.048 WER** was previously described here as "a clean-text figure". Reading the model card and the
author's dataset makes it weaker than that:

- **It has no stated evaluation set.** The card reports 0.048 WER / 0.029 CER / 0.916 BLEU against
  Tesseract and the Qwen base and never says what any of it was measured on. A number with no named
  eval set cannot be reproduced, attributed, or compared — before contamination is even discussed.
- **Its declared scope is five fonts and seven point sizes**, all in the fine-tuning set, on a
  training corpus the card calls synthetic. Read 0.048 as *clean synthetic Nastaliq in the model's
  own training fonts*, not as printed Urdu.
- **The author's companion news dataset has a systematic label defect:** the character **آ**
  (U+0622) does not appear in it at all. A CER measured against those labels rewards omitting a
  common Urdu character. Full working in [[DATASETS]] §4.

So: **do not quote 0.048 as this pipeline's Urdu accuracy, and do not measure a replacement number
on the Qaari news dataset either** — that is the trap, not the fix. **Urdu WER on degraded input
remains unmeasured:** skew, low-DPI scans, stamp and signature overlap, and handwritten annotation
are exactly the ≥ 25% degraded slice of the golden set above, and no Urdu error rate has been
measured on any of it. Do not assume Urdu field recall on degraded documents resembles the Latin
path's. Measuring it is a prerequisite for any claim about Urdu support — until then it belongs
in §6.

**The general lesson, since this is the third time:** a published metric, a clean-looking dataset
card, and a defect visible only by sampling rows. `cnic_digit_count`, `mrc + otc == subtotal`, and
now this. Check the corpus before quoting the number off it — [[DATASETS]] exists for that.

### Synthesised degradation ladder

CORD and every other public receipt/invoice corpus we can use is **clean**, and we have no degraded
Latin-script invoices at all. So the ≥ 25% degraded slice above cannot currently be filled, and
"accuracy degrades on bad scans" is a claim with no number behind it.

`backend/tools/degrade.py` synthesises a **6-step ladder from one clean image** — L0 is the
original, L5 the worst realistic scan — applying skew, contrast loss, Gaussian blur, a downsample
to 100–150 dpi, and JPEG artefacts, in that order. It is deterministic given a seed, so a CER curve
is reproducible and a regression is attributable to the model rather than to the noise.

**What it buys:** the shape of the curve — *where* accuracy breaks, not merely *that* it does.
Running Stage 1 across L0…L5 gives a CER per level and identifies the step at which the Latin path
stops being usable.

**What it does not buy, and this is the same caveat as the synthetic-data one above:** a synthesised
ladder measures the pipeline against *this ladder*, not against real scans. Photocopier banding,
scanner streaks, stamp and signature overlap, handwritten annotation, and paper texture are not in
it. **A CER curve from `degrade.py` is not a golden-set number and is not quotable as accuracy on
degraded documents** — it is a diagnostic that tells you which degradation dimension to go and
collect real examples of. Real degraded documents replace it; they are not optional because it
exists.

### Label format
One JSON per document, matching `EXTRACTION_SCHEMA.json` `fields` block, values only:

```json
{ "document_id": "gold-0042", "po_number": "PO-2291", "mrc": "45000.00", "iban": null }
```

`null` means *the field is genuinely absent from the document*. Distinguish this from
*present but unreadable*, which is `"__illegible__"`. Scoring treats them differently.

---

## 3. Metrics

For each field, over the golden set:

- **Precision** = correct extractions / extractions attempted (non-null predicted)
- **Recall** = correct extractions / times the field was actually present
- **Hallucination rate** = predicted non-null where truth is `null` ← *watch this one*
- **Calibration** = accuracy within each confidence decile

**Precision alone does not catch a silently dropped field, and the harness must not report only
precision.** A field the model never extracted is invisible to every gate — [[ADR-004-format-only-gate-state]]'s
absent-field handling treats "genuinely not on the document" and "was on the document, the model
missed it" identically, on purpose, because a gate has no ground truth to tell them apart
([[ADR-009-omission-is-invisible-to-the-gate-layer]]). Eval is the only place that distinction is
answerable, because it has the golden label. **`run_eval.py` must report per-field recall and a
present-vs-absent breakdown** — for every field on every golden document, classify it as
present-and-correct, present-and-wrong, present-and-missed (a recall miss), or genuinely-absent —
using the `null`-means-absent / `"__illegible__"`-means-unreadable distinction §2 already specifies.
A report that only prints precision would pass every one of these cases silently.

Matching rules:
- Money: exact string match after decimal normalisation.
- Dates: normalised to ISO, exact.
- Names: case- and whitespace-insensitive exact. No fuzzy matching — fuzzy scoring flatters bad models.
- IBAN/CNIC: exact.

### Release gates (v1)

| Metric | Gate |
|---|---|
| Critical-field precision | ≥ 0.97 |
| Critical-field recall | ≥ 0.90 |
| Hallucination rate, critical fields | ≤ 0.01 |
| Gate false-pass rate (bad value marked `verified`) | 0.00 — hard fail |
| Non-critical field precision | ≥ 0.85 |

Recall is deliberately looser than precision. A missing field costs a human 20 seconds.
A wrong field costs a wrong invoice.

---

## 4. Test layers

**Unit (many, fast)**
- Each deterministic gate in isolation: IBAN checksum against known-valid and known-invalid,
  CNIC/NTN/STRN format checks, arithmetic reconciliation with a deliberate 1-rupee mismatch.
- **Format-only gates need a third test**, not two: well-formed → `format_only`, malformed →
  `failed`, and an assertion that neither path ever sets `verified: true`. A format gate tested
  only for pass/fail is the bug it is supposed to catch.
- Schema validation: malformed LLM output is rejected, never partially accepted.
- Money parsing: `45,000`, `45000.00`, `Rs. 45,000/-`, `4.5e4` → correct or rejected. Never silently coerced.

**Integration (some)**
- Fixture PDF → full pipeline → result validates against `EXTRACTION_SCHEMA.json`.
- Idempotency: same document + same `pipeline_version` twice → identical field values (INV-4).
- Gate authority: force the LLM to emit a valid-looking but checksum-failing IBAN;
  assert `verified: false` (INV-5).

**Contract (critical, given the two-person split)**
- Backend test asserts every response matches `API_CONTRACT.md`.
- Frontend test runs against recorded fixtures from that same contract.
- These two suites are what stop integration week from becoming integration month.

**Eval (nightly)**
- Full golden set. Output a per-field table. Commit the result to `evals/history/`.
- **Regression alarm:** any critical field dropping > 2 points vs. the last run blocks merge.

**Load (once, before handover)**
- N concurrent documents until p95 latency doubles. That N is your queue limit. Write the number
  into `PROJECT_CONTEXT.md` §7.
- **Blocked: there is no L20** ([[ADR-006-two-deployment-profiles]]). A load test on the RTX 3060 Ti
  measures a different machine running a different LLM, so it does not answer the production
  concurrency question. Do not run it and record the answer as if it did.

---

## 5. Harness shape

```
evals/
├── golden/
│   ├── dev/{docs,labels}/
│   └── sealed/{docs,labels}/
├── run_eval.py          # → per-field table + JSON report
├── scorers.py           # matching rules from §3
└── history/2026-08-04.json
```

`run_eval.py` prints one table and exits non-zero if any release gate fails.
That exit code is the whole point — it is what makes "95% accurate" a fact instead of a slogan.

**None of this exists yet.** `backend/evals/` contains three `.gitkeep` files and nothing else —
no `run_eval.py`, no `scorers.py`, no golden documents. `backend/CLAUDE.md` lists
`uv run python evals/run_eval.py` among its commands; that command does not currently run. The
shape above is a specification, not a description. **Consequence: no number produced anywhere in
this project is quotable yet under §1, including any CER measured off `tools/degrade.py`** — the
harness that would make one quotable has not been written.

---

## 6. What we are *not* testing yet

Named honestly so nobody assumes coverage that does not exist:
handwriting-only documents, rotated-90° pages, multi-document PDFs, non-Urdu/non-English text,
adversarial uploads, **Urdu OCR accuracy on degraded scans** (see the Urdu OCR caveat in §2).
Add each to the golden set before claiming support.
