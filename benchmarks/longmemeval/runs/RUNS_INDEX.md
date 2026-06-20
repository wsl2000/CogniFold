# LongMemEval — Iteration Runs Index

All N=500 runs over the cleaned dataset (`data/longmemeval_s_cleaned.json`).
Each row links to a folder containing `hypothesis.jsonl`, `metrics.json`, `wrong_cases.json`, `CHANGES.md`.

## Stack (constant across iters unless noted)
- Reader: `openai:openai/gpt-5-mini` (reasoning_effort=high via "gpt-5" substring auto-rule)
- Writer: `openai:openai/gpt-4o-mini`
- Judge: `openai:openai/gpt-4o`
- Embed: `openai:openai/text-embedding-3-small`
- Routing: OpenRouter (OPENAI_BASE_URL=https://openrouter.ai/api/v1)
- Driver: `scripts/parallel_longmemeval.sh 100 84 500 <iter_label>` (100 parallel × 5 qids)

## Runs

| Iter | Folder | Strict | NET vs prev | Decision | Commit |
|---|---|---|---|---|---|
| 00 | [iter00_baseline_df644ee](./iter00_baseline_df644ee/) | 80.0% | — | reference | df644ee |
| 01 | [iter01_TR_resolver_or](./iter01_TR_resolver_or/) | 83.0% | **+3.0 pts** | KEEP (folded into iter02) | — |
| 02 | [iter02_qa_distinct_entity_or](./iter02_qa_distinct_entity_or/) | **83.2%** ★ | +0.2 pts | KEEP — current prod | f5ec922 |
| 03 | _(lost — not snapshotted)_ | — | — | reverted | — |
| 04 | [iter04_named_day_object_local](./iter04_named_day_object_local/) | 82.0% | -1.2 pts | REVERT — do not push | ae16124 (local) |
| 05 | [iter05_full_stack](./iter05_full_stack/) | 84.2% | **+1.0 pts** | KEEP gains; fix TR regression in iter06 | local only |

★ = current best on remote `opennorve/longmemeval-iter`.

## Hardcore-49 (wrong in iter1 ∩ iter2 ∩ iter4)

Theoretical ceiling on current stack = **90.2%** (1 - 49/500). See breakdown by failure mode:

| Failure mode | Count | Disposition |
|---|---|---|
| count-wrong (writer found partial, reader undercounts) | 19 | needs writer-side enumeration support; high risk |
| writer-missed-fact (reader correctly refuses) | 19 | upstream extraction gap; needs better writer or chunk strategy |
| TR-other (chronological-order / strong-date-anchor) | 8 | partly addressable: `order_among` resolver + better named_day |
| abs-confabulates (reader should refuse but doesn't) | 2 | needs scoped anti-confab rule (broad rules regressed in iter4) |
| specific-fact-wrong (KU latest-value miss) | 1 | check why `latest_value` resolver didn't fire |

Per-type:
- TR: 22 / 133 hardcore
- MS: 20 / 133 hardcore
- KU: 3 / 78 hardcore
- SSA: 2 / 56 hardcore
- SSU: 2 / 70 hardcore

Stochasticity floor: ~35 cases/run from reader non-determinism. Any delta < 7 cases is in the noise.

## Forbidden changes (regressions previously confirmed)

- **profile.yaml rules 9+10** (TYPED ATTRIBUTE VERBATIM, DURATION ANCHOR): cause writer `graph_nodes` median to drop from ~1094 → 546 (output JSON truncation). NEVER reintroduce.
- **Broad `qa_answer` refusal rules**: any "if uncertain refuse" rule broader than P1 distinct-entity caused cluster of preference-question regressions.
- **Broad `_ASSISTANT_RECALL_TRIGGER`**: removing the past-conversation anchor regressed preference-cluster cases.

## How to run the next iter

```bash
# 4th arg = iter label → outputs to runs/iterNN_<label>/
bash scripts/parallel_longmemeval.sh 100 84 500 "iter05_order_among"
```

Then write `runs/iter05_order_among/CHANGES.md` documenting:
1. What changed in code (resolver/profile/run_eval)
2. Why (target failure cluster from hardcore-49)
3. NET vs iter02 (the bar to beat is 83.2%)
4. KEEP / REVERT decision

## Branch policy (preserved)
- Push only to `opennorve/longmemeval-iter`
- Never push to `main`, `iter`, `public-release`, `cognifold-dev`
- Never push iter3 / iter4 (both negative NET)
