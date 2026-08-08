---
status: active
owner: Adeen
last_reviewed: 2026-08-05
version: 1.0.0
---

# DATASETS.md — what data exists, what it is worth, and what it is not

Every corpus this project might train on, evaluate against, or quote a number from. **Read
[[EVAL_AND_GOLDEN_SET]] §1 first:** no accuracy number is quotable unless it came from that harness.
This file is about the inputs; that one is about the measurement.

> ⚠️ **Provenance of this file.** It was asked for as "merge the three research responses". **Those
> three responses were not available to me** — they are not in this repository and were not supplied.
> Everything below is either (a) verified directly against source code, the Hugging Face API, or a
> model card, with the check named, or (b) explicitly marked as an unverified claim carried over
> from the request. **Nothing here is a summary of a research document I have not read.** Where the
> request said three sources disagreed, §2 records what the code does instead. Sections marked
> **[NEEDS THE THREE RESPONSES]** are the parts I could not write without them.

---

## 1. The one-line summary

**There is no public dataset of mixed Urdu/English business documents.** That is why
[[ADR-008-synthetic-generation-is-a-component]] makes generation a component. Everything in §3 is a
substitute for something that does not exist.

---

## 2. Synthdog-RTL — verified against source, 2026-08-05

`github.com/aiviewz/Synthdog-RTL`, cloned at commit `15e9d1f`, 528 lines of Python. Three research
sources reportedly disagreed on whether it emits field-level boxes and Donut-style JSON or
line-level transcription only. **The code settles it.**

### Does it produce field-level bounding boxes? **No. It writes no coordinates at all.**

- `template.py:70` computes `"roi": np.array(paper_layer.quad, dtype=int)` — the **page** quad, four
  corners of the paper. Not fields.
- `template.py:81` binds `roi = data["roi"]` inside `save()` **and never uses it.** No coordinate of
  any kind is written to disk.
- Per-token layers *do* exist transiently: `elements/textbox.py:24-36` builds one `TextLayer` per
  whitespace token with a real `bbox`. Line 42 then calls `layers.Group(line_layers).merge()`, which
  collapses them into a single layer. **The per-token geometry is destroyed before the function
  returns.**

### Does it produce Donut-style JSON? **Only the envelope, not the content.**

`template.py:99` is the whole answer:

```python
metadata = self.format_metadata(image_filename=..., keys=["text_sequence"], values=[label])
```

One key: `text_sequence`. It emits Donut's `{"gt_parse": {...}}` wrapper, so a skim of the output
format says "Donut" — but `gt_parse` contains a single flat string, not key–value fields. Confirmed
against the generated output committed to the repository at
`outputs/SynthDoG_ur/*/metadata.jsonl`:

```json
{"file_name": "image_0.jpg",
 "ground_truth": "{\"gt_parse\": {\"text_sequence\": \"محمد علی جناح: ایک عہد ساز شخصیت …\"}}"}
```

### Is it line-level? **No — it is coarser than that. It is page-level.**

`template.py:63`: `label = " ".join(texts).strip()`. Every textbox on the page is concatenated into
one string. Line segmentation is not preserved either, so "line-level transcription" overstates it.

**Verdict on the three-way disagreement:** the source supports *none* of "field-level boxes +
Donut JSON". It is page-level plain text in a Donut-shaped wrapper. Whichever source claimed
structured JSON was most likely reading the `gt_parse` envelope or the README, which says the tool
is "for … data extraction … using Donut OCR" without ever claiming field annotation.

### Does it handle mixed Urdu/English in one line? **No, and not nearly.**

Five independent findings, all from source:

1. **`bidi` is imported and never called.** `template.py:15` has
   `from bidi.algorithm import get_display`. `get_display` appears nowhere else in the repository.
   The one function that would do bidirectional reordering is dead.
2. **RTL is a right-to-left word advance, not bidi.** `elements/textbox.py:20-32` splits the line on
   spaces and decrements `left` per token. Applied to a mixed line, an English run is laid out
   right-to-left too — **English word order comes out reversed.** This is not an approximation of
   bidi; it is a different algorithm that coincides with bidi only for pure RTL text.
3. **`bidirectional: 0` in the configs is not what it looks like.** It appears at `config_ur.yaml:101`
   under the **shadow effect** arguments (`intensity`, `amount`, `smoothing`, `bidirectional`). It is
   a shadow parameter. **This is the single most likely cause of the disagreement between the three
   sources** — it reads as a text-direction switch and is not one.
4. **The shipped Urdu corpus contains zero Latin characters.** `resources/corpus/urdu_sample.txt`:
   53 lines, 0 occurrences of `[A-Za-z]`. Mixed script has never been exercised.
5. **The fonts cannot render Latin.** `resources/font/ur/` contains only the four
   `NotoNastaliqUrdu-*` faces, which have no Latin coverage.

### Other findings worth knowing before adopting it

