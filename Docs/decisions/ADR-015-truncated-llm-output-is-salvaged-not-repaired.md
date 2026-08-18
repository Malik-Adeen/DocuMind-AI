---
status: accepted
owner: Adeen
last_reviewed: 2026-08-18
version: 1.0.0
---

# ADR-015 — A truncated LLM response is salvaged and routed to needs_review, not repaired-by-retry and not failed outright

**Status:** accepted · **Decided:** 2026-08-18
**Supersedes:** — · **Reverses:** [[ARCHITECTURE]] §7's "never regex-patch the JSON" rule, narrowly,
for the truncation-salvage path only (see Reason) · **Related:**
[[ADR-012-provenance-merge-was-dead-code]],
[[ADR-011-terminal-status-requires-positive-verification-evidence]], [[ADR-004-format-only-gate-state]]

## Context

`app/pipeline/llm/transport.py`'s `HostedChatTransport.__call__` returned only `content`, discarding
the rest of the response body — the same pattern `complete_full()` was later built to fix for the
eval harness (`id`/`provider`, [[JOURNAL]] 2026-08-10), except production's `LLMClient.complete()`
never adopted `complete_full()`. `finish_reason` lived in that discarded body the whole time.

The consequence: a response cut short by `max_tokens` (hard-capped at 2000) surfaced identically to
a genuinely malformed one. `complete_with_repair()` (`app/pipeline/llm/repair.py`) does
`json.loads(raw)`; a truncated response fails that with `json.JSONDecodeError`, indistinguishable
from any other parse failure, and triggers the same repair-prompt retry — which resends the
original prompt *plus* the entire truncated (near-2000-token) bad output *plus* an error message, a
strictly longer request with the same odds of truncating again. After the retry budget (1) is
exhausted, `RepairExhaustedError` surfaces as a generic `ExtractionFailedError`, and the document is
`failed` — full stop, whatever the model did manage to extract discarded.

**Measured, not estimated** (`~/Downloads/Azeem.jpeg`, a real, dense, phone-scanned purchase order —
17 fields, 5 line items, a lengthy terms-and-conditions block): calling
`HostedChatTransport.complete_full()` directly, 4 of 5
calls returned `finish_reason: "length"` at exactly `completion_tokens: 2000` with invalid JSON; the
5th succeeded at `completion_tokens: 1340`. A wider sample of 13 real completions (mixed capped and
diagnostic-uncapped) put natural completion length at 1340–3201 tokens for this document — `2000`
sat below the observed maximum, which is the direct cause of the ~45% failure rate. Inspecting a
2329-token natural response showed it correctly enumerating all 5 real line items on the source
document; a capped, truncation-prone response tended to enumerate only 2 — the token ceiling was not
just causing failures, it was tacitly rewarding incomplete extractions that happened to fit.

## Decision

**Truncation is now its own detected, distinct failure mode, handled in three parts.**

**1. Detect it, in the transport, from the field that was already being computed and discarded.**
`HostedChatTransport.__call__` checks `finish_reason` before returning, and raises
`TruncatedResponseError(content)` — carrying the truncated text — when it is `"length"`. The
`Callable[[str], str]` contract `LLMClient.complete()` and `complete_with_repair()` are built around
is unchanged; this is one more way the callable can fail, the same as `HostedLLMError` already is.

**2. Bypass the repair-prompt loop entirely — do not retry with a longer request.**
`orchestrator.py::extract()` catches `TruncatedResponseError` around the `complete_with_repair()`
call, not inside it. A truncated response never enters the retry loop and never spends a second
hosted-LLM call resending itself.

