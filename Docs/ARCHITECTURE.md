---
status: active
owner: Adeen
last_reviewed: 2026-08-07
version: 1.2.0
---

# ARCHITECTURE.md

Scope: the system as it actually is — one node, one GPU, one tenant.
Aspirational infrastructure lives in `PROJECT_CONTEXT.md` §3 under "not in scope".

---

## 1. Constraints that shape everything

- **One GPU, and right now it is the small one.** There is no L20 yet — see the two profiles below.
  Throughput is bounded by GPU, not CPU or IO, on either card.
- **Single tenant, internal users.** No org isolation, no per-tenant quotas.
- **Correctness > latency.** A 90-second document that is right beats a 10-second document that is wrong.

Consequence: the design is a **queue with a serialised GPU stage**, not a scale-out service.
Everything else exists to keep that stage fed and to check its output.

### Two profiles

| | `prototype` — now | `production` — if approved |
|---|---|---|
| GPU | RTX 3060 Ti, 8 GB GDDR6 | L20, 48 GB GDDR6 |
| PaddleOCR PP-OCRv5 | local | local |
| Qaari-0.1-Urdu | local, 4-bit base if fp16 does not fit | local, fp16 |
| Qwen2.5-7B-Instruct | **hosted API** | local, vLLM |
| Documents permitted | **public and synthetic only** | real PTCL documents |

**INV-6: a real PTCL document never reaches a hosted API.** That is the reason the profiles exist;
the hardware difference is the consequence. Enforced in `app/pipeline/llm/client.py`, not by
convention — the guard reads `data_classification` off the document record, where it was set at
upload and cannot be changed ([[ADR-007-classification-on-the-document-record]]). See
[[ADR-006-two-deployment-profiles]].

**The profile is stamped on every extraction.** `pipeline_version.profile` is required in
[[EXTRACTION_SCHEMA.json]] as of 0.3.0. Without it, the same document extracted on `prototype` and
on `production` produces two `pipeline_version` values that compare as equal while having gone
through a different LLM on different hardware — so a prototype number would silently satisfy a
production release gate, and INV-4's "idempotent per (document, pipeline_version)" would treat two
genuinely different runs as one. ADR-006 listed this as a consequence to be handled; this is it.

### VRAM budget

**These are estimates, not measurements.** Nothing here has been profiled on either card. They are
planning figures for deciding what can be resident at once, and every one of them should be
replaced with a measured number before it is relied on — the same rule
[[EVAL_AND_GOLDEN_SET]] applies to accuracy applies to capacity.

| Resident component | `prototype` (8 GB) | `production` (48 GB) |
|---|---|---|
| PaddleOCR PP-OCRv5 det + rec | ~1 GB | ~1 GB |
| Qaari-0.1-Urdu | ~2 GB at 4-bit | ~5 GB at fp16 |
| Qwen2.5-7B-Instruct weights | — (hosted) | ~15 GB at fp16 |
| KV cache + activations, single document | ~1 GB | ~4 GB at the concurrency limit |
| CUDA context, fragmentation, headroom | ~1 GB | ~2 GB |
| **Estimated total resident** | **~5 GB of 8** | **~27 GB of 48** |

The prototype's headroom is thin and the 4-bit Qaari is what buys it. **If Qaari fp16 fits, use
it** — 4-bit is a quality regression of unknown size on a model whose degraded-Urdu accuracy is
already unmeasured ([[EVAL_AND_GOLDEN_SET]] §2), so it is a cost to pay only when forced. Measure
before choosing.

**Correction, 2026-08-05:** the Qaari row is a 2 B vision-language model, not a small OCR model. The
published artifact is a LoRA adapter whose declared base is `unsloth/Qwen2-VL-2B-Instruct-unsloth-bnb-4bit`
— **already 4-bit**. So on the prototype, 4-bit is not a compromise we impose; it is the
configuration the adapter was trained against, and merging onto an fp16 Qwen2-VL-2B is the variant
that has *not* been validated by its author. The rows above still hold as estimates, but the
"if fp16 fits, use it" advice is now the less-tested path rather than the safer one. Nothing here
has been profiled.