- **`TextReader` never terminates.** `elements/content.py:27-36`: on exhaustion it resets `idx` to 0
  and returns line 0 again, so `next(self.reader, None)` at line 69 never yields `None`. The corpus
  loops forever. With the shipped 53-line corpus, generated pages repeat heavily.
- **Tokens that overflow are silently dropped.** `textbox.py:34` breaks the loop when `left < 0`; the
  label is `" ".join(lines)` of the tokens that fit. Labels stay truthful, but page content is
  silently truncated relative to the corpus line.
- **`TextLayer` is constructed twice per token** (`textbox.py:24` and `:29`), the first discarded,
  and `left` is advanced using the pre-rescale width. Sloppy rather than fatal.

**Conclusion:** usable as a starting point for *Urdu-only, page-level* OCR pretraining. Unusable as
the generator [[ADR-008-synthetic-generation-is-a-component]] requires without adding field
structure, coordinate output, and real bidi.

---

## 3. Existing Urdu corpora

Searched Hugging Face for Urdu OCR datasets, 2026-08-05. Seven results, ranked by downloads:

| Dataset | Size | Content | Field labels? | Mixed script? |
|---|---|---|---|---|
| [`PuristanLabs1/urdu-ocr-1M`](https://hf.co/datasets/PuristanLabs1/urdu-ocr-1M) | 1.5 M | synthetic Nastaliq lines | No | No |
| [`deepcopy/MMU-OCR-21-Urdu-TextLines`](https://hf.co/datasets/deepcopy/MMU-OCR-21-Urdu-TextLines) | 100 K–1 M | text lines | No | No |
| [`Khurram123/urdu-poetry-nastaleeq-ocr`](https://hf.co/datasets/Khurram123/urdu-poetry-nastaleeq-ocr) | 17,610 | poetry couplets, Jameel Noori | No | No |
| [`Khurram123/urdu-poetry-ocr-couplets`](https://hf.co/datasets/Khurram123/urdu-poetry-ocr-couplets) | 11,700 | poetry couplets | No | No |
| [`oddadmix/qaari-0.1-ocr-urdu-news-dataset-small`](https://hf.co/datasets/oddadmix/qaari-0.1-ocr-urdu-news-dataset-small) | 35.9 K | news articles — **see §4** | No | No |
| `tfxhk/urdu_ocr` | small | untagged, undocumented | ? | ? |
| `ebadhussain20/urdu_ocr` | 1 K–10 K | **gated** | ? | ? |

**Not one is a business document. Not one carries field annotation. Not one mixes scripts.** Two
searches for bilingual or business-document Urdu datasets returned zero results. This is the
evidence base for [[ADR-008-synthetic-generation-is-a-component]].

Note what the shape of this table means for [[ADR-002-two-stage-ocr]]: every available Urdu corpus
is *line or page transcription of prose*. There is no public data anywhere that teaches a model
where a field *is* on an Urdu page, only what a line *says*.

---

## 4. The Qaari news dataset — do not measure CER on it

The request flagged this as "likely Qaari's own training corpus, so a CER measured on it is
train-set performance and not quotable". **The operative conclusion is right. The stated reason is
partly wrong, and the real reason is worse.**

### What is verified

- The model is [`oddadmix/Qaari-0.1-Urdu-OCR-VL-2B-Instruct`](https://hf.co/oddadmix/Qaari-0.1-Urdu-OCR-VL-2B-Instruct)
  — a **PEFT/LoRA adapter on Qwen2-VL-2B**, base `unsloth/Qwen2-VL-2B-Instruct-unsloth-bnb-4bit`.
- The dataset is by **the same author**, carries **the model's own version prefix**
  (`qaari-0.1-…`), and was **created 8 Mar 2025 — two days before the model** (10 Mar 2025).
- It is **35.9 K rows** (28.7 K train / 3.6 K validation / 3.6 K test) of **real Urdu news** — image
  URL plus transcription. Two columns, both strings. Not synthetic.

### Conflict — recorded, not resolved

**The model card contradicts the training-corpus hypothesis.** It states:

> **Training Dataset** — Size: 10,000. Source: "Syntehtic Dataset" *(sic)*.

So the card claims 10 K **synthetic** images, while this dataset is 35.9 K **real news** images.
These cannot both describe the same corpus. Possibilities, none confirmed:

- the news dataset is a different artifact from the training set;
- the card is imprecise (it also lists the base model two different ways);
- 10 K is a subset, or an earlier run.

**Resolving it needs the author.** It is recorded here as a conflict rather than decided.

### Why the conclusion holds anyway — three reasons, all stronger than contamination

**(a) The 0.048 WER has no stated evaluation set.** The card reports 0.048 WER / 0.029 CER / 0.916
BLEU against Tesseract and the Qwen base, and never says what any of it was measured on. A number
with no named eval set cannot be reproduced, attributed, or compared — regardless of contamination.

**(b) The card's own scope is much narrower than "Urdu".** It lists five fine-tuning fonts
(AlQalam Taj, Alvi, Gandhara Suls, Jameel Noori, NotoNastaliqUrdu) and seven point sizes (14–40),
and its Limitations section says performance degrades outside them. Combined with a synthetic
training source, **0.048 is best read as clean synthetic Nastaliq in the model's own five training
fonts** — not printed Urdu generally, and certainly not a scanned PTCL invoice.

**(c) The labels have a systematic character-level defect.** This is the serious one.

**The character آ (U+0622, alef with madda) does not appear anywhere in the transcriptions.** Across
11 rows sampled from two splits (~6,000 characters), it occurs **zero** times, while dozens of words
require it:

| In the label | Should be | Meaning |
|---|---|---|
| `مارشل رٹ` (×5) | `مارشل آرٹ` | martial art |
| `کسیجن` (×2) | `آکسیجن` | oxygen |
| `رڈیننس` (×2) | `آرڈیننس` | ordinance |
| `سان` (×2) | `آسان` | easy |
| `ئندہ` | `آئندہ` | next / upcoming |
| `ئل` (×3) | `آئل` | oil |
| `نکھوں` | `آنکھوں` | eyes |
| `پشن` | `آپشن` | option |
| `سٹریلیا` | `آسٹریلیا` | Australia |
| `ئی سی سی` (×3) | `آئی سی سی` | ICC |
| `رنلڈ شوازینگر` (×3) | `آرنلڈ شوازینگر` | Arnold Schwarzenegger |
| `اکانٹ` | `اکاؤنٹ` | account — **ؤ (U+0624) also affected** |

**Consequences, in order of severity:**

1. **A CER measured against these labels is not a CER.** It scores agreement with a corpus that is
   systematically wrong about a common Urdu character. A model that correctly reads آ would be
   *penalised*.
2. **If Qaari trained on this, Qaari has learned to omit آ** — which would then show up in our
   pipeline as a silent transcription defect on every Urdu field, exactly the class of failure
   [[PROJECT_CONTEXT]] §2 exists to prevent.
3. It is invisible from the model card, invisible in 0.048, and would have been invisible in any
   number we published off this corpus.

**Method and its limits, stated honestly:** 11 rows across the `train` and `test` splits, inspected
via the Hugging Face dataset viewer. Zero occurrences of آ against dozens of required sites is far
beyond chance for Urdu prose, but a full-corpus count was not run — the dataset was not downloaded.
**Anyone planning to use this corpus should run that count first; it is a few minutes' work and it
decides whether the corpus is usable at all.**

### Verdict

**Do not quote any number measured on this dataset.** Not the train split, not the validation split,
not the test split — the test split is the model author's own split of the model author's own corpus,
published alongside the model, and carries the same label defect. It is not an independent benchmark
under [[EVAL_AND_GOLDEN_SET]] §1 by any reading.

---

## 5. CORD

Used as the Latin-script reference corpus. Clean receipts, field-annotated, English/Indonesian.

**Its limitation is why `backend/tools/degrade.py` exists:** CORD is clean, and no degraded
Latin-script invoice corpus is available to us, so the degradation ladder synthesises one. See
[[EVAL_AND_GOLDEN_SET]] §2 for what a CER curve off that ladder is and is not allowed to claim.

**Not downloaded yet.** No number has been measured against it in this repository.

---

## 6. The golden set

150 real PTCL documents, specified in [[EVAL_AND_GOLDEN_SET]] §2. **Does not exist yet.**

It is `restricted` under INV-6 by definition, so it cannot be used on the `prototype` profile at all
([[ADR-006-two-deployment-profiles]]). Everything in this file is what stands in for it until the
L20 exists and real documents can be processed.

---

## 7. [NEEDS THE THREE RESPONSES]

Sections I could not write without the research responses that were not supplied:

- **Any dataset the three responses named that is not in §3.** My §3 is a Hugging Face search;
  it will miss anything on Kaggle, a university page, a paper's supplementary material, or the
  LDC/ELRA catalogues.
- **The specific disagreements between the three sources**, beyond the Synthdog-RTL question in §2.
  I recorded what the code does; I cannot record who said what.
- **Any Urdu/Arabic-script benchmark with published, independently-run numbers** — the thing that
  would let us calibrate against someone else's measurement rather than only our own.

Paste the three responses and this file gets those sections. Until then they are absent rather than
guessed at.

---

## 8. The rule this file exists to enforce

Every corpus here is either **not what it claims**, **not what we need**, or **not yet obtained**.
Three of the five entries carry a defect that is invisible from their documentation and was only
found by reading source or sampling rows.

**Read the corpus before you quote a number off it.** The Qaari case in §4 is the worked example:
a published model, a headline metric, a clean-looking dataset card, and a missing character that
makes the metric meaningless.
