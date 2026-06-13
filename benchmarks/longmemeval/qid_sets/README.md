# Canonical qid sets

Stable qid subsets used for direct A/B comparison across runs. Each file
is plain-text, one question_id per line. Use via the launcher env var:

    QID_LIST_FILE=benchmarks/longmemeval/qid_sets/<file>.txt \
        bash scripts/parallel_longmemeval.sh <N_PARALLEL> 200 500 <label>

The launcher's `QID_LIST_FILE` path overrides the stratified selection.

## `hard100.txt`

100 question_ids selected as "consistently hard across our iteration
history". Selection methodology:

1. For each qid, count how many of these five runs got it wrong (verdict
   != CORRECT):
   - iter02 (gpt-5-mini reader, early stack)
   - iter05 (full_stack)
   - iter19 (current public-release baseline, 86.72% N=500)
   - iter27 (gpt-5.4-mini + W1+W2, 86.80% N=500)
   - iter28b_TR_only_OR (133 TR qids, gpt-5.4-mini)
2. Keep only qids covered in ≥2 runs (filters out single-run noise).
3. Within each question_type, sort by wrong-count desc; take top 17.
   When a type has fewer than 17 wrong qids, fall back to other types'
   overflow sorted by wrong-count.
4. Cap at 100.

Distribution at creation time:

| type | count | avg #runs-wrong |
|---|---|---|
| temporal-reasoning | 36 | 3.8 |
| multi-session | 32 | 2.9 |
| knowledge-update | 9 | 2.2 |
| single-session-user | 9 | 1.4 |
| single-session-preference | 8 | 1.4 |
| single-session-assistant | 6 | 2.0 |

68% are MS+TR — our weakest types. 13 qids were wrong in ALL 5 runs.

Baseline strict on hard100 (from existing run hypothesis files):

| run | strict |
|---|---|
| iter02 | 22% |
| iter05 | 36% |
| iter19 | 38% |
| iter27 | 43% |

A run that scores ≥60% on hard100 is showing real architectural change,
not stochastic reroll noise (±5pp band on N=100 is typical for the
reasoning-reader stack).
