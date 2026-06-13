# iter05_full_stack

## Score
- **strict: 84.2%** (421/500)
- partial: 84.6%
- run date: 2026-06-02
- NET vs iter02 (83.2%): **+1.0 pts (+5 cases)**

## What changed vs iter02
**A — datetime precision**: `data["date"]` stores full ISO datetime; title prefix `[YYYY-MM-DD HH:MM]` so same-day KU sessions can be ordered.
**B — R9-A regex widening**: added bare verbs (attend, visit, do, replace, etc.) + adverb tolerance; replaced time-unit exclusion with explicit TR-marker (`ago`/`since i`/`between`/`before i`) suppression.
**B' — `--agg-max-context-chars 15000`**: aggregation Qs get 50-node retrieval + 15K ctx assembly (was 6K cap).
**R2 — `build_time_of_day_block`**: pin nodes with clock-time pattern (`\d{1,2}:\d{2}\s*(am|pm)`) to top of context for "what time do I X" questions.
**R3 — `build_proper_noun_block`**: pin nodes with capitalized multi-word names to top for "what breed / what's the name of / which X" questions.
**W1 — `_typed_attribute_pass`**: second writer pass per session, extracts typed attributes (time/date/duration/quantity/name) verbatim from user turns; gated by `--extract-typed-attributes` flag.
**Audit fix**: `MAX_CONTEXT_BYTES = 1_000_000` so the full reader context is preserved in hypothesis.jsonl (was 2048-char cap).

## NET vs iter02 (bar = 83.2%)
- delta correct: +5
- delta strict pts: +1.0

## Wrong-case breakdown by type
- knowledge-update: 4 (iter02 had 7)
- multi-session: 24 (iter02 had 30)
- single-session-assistant: 3 (iter02 had 4)
- single-session-preference: 2 (iter02 had 4)
- single-session-user: 2 (iter02 had 6)
- temporal-reasoning: **44** (iter02 had 33) ← REGRESSION

## Transition matrix
| | iter05 ✓ | iter05 ✗ |
|---|---|---|
| iter02 ✓ | 391 | 25 regressions |
| iter02 ✗ | 30 gains | 54 |

## Gains by type
+14 MS, +5 SSU, +4 TR, +3 KU, +3 SSP, +1 SSA

## Regressions by type
-15 TR, -8 MS, -1 SSP, -1 SSU

## Decision
**KEEP** the gains; **DIAGNOSE + FIX the TR regression in iter06**.

Root cause of TR regression (confirmed mid-run):
- Datetime precision in title (`[2023-02-12 19:30]`) led reader to treat dates as absolute timestamps and compute "X days ago" against system date (2026-06-01) instead of the dataset's question_date.
- Example: gpt4_af6db32f Super Bowl Q — iter02 "17 days", iter05 "1,205 days (as of 2026-06-01)".

Proposed iter06 fix: revert title prefix to date-only `[YYYY-MM-DD]` (keep `data["date"]` as full datetime so resolvers still get HH:MM precision). Reader sees date-only and trusts narrative for relative-time computations.

## Commit
- Local only — NOT pushed (TR regression first).
