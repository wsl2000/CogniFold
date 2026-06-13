# iter02 — full 84-wrong case-by-case analysis

iter02 strict 83.2% (416/500 correct, 84 wrong). This doc analyzes ALL 84 wrong cases, split into two layers using cross-iter agreement.

## Layer 1 — 49 hardcore (wrong in iter1 ∩ iter2 ∩ iter4)
See `../RUNS_INDEX.md` "Hardcore-49" section and the full per-case dump from previous analysis. These are the structural ceiling.

## Layer 2 — 35 recoverable (right in iter1 OR iter4 at least once)

Cross-iter pattern breakdown:

| Pattern | Count | Interpretation |
|---|---|---|
| iter1 ✓ / iter4 ✗ | 19 | iter1 had it, iter2 and iter4 lost it |
| iter4 ✓ / iter1 ✗ | 2 | iter4 P1 (named_day OBJECT) coincidentally helped |
| iter1 ✓ / iter4 ✓ | 14 | **Pure iter2 stochasticity victim** — both other iters correct |

### 14 pure-stochasticity victims (iter1 ✓ ∧ iter4 ✓ ∧ iter2 ✗)

These cannot be deterministically recovered with code — they're reader-side noise. Track to confirm if they vanish on rerun.

| qid | type | Q (short) | GT | iter2 wrong HYP (short) |
|---|---|---|---|---|
| f685340e | KU | tennis frequency previously/now | Sunday weekly→biweekly | conflated to "every other week previously" |
| 0a995998 | MS | clothing items to pick up | 3 | "Two" |
| 36b9f61e | MS | luxury items total spend | $2,500 | "$1,300" (missed Gucci $1200) |
| f0e564bc | MS | handbag+skincare total | $1,300 | "$800 minimum, can't confirm rest" |
| gpt4_59c863d7 | MS | model kits worked on | 5 | "Three" |
| 561fabcd | SSA | Radiation Amplified zombie name | Fissionator | "Contaminated Colossus" |
| 1da05512 | SSP | NAS now or wait | personal-storage context | generic NAS spec list |
| fca70973 | SSP | theme park weekend | personal-experience leveraged | generic Halloween advice |
| 19b5f2b3_abs | SSU | how long in Korea | not enough info | confabulated "about a week" |
| 36580ce8 | SSU | cold→? | bronchitis | "COVID-19" |
| 6613b389 | TR | months Rachel-engagement→anniversary | 2 | "0 months" |
| gpt4_59149c78 | TR | art event 2 weeks ago, where | Metropolitan Museum | "local farm stay" |
| gpt4_d6585ce9 | TR | who at music event last Saturday | my parents | "group of friends" |

### 19 i1✓ / i4✗ — likely also stochasticity

If rerank-ON in iter2 were the cause, iter4 (rerank OFF, same as iter1) should also be ✓. Since iter4 is ✗ here, it's not rerank — it's reader variance.

Notable:
- `6a1eabeb` (5K best time 25:50): **looks like judge inconsistency**. Both iter1 and iter2 HYPs contain "25:50" verbatim but iter1 judged CORRECT, iter2 judged INCORRECT. Phrasing-sensitive judge?
- `3c1045c8` (age vs dept average 2.5y): iter1 gave 2y estimate from partial info and got CORRECT; iter2 reader refused; iter4 reader refused. Loose judge tolerance for iter1.
- `28dc39ac` (game hours total 140): iter1 summed correctly to 140; iter2 missed one game and got 110.
- `577d4d32` (stop checking email 7pm): iter1 produced answer; iter2 refused; iter4 refused.

### 2 i4✓ / i1✗

- `d23cf73b` (cuisines 4): iter4 happened to count to 4. iter1 said 5. iter2 said 5. Noise, not from P1.
- `gpt4_93159ced_abs` (Google job abs): iter4 happened to refuse correctly. iter1 didn't refuse. Noise.

**Conclusion**: iter4 has zero deterministic wins. Its -6 NET is real.

## Aggregated insight across hardcore-49 + recoverable-35

Combined failure-mode totals (84 wrong cases):

| Mode | Total | Hardcore | Recoverable |
|---|---|---|---|
| count off (writer found partial / reader undercount) | 27 | 19 | 8 |
| writer-missed-fact (reader refuses) | 25 | 19 | 6 |
| TR ordering / chronological | 13 | 8 | 5 |
| TR number off (days/weeks/months) | 5 | 0 | 5 |
| specific fact wrong (entity confusion) | 11 | 1 | 10 |
| abs confabulation | 3 | 2 | 1 |

### Top-3 actionable clusters (ranked by ROI)

1. **count-off (27 cases, ~5.4 pts)** — needs writer to label co-typed events so resolver can do count_distinct. **High risk**: requires writer schema change, profile.yaml rules 9+10 already proven dangerous (graph_nodes drop). Try reader-side hint first: "if asked 'how many X', list all events of type X before counting".

2. **writer-missed-fact (25 cases, ~5.0 pts)** — upstream extraction gap. Writer model upgrade is the obvious lever but gpt-5-mini = 3min/call (unusable). Possible alternatives: try gpt-4.1-mini? Or smaller, targeted writer prompt additions for recurring missed patterns (clinic, doctor appt, embroidery store name).

3. **TR ordering (13 cases, ~2.6 pts)** — implementable as `order_among` resolver. Sort [topic_eq] nodes by ts asc. Lower risk than #1 or #2.

### Judge-variance suspicion

`6a1eabeb` 25:50 case suggests the judge (gpt-4o) can be phrasing-sensitive. Worth a small experiment: re-judge iter2's wrong set with the SAME judge model and see how many flip to CORRECT. If non-trivial flip rate, judge variance is part of the noise floor.

## Forbidden retries (confirmed harmful)

- profile.yaml rules 9+10 (TYPED ATTRIBUTE VERBATIM / DURATION ANCHOR) — writer graph_nodes drops 1094→546
- broad qa_answer refusal rules — regresses preference cluster
- broad `_ASSISTANT_RECALL_TRIGGER` — regresses preference cluster

## Next iter targets (in order of suggested ROI)

1. iter05 — `_try_latest_value` debug for KU 07741c45/a2f3aa27 (low risk, 2 cases)
2. iter06 — `order_among` resolver for chronological-order TR (medium risk, 4-13 cases)
3. iter07 — judge-variance experiment (re-judge wrong set, no code change)
4. iter08 — reader-side count hint for count-off cluster (medium risk, 27 cases potential)