The production column has room for a second concurrent document; whether that is *useful* is the
open concurrency question in [[PROJECT_CONTEXT]] §7, and it is answered by the load test in
[[EVAL_AND_GOLDEN_SET]] §4, not by this table.

---

## 2. Components

```
Browser (Next.js)
      │  HTTPS, JWT
      ▼
FastAPI  ──────────►  PostgreSQL 16  (documents, extractions, corrections,
      │                                exports, users, audit_log)
      │                     ▲
      │ enqueue             │
      ▼                     │
Redis ──► Celery worker ────┘
              │
              ├─ Stage 1  PaddleOCR PP-OCRv5      → text + layout boxes
              │             app/pipeline/ocr/paddle.py — model load is lazy
              │             and injectable; regions carry normalised 0..1
              │             bboxes + per-region confidence (INV-2)
              ├─ Stage 2  Qaari-0.1-Urdu          → Urdu regions only
              ├─ Stage 3  text assembly + cleanup
              ├─ Stage 4  Qwen2.5-7B-Instruct     → JSON per EXTRACTION_SCHEMA
              │             production: local vLLM
              │             prototype:  hosted API — INV-6 guard refuses
              │                         anything not public/synthetic
              ├─ Stage 5  schema validation       → reject malformed, no partial accept
              ├─ Stage 6  deterministic gates     → IBAN / CNIC / arithmetic
              └─ Stage 7  persist + route         → complete | needs_review
                            │
                            ▼
                  Excel generator (on demand)
```

**The diagram above describes the intended shape; nothing currently drives it end to end.** No
Celery worker exists yet (`app/workers/` is empty, `enqueue_extraction()` is a documented no-op —
[[JOURNAL]] 2026-08-07), so today the chain below runs only when a caller invokes it directly, as
the tests do.

**Stages 3–7 are `app/pipeline/orchestrator.py`.** It is the only code that calls OCR, the LLM
client and the gate modules in sequence — before it existed, each of those was tested only in
isolation. `extract()` is a pure function, `DocumentRecord` in and an `ExtractionOutcome` out, with
OCR/LLM/gates all injected; `run_and_persist()` wraps it with a `Session` to write the `Extraction`
row and update `documents.status`. It does not import Celery or know it will eventually run inside
a worker — that wiring is separate and later.

Schema validation (Stage 5) runs on the LLM's **raw** JSON — `document_type` / `language` /
`fields` / `line_items` only, checked against a schema built from `EXTRACTION_SCHEMA.json`'s own
`$defs` via `jsonschema`'s `Draft202012Validator` — before `document_id`, `pipeline_version`,
`status` and `gates` are stitched on by the orchestrator. A field missing `source` or `confidence`
fails the whole stage, not just that field, because both are already required by `$defs/field`
(INV-2). Every field's `verified` is then force-reset to `false`, regardless of what the LLM
claimed; only a gate result of `passed` can set it back to `true` (INV-5) — a field the model
reports 0.99 confidence on is not verified if no gate touched it, and stays unverified if a gate
touching it failed.

**The gate registry (`DEFAULT_GATES`) is an explicit tuple, not import-scanning.** A gate module
that exists under `pipeline/gates/` but is not added to that tuple never runs — a silent hole, by
design made visible rather than automatic. Before persisting, every top-level money field (derived
from `EXTRACTION_SCHEMA.json`'s `money_field` refs, not hand-listed — currently `mrc`, `otc`,
`subtotal`, `tax`, `total`) must carry a non-null `gate`; if none of the registered gates touched
it, `run_and_persist` refuses to write the row rather than persist an unchecked number (INV-1).

**Routing:** `complete` only if every populated top-level field ends up `verified: true`;
otherwise `needs_review`. In practice this routes most realistic documents to review, since fields
like `customer_name` have no gate at all yet — that is the intended bias ([[PROJECT_CONTEXT]] §2),
not a bug to tighten.

Local filesystem for raw uploads and exports. Not MinIO, not S3 — a directory with a documented
path and a backup cron. Swap later if it ever needs to be shared across nodes.

