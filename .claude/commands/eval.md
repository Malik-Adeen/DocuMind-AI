---
description: Run the eval harness and record the result
argument-hint: [optional run label]
disable-model-invocation: true
---

Run `CodeBase/backend/evals/run_eval.py`. Label: $ARGUMENTS

The rules for what these numbers mean, which fields are critical, and the release gate thresholds
are in `Docs/EVAL_AND_GOLDEN_SET.md`. Read it before interpreting anything — do not restate the
thresholds from memory.

1. Run the harness. Quote its actual output. `run_eval.py` exits non-zero on gate failure; report
   the exit code.
2. Write the full result to `CodeBase/backend/evals/history/` (git-tracked; the golden set itself is not).
3. Report the **per-field** table — precision, recall, hallucination rate. Never a single
   document-level number: `EVAL_AND_GOLDEN_SET.md` §1 explains why that number lies.
4. Compare against the most recent file in `CodeBase/backend/evals/history/`. **Any critical field down more than
   2 points is a regression — say so loudly, at the top, before the table.** Do not bury it.

If the run touched `sealed/`, say so explicitly. Tuning against sealed converts it from an eval
set into training data and the numbers stop being quotable.