**3. Salvage what finished generating; drop what didn't; never guess.** This step is, plainly, a
form of the thing [[ARCHITECTURE]] §7 says never to do: `_salvage_truncated_output()` runs
`json_repair.repair_json()` (new dependency, `json-repair` — chosen over hand-rolling a
truncated-JSON-and-escaped-string parser for a reviewer-facing path where a subtle bug would
silently corrupt data) to close out whatever JSON structure the model had actually finished
writing, then patches it into something parseable. That is a regex-shaped operation regardless of
whether `json_repair`'s own implementation happens to use `re` — the point of §7's rule was never
the literal module, it was "don't heuristically fix broken model output and trust the result as if
the model had said it." This ADR reverses that rule for this one path; see Reason for why, and
what stops it from being the thing the rule was written to prevent. Every field and line-item
entry is then
individually re-validated against its own schema fragment (`$defs/field` / `$defs/money_field` from
`EXTRACTION_SCHEMA.json`) — an entry missing a required key (`value`/`confidence`/`verified`/
`source`) because generation stopped mid-object is dropped, not kept with holes. If nothing survives
— zero fields, zero line items, or the document itself fails validation (`document_type` missing or
malformed) — salvage returns nothing and the caller raises `ExtractionFailedError`, exactly the
existing behaviour for any other unrecoverable response. **This is the line between "cut short" and
"unusable": schema validation on the recovered subset decides it, not a guess about how much text is
"probably enough."**

When salvage succeeds, the extraction is **forced to `needs_review`** regardless of what the
ordinary heuristic (`_needs_review()`) would compute on its own — a salvaged response must never be
promoted to `complete`, even if every field that happened to survive also happens to gate-verify.
`review.reason` is set to `"llm_output_truncated"` (`EXTRACTION_SCHEMA.json` declared `review.reason`
early with exactly this kind of example and nothing had ever populated it — this is the first).
`document.error` is populated with `LLM_OUTPUT_TRUNCATED` via the existing envelope
(`app/core/errors.py`) — the one case where `error` is non-null on a document that is not `failed`.

**`hosted_llm_max_tokens` becomes a `Settings` field, defaulted to 4000.** Chosen from the measured
1340–3201 range above — roughly 2x the typical case, with headroom above every sample observed —
not doubled on instinct. Externalized (`.env` / `HOSTED_LLM_MAX_TOKENS`) rather than left as a
dataclass literal, matching `hosted_llm_model` / `llm_max_repair_retries`, because it is a real
cost/latency lever and the whole premise of this ADR is that a hardcoded, unmeasured value at this
layer is exactly what caused the problem.

## Reason

**The salvage is itself a fallible check, and a fallible check must not be authoritative over the
document — the same reasoning [[ADR-012-provenance-merge-was-dead-code]] already established for
provenance-merge's exact-substring match.** `json_repair`'s best-effort reconstruction, and the
per-entry schema re-validation on top of it, can both be wrong about how much of a cut-off response
is genuinely trustworthy. Forcing `needs_review` — never `complete` — on every truncated-and-salvaged
document is the direct application of that precedent to a second fallible-recovery mechanism: it may
flag a document that would have been fine, but it must never wave one through that wasn't.

**Why reversing "never regex-patch the JSON" is safe here, and only here.** The blanket rule exists
because a heuristic patch that produces syntactically valid JSON says nothing about whether the
*values* inside it are still what the model meant — a patch could close a truncated string one
character early, or one late, and the result would parse cleanly while silently containing the
wrong number. That risk is real and general, which is why the rule stays in force for every other
case: a garbled-but-*not*-truncated response is still corrected by asking the model itself to fix
it (the repair prompt), never by code patching its text. What is different about the truncation
path, specifically, is the second gate this decision insists on and a bare regex-patch would not
have: `_salvage_truncated_output()` does not stop at "does this parse." Every recovered field and
line-item entry is independently re-validated against `EXTRACTION_SCHEMA.json`'s own `$defs/field`
/ `$defs/money_field` fragment — the identical schema every complete, untruncated response is
already held to — and anything that doesn't validate is dropped, not kept-and-trusted. A field that
survives salvage is not "probably fine because the JSON parsed"; it is a field with a well-formed
`value`/`confidence`/`verified`/`source` shape, indistinguishable in structure from one the model
emitted whole. The mitigation is not "we patched it carefully" — carefulness is not verifiable after
the fact. It is "we patched it, then required every surviving piece to independently pass the same
check a normal response has to pass," which is a different, checkable claim. That is what makes this
narrow enough to reverse the rule for, and why it does not license patching JSON anywhere else in
this pipeline.