---

## 3. Why a queue at all

Because the GPU stage is serial and slow. Without a queue, a second upload either blocks an HTTP
request for a minute or OOMs the GPU. Celery gives: bounded concurrency, retry on transient
failure, and a status a client can poll. `API_CONTRACT.md` §3 exists because of this design, not
the other way round.

**Concurrency is a config value, not a guess.** Set it from the load test in
`EVAL_AND_GOLDEN_SET.md` §4.

---

## 4. The two-stage OCR decision

Neither engine alone is sufficient. PaddleOCR handles Latin text and layout well and is weak on
Urdu script; Qaari is Urdu-specialised and not a general layout engine.

Flow: PaddleOCR runs first and produces layout regions. Regions whose script is detected as Urdu
are re-read by Qaari. Results are merged by bounding box, Qaari winning on overlap in Urdu regions.

**Qaari returns no coordinates, and the merge depends on that being understood.** It is not a
detection-plus-recognition engine like PaddleOCR — it is a **PEFT/LoRA adapter on Qwen2-VL-2B**, a
vision-language model prompted to "return the plain text representation of this document". Given a
region crop it returns text and nothing else. So the bbox attached to any Urdu field comes from
**PaddleOCR's detection**, never from Qaari; Qaari only replaces the *string* inside a box
PaddleOCR already found. Two consequences: PaddleOCR must detect an Urdu region even when it reads
it badly, or the region is invisible to the whole pipeline; and INV-2's source span for an Urdu
field is Latin-stage provenance carrying Urdu-stage text. Verified against the model card,
[[DATASETS]] §4.

**Cost:** two model loads resident on one GPU, and a merge step that can produce duplicated or
dropped text at region boundaries. That merge is a known sharp edge — it needs its own unit tests
with overlapping-box fixtures.

**Stage 1 is `app/pipeline/ocr/paddle.py`.** It wraps PP-OCRv5 and nothing else: it returns
`TextRegion`s carrying text, per-region confidence, and a bbox normalised to 0..1 in the shape of
the `source` object in [[EXTRACTION_SCHEMA.json]]. **There is no merge logic in it** — Qaari and the
merge are separate stages, and putting either inside the Latin reader is what makes a merge bug
untestable. Model loading is lazy and the loader is injectable, so the unit tests need neither the
model nor a GPU; a mismatch between the engine's texts, scores and polygons raises rather than
truncating, because a silently dropped region is a field that reaches the reviewer with no
provenance (INV-2).

---

## 5. Validation as a separate stage

The gates (Stage 6) are ordinary deterministic code. No model involvement.

**A gate returns three states, not two:** `passed`, `failed`, `format_only`.

`format_only` exists because most identifiers on these documents have no checksum. A format check
can prove a value is *malformed*; it can never prove a well-formed value is *correct*. Collapsing
that into a boolean would let "looks like a CNIC" be recorded as "is the right CNIC", which is
exactly the confidently-wrong failure this system exists to prevent.

**A `format_only` result can never set `verified: true`.** Only a gate that can actually falsify a
correct-looking value may verify one.

| Gate | Result states | Can set `verified: true`? |
|---|---|---|
| `iban_checksum` — mod-97 | `passed` / `failed` | **Yes** |
| `arithmetic_reconciliation` — `subtotal + tax = total` | `passed` / `failed` | Yes |
| `arithmetic_reconciliation` — mrc/otc reconciliation | `format_only` / `failed` | **No** — see below |
| `date_parse` — parses to a real date, and is not absurd (e.g. year 1900) | `passed` / `failed` | Yes |
| `line_item_sum` | `passed` / `failed` | Yes |
| `currency_consistency` — one currency per document | `passed` / `failed` | Yes |
| `cnic_format_check` — 13 digits, positional structure | `format_only` / `failed` | **No** |
| `ntn_format_check` | `format_only` / `failed` | **No** |
| `strn_format_check` | `format_only` / `failed` | **No** |

**The mrc/otc sub-check can fail but can never pass, and that asymmetry is deliberate.** It is the
only entry in the table with that shape, so it looks like a bug and will invite someone to "finish"
it. It is finished.

