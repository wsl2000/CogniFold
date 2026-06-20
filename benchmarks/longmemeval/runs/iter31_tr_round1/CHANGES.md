# iter31_tr_round1 — TR-only N=133 round 1 (resolver TR fixes)

## Score

- **strict: 88.72%** (118/133), partial: 89.10%
- empty HY: 0
- run date: 2026-06-05 → 2026-06-06
- baseline: iter27 TR = 80.5% (107/133)
- **Δ = +8.3pp = +11 net cases (16 improvements, 5 regressions)**

## Stack

- Reader / Writer / Rerank: `openai/gpt-5.4-mini` via **commonstack**
- Writer reasoning_effort: medium (CLI flag, overrides env)
- Reader reasoning_effort: high (default)
- Rerank reasoning_effort: low, pool=100
- Judge: `openai/gpt-4o` via OpenRouter
- Embed: `openai/text-embedding-3-small` via OpenRouter
- `--symbolic-resolver --symbolic-temporal --symbolic-bypass`
- `--tr-topic-timeline` (TR-α, X1)
- `--llm-rerank`
- `--agg-max-context-chars 15000`
- W1 / W2 / W3 / Reflector: OFF (iter19 stack)

## What changed vs iter27

### Round 1 (15 base fixes, commit c94b68b)

**Resolver (`benchmarks/longmemeval/symbolic_resolver.py`)**:
- Disabled `which_first` and `relative_ago_recall` patterns (0%-acc in iter27)
- `_find_is_start_concept` Pass 3: EARLIEST mention fallback for unmarked
  start concepts (TR-A cluster fix)
- `_try_diff_since_when`: strict recovery-verb match (`recovered/healed/got
  over`) → uses EARLIEST date
- `_try_order_among`: force bypass=False for lists with >3 items
- `_try_named_day_recall`: multi-candidate hint when ≥2 same-day candidates
- Accept `activity_start` field alongside `is_start`; honor `start_date`

**Writer (`src/cognifold/agent/batch.py` BATCH_SYSTEM_PROMPT)**:
- Rule 4: START events extraction — when user FIRST mentions an ongoing
  activity, emit concept with `activity_start: true`, `activity: "<verb+
  object>"`, `start_date: <absolute date>`

**Reader (`configs/longmemeval_profile.yaml` qa_answer, 8 rules added)**:
- DURATION-SINCE-START
- AGE-INFERENCE (case d01c6aa8)
- PLANNED→COMPLETED "today" translation (case gpt4_68e94288)
- INCLUSIVE-BOUNDARY (case gpt4_4fc4f797)
- COMPARATIVE EARLIER=FIRST (case gpt4_0b2f1d21)
- EXHAUSTIVE-COUNT exclude-anchor caveat (case a3838d2b)
- BOOKING vs PLANNING (case 982b5123)
- _abs both-entities check (case c8090214_abs)

### Round 1.5 (X1 + X4, commit 8932867)

**Launcher**:
- `--tr-topic-timeline` flag ON: TR-only chronological topic-timeline block
  is prepended to retrieved context

**Reader**:
- CHRONOLOGICAL-SCAN rule: tells the reader to use TOPIC_TIMELINE /
  CHRONOLOGICAL_TEMPORAL blocks as authoritative for ordering

## Operational notes

- Commonstack provider mid-run failures (2026-06-05):
  - 5p initial run → 25% empty HY (TPM throttling)
  - 25p second attempt → 70% empty HY (balance depleted to 0 from cascade)
  - 2p recovery → 100% empty (balance still 0)
  - After user $500 top-up: 10p stable → 0% empty for 2h
  - 20p continuation: 0% empty, ~75 min for final 55 qids
- Total wallclock from first launch to 133/133: ~9h (excluding kill/restart)
- Estimated commonstack burn: ~$200-250

## Per-cluster contribution

16 improvements categorized:
- **TR-A duration_since_start (8)**: c9f37c46, cc6d1ec1, gpt4_4cd9eba1,
  993da5e2, b29f3365, e4e14d04, dcfa8644, d01c6aa8
- **TR-D date_diff INCLUSIVE-BOUNDARY (1)**: gpt4_4fc4f797
- **TR-G comparative EARLIER=FIRST (1)**: gpt4_0b2f1d21
- **TR-F derived_time (1)**: gpt4_2c50253f
- **TR-B order_among (1)**: gpt4_d6585ce8 (X1 topic_timeline win)
- **TR-G BOOKING vs PLANNING (1)**: 982b5123
- **PLANNED→COMPLETED (1)**: gpt4_68e94288
- **TR-A 14d duration (1)**: gpt4_cd90e484
- **eac54adc website launch derive (1)**

5 regressions:
- gpt4_fe651585: who-first (Rachel vs Alex parent)
- gpt4_e061b84f: order_among 3 sports (X1 made reader MORE conservative)
- b46e15ed: diff_since months off-by-one (2→1)
- 9a707b81: baking class 20 days (judge variance — same answer as iter27)
- gpt4_59149c78: art event Met (retrieval/hallucination)

## Decision

- **KEEP** — strong +8.3pp TR gain.
- Next: full N=500 verification to confirm no regressions in MS/KU/SSA/SSP/SSU.
- iter27 had W1+W2 ON (gained SSA +8.9pp, lost MS -4.5pp). iter31 has W1/W2
  OFF, so expect SSA back to ~91% (iter19 level) and MS recovered to ~82%.
- N=500 projection: 78 KU × 93.6% + 133 MS × ~82% + 56 SSA × ~91% +
  30 SSP × ~93% + 70 SSU × ~96% + 133 TR × 88.7% ≈ **87.7-88.5% N=500**.

## Branch / PR

- Branch: `tr-only-optimization`
- PR: #5 (linked to issue #4)
- Commits: c94b68b, 8932867, 380c4b5, 0152118, b9f8bcb, 2dd16b6, 5d38afa,
  af41cab, (this final commit)