**Bypassing the repair loop, specifically, is not an optimization — the loop is actively
counterproductive here.** Repair-prompt retry exists for a genuinely different failure shape: the
model produced syntactically or semantically *wrong* output that a corrective nudge might fix. A
truncated response is not wrong, it is *unfinished* — the correct response to "you ran out of room"
is not "here is your own too-long output again, please shorten it," which is what the repair prompt
does by construction (original prompt + the entire bad output + an error string, strictly longer
than the request that just failed). The observed pattern of repeated truncations landing at nearly
the same character position on retry (from the deskew task's earlier real-run report) is exactly
what this predicts.

**Killing the document outright is harsher than any gate.** [[ARCHITECTURE]] §7's failure-mode table
already draws this line for every other check that can be wrong about its own inputs: a failed gate,
or `format_only`, routes to `needs_review` with the specific field unverified — it does not fail the
document. A truncated-but-partially-recovered response is the same shape of problem at the
extraction level instead of the field level: real, LLM-produced content exists, it is simply
incomplete, and a reviewer with the recovered fields in front of them is in a strictly better
position than a reviewer with nothing and a generic "invalid JSON" log line.

## Consequences

**Accepted:**

- A dense document that previously failed outright roughly 45% of the time now either completes
  cleanly (more often, given the 4000-token ceiling), or — on the residual cases that still exceed
  it — reaches `needs_review` with whatever the model had finished writing, instead of `failed` with
  nothing.
- `needs_review_count` (API_CONTRACT §7) and any downstream tooling that reads `document.error` now
  has to know one `error` cause implies `needs_review` rather than `failed` — documented explicitly
  in API_CONTRACT §3 as the single named exception, not left implicit.
- New dependency: `json-repair` (core, not the `ocr` group — the LLM path runs on every profile).
  Small, dependency-free itself, purpose-built for this exact problem class (LLM output repair)
  rather than a hand-rolled truncated-JSON parser this project would otherwise own and maintain.
- `HostedChatTransport.max_tokens` default and `Settings.hosted_llm_max_tokens` default both moved
  to 4000 together — no code path is left quietly relying on the old 2000 literal.

**Rejected alternatives:**

- *Just raise `max_tokens`, leave detection as-is.* Rejected as insufficient on its own: any finite
  ceiling can still be exceeded, and without `finish_reason` detection the failure mode stays
  indistinguishable from genuine malformation — the more serious defect named at diagnosis time.
  Raising the ceiling without fixing detection would have quieted the symptom on this one document
  while leaving the actual gap in place for the next one.
- *Retry truncation with the original (non-repair) prompt, hoping for a shorter completion.* The
  measured data shows real run-to-run variance in completion length, so this would sometimes work —
  but it is silent, costs a full extra hosted-LLM call per attempt, and does not change what happens
  when the retry *also* truncates. Salvaging what already exists is strictly cheaper and does not
  depend on getting lucky twice.
- *Hard-fail every truncated response, matching the pre-existing behaviour minus the wasted repair
  retry.* Rejected per Reason above and per direct instruction: a partial extraction is useful to a
  reviewer, and failing the document outright is harsher than any gate in this pipeline is allowed
  to be.
- *Trust `json_repair`'s output once it parses, with no further validation.* This was the first
  shape of this decision, and it is exactly the thing [[ARCHITECTURE]] §7's rule forbids with
  nothing to justify the exception — a syntactically valid patch with no check on whether the
  values inside it are real. Rejected before implementation; the per-entry schema re-validation in
  the Decision above is not an enhancement on top of this alternative, it is the reason this ADR is
  allowed to reverse the rule at all.

## Revisit when

- A document is observed exceeding 4000 output tokens naturally (not just truncated at the old 2000
  ceiling) — the salvage path will still work, but the ceiling would need re-measuring against new
  evidence, not incrementing again on instinct.
- `evals/run_eval.py` exists (still does not, per [[ADR-012-provenance-merge-was-dead-code]]'s own
  open item) — truncation rate and salvage-recovery rate belong alongside `resolved / claimed` as a
  golden-set-level signal, not just a per-request log line.