A malformed `mrc` or `otc` — a value that is not a decimal amount — is a **data defect**, and the
sub-check returns `failed` for it. But there is **no known arithmetic relationship** between
`mrc`/`otc` and the totals: an invoice may bill `otc` plus one month of `mrc`, a contract may state
`mrc` with no total at all, and multi-month billing satisfies neither. So there is nothing the
sub-check can confirm, and it returns `format_only` for every well-formed value.

`mrc + otc == subtotal` was written into this gate once, on inference from the field names, and
removed. **Do not reinstate it without real documents.** `arithmetic_reconciliation` is a verifying
gate, so a wrong rule inside it does not merely produce false failures — it marks a wrong number
`verified: true` whenever a document satisfies the invented identity by coincidence. See
[[ADR-005-mrc-otc-relationship-unspecified]] and the open question in [[PROJECT_CONTEXT]] §7.

**Absent fields return `format_only`, not `failed`.** A gate whose field is null or absent has
nothing to check, and a document that genuinely has no IBAN is not a document with a broken one.
The "Result states" column above lists the states reachable when the field is *present*; every
gate can additionally return `format_only` when it is not. Only a present, well-formed,
checksum-passing value returns `passed`.

**`iban_checksum` is the only identifier gate that can verify.** CNIC carries no checksum — its
last digit is a gender parity marker, not a check digit, so it constrains nothing about the
preceding twelve. NTN and STRN have no checksum either. A CNIC, NTN or STRN that passes its format
check is `format_only` and reaches the reviewer as unverified, always.

A gate failure does **not** fail the document. It sets `verified: false` on the affected fields and
routes to `needs_review`. Silent auto-correction is forbidden — it converts a visible problem into
an invisible one.

---

## 6. Data model (shape, not DDL)

- `documents` — file metadata, current status, `data_classification`. Raw file immutable (INV-3),
  and so is the classification: it is set at upload and never updated.
- `extractions` — one row per pipeline run, stamped with `pipeline_version`. Append-only (INV-4).
- `corrections` — one row per human edit, referencing extraction + field. Append-only.
- `exports` — export jobs and their artifacts.
- `users` — id, name, email, password hash, role.
- `audit_log` — who did what, when.

Current extraction view = latest extraction + corrections applied on top. Never destructive.

**`documents.data_classification`** is `public | synthetic | restricted`, `NOT NULL DEFAULT
'restricted'`, and has **no `UPDATE` path** — reclassifying a document inserts a new `documents` row
with a new `document_id` and re-extracts against it. It is the one column on `documents` whose
wrongness has no detector (INV-6), so it gets extraction-table treatment rather than metadata
treatment. See [[ADR-007-classification-on-the-document-record]].

### How append-only is enforced

Not by convention, and not only in Python. Migration `0001` installs two triggers:

| Trigger | On | Refuses |
|---|---|---|
| `<table>_append_only` | `extractions`, `corrections`, `audit_log` | every `UPDATE` and `DELETE`, `restrict_violation` (INV-4) |
| `documents_immutable_columns` | `documents` | an `UPDATE` that changes `data_classification` (INV-6), `storage_path` or `sha256` (INV-3) |

Every other `documents` column — `status`, `document_type` — is still updatable, which is the point:
the row tracks progress, and only the three columns whose wrongness is undetectable are frozen.

`app/db/session.py` adds a `before_flush` listener that raises `AppendOnlyViolationError` /
`ImmutableColumnError` **before the statement reaches Postgres**, so the ORM path fails with a
message naming the invariant instead of a database error. The trigger is the guarantee; the listener
is the readable failure. Both are tested, because a guard tested only through the layer above it is
a guard you are trusting rather than checking.

**`TRUNCATE` bypasses both.** Row triggers do not fire on truncate, so a deployment must not grant
`TRUNCATE` on these tables to the application role. The test suite uses it deliberately, to reset
between cases — that is the only place it is legitimate.

### Ordering: `seq`, not `created_at`

