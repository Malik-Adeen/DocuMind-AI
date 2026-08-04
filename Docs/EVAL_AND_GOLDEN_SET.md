---
status: active
owner: Adeen
last_reviewed: 2026-08-04
version: 1.1.0
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

**Urdu OCR caveat.** Qaari-0.1-Urdu's reported **0.048 WER is a clean-text figure** — printed,
well-scanned Urdu. It says nothing about the documents this system actually receives. **Urdu WER on
degraded input is unmeasured:** skew, low-DPI scans, stamp and signature overlap, and handwritten
annotation are exactly the ≥ 25% degraded slice of the golden set above, and no Urdu error rate has
been measured on any of it. Do not quote 0.048 as this pipeline's Urdu accuracy, and do not assume
Urdu field recall on degraded documents resembles the Latin path's. Measuring it is a prerequisite
for any claim about Urdu support — until then it belongs in §6.

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
- N concurrent documents on the single L20 until p95 latency doubles. That N is your queue limit.
  Write the number into `PROJECT_CONTEXT.md` §7.

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

---

## 6. What we are *not* testing yet

Named honestly so nobody assumes coverage that does not exist:
handwriting-only documents, rotated-90° pages, multi-document PDFs, non-Urdu/non-English text,
adversarial uploads, **Urdu OCR accuracy on degraded scans** (see the Urdu OCR caveat in §2).
Add each to the golden set before claiming support.
