# iter04 — named_day_recall OBJECT extraction + relative_ago threshold + verb-match guard

## Score
- **strict: 82.0%** (410/500)
- partial: ~82.7%
- NET vs iter02: **-6 correct (-1.2 pts)** ← REGRESSION

## What changed vs iter02
`benchmarks/longmemeval/symbolic_resolver.py` (local commit `ae16124`):

- **P1**: `named_day_recall` OBJECT-noun extraction. Multiple regex approaches to extract the object noun from question patterns:
  - "X to/with/at/from the …"
  - "X was the …"
  - "X of …"
  - "X last/past day"
  Goal: improve recall on "what was the X" questions with strong date anchor.

- **P2**: `relative_ago_recall` similarity threshold raised from `0.34 → 0.5` (tighten to avoid false-match bypass).

- **P3**: verb-match guard in `_try_diff_ago` and `_try_diff_since`. Extracted verb after "did I"/"since I" and required a stem variant to appear in the matched concept (anti-mismatch).

- `scripts/parallel_longmemeval.sh`: `--llm-rerank` reverted to OFF.

## Result analysis
- P3 verb-match guard did NOT help any target case (the failures it was meant to catch were caused by different upstream problems).
- ~22 random regressions appeared from reader stochasticity on cases that were previously correct.
- iter4 wrong set = 90 (vs iter2 wrong = 84). The shifts were mostly noise, not signal.

## Decision
**REVERT.** Do NOT push commit `ae16124`. Keep iter02 (f5ec922) as the production state on `opennorve/longmemeval-iter`.

## Lesson
- Reader stochasticity ≈ ±35 cases/run on this stack. Any "improvement" with delta < ~7 cases is in the noise floor and not trustworthy without a second confirmation run.
- The 49 hardcore qids (wrong in iter1 ∩ iter2 ∩ iter4) are the real ceiling. See `../RUNS_INDEX.md` "hardcore-49" section.