`extractions` and `corrections` each carry a `seq BIGINT GENERATED BY DEFAULT AS IDENTITY UNIQUE`,
and "latest" everywhere means highest `seq`. `created_at` is `now()`, which is **transaction start
time** — two rows written in the same transaction tie exactly, and a tie broken on a random UUID
primary key makes the current view non-deterministic. That is a wrong-number-reaching-a-billing-sheet
bug with no error attached to it, so ordering does not depend on a clock.

### The current view is one query

`app/db/queries.py` holds `CURRENT_EXTRACTION_VIEW`: latest extraction by `seq`, its corrections
reduced to the newest per field, merged into `result.fields` in a single statement. A corrected
field comes back `verified: true`, `gate: null`, `source: {"origin": "human"}`; a field the
extraction never produced is added at `confidence: 0.0`. Corrections attached to a **superseded**
extraction do not leak into the current view — re-extraction resets the human edits, which is a
decision worth knowing rather than discovering.

### Money

There is **no money column.** Money lives inside `extractions.result` as a decimal string, which is
what [[EXTRACTION_SCHEMA.json]] specifies and what `backend/CLAUDE.md` means by "decimal string in
JSON". No table therefore has a `NUMERIC` amount, and — more to the point — no table anywhere has a
`FLOAT` or `DOUBLE PRECISION` column, which is asserted over `Base.metadata` in the test suite.

Two `CHECK` constraints stop money becoming a float at the layer where it actually could:

```sql
CHECK (NOT jsonb_path_exists(result, '$.fields.*.value ? (@.type() == "number")'))
CHECK (NOT jsonb_path_exists(result, '$.line_items[*].*.value ? (@.type() == "number")'))
```

A JSON number anywhere in a field value is rejected by Postgres. `11700.00` written as a number
instead of `"11700.00"` never lands, so the round-trip cannot silently become `11700.0`. When a
denormalised monetary column is eventually wanted for reporting, it is `NUMERIC(18, 2)` and it is a
new migration.

---

## 7. Failure modes and what happens

| Failure | Behaviour |
|---|---|
| OCR returns near-empty text | fail fast, `OCR_FAILED`, retryable. Do not send empty text to the LLM. |
| LLM emits invalid JSON | retry once with a repair prompt; then `EXTRACTION_FAILED`. Never regex-patch the JSON. |
| LLM omits a required field | field is `null`, `confidence: 0` — not a crash. |
| Gate fails | `needs_review`, affected fields `verified: false`. |
| Gate returns `format_only` | Not a failure. Field stays `verified: false` and reaches the reviewer as unconfirmed. CNIC/NTN/STRN always land here (§5). |
| GPU OOM | task retries with backoff; concurrency limit is the real fix. |
| Worker dies mid-task | Celery re-queues; idempotency (INV-4) makes this safe. |
| Restricted document reaches a hosted endpoint | Cannot. `HostedEndpointRefusedError` raises before the transport is invoked (INV-6). The task fails; no request is made. The guard reads the classification off the document record — it is not a call argument, so a caller cannot get it wrong. |
| Document has no `data_classification` | Refused on the `prototype` profile — default deny. An unclassified record is `restricted`. The upload endpoint rejects it earlier still, with `422 INVALID_CLASSIFICATION`. |
| Someone tries to reclassify a document | Rejected. The record is immutable and `PATCH .../extraction` returns `422 IMMUTABLE_FIELD`. Reclassification is a new upload ([[ADR-007-classification-on-the-document-record]]). |

---

## 8. Known weaknesses

Stated plainly so they are chosen, not discovered:

- **Single point of failure at the GPU.** No node dies gracefully here. Acceptable for internal use.
- **OCR merge boundary** (§4) is the most likely source of silent text corruption.
- **7B model on numerically dense documents.** The gates exist precisely because we do not trust it.
- **Local filesystem storage** blocks horizontal scaling the day a second node appears.
- **No streaming.** Large multi-page PDFs load fully into memory.

---

## 9. What would change this design

Write it down when it happens: a second GPU node, an external tenant, a p95 latency requirement,
or a document volume that makes the serial GPU stage the business bottleneck. None are true today.
