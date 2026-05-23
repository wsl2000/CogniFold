#!/usr/bin/env bash
# Run LongMemEval in N parallel batches.
#
# Usage:
#   bash scripts/parallel_longmemeval.sh [N_PARALLEL] [STRATIFIED] [TOTAL_LIMIT]
#
# Examples:
#   bash scripts/parallel_longmemeval.sh 10              # default: 10 batches, full stratified
#   bash scripts/parallel_longmemeval.sh 10 14 80        # 10 batches of 80/10=8 questions each
#   bash scripts/parallel_longmemeval.sh 5 84 500        # 5 batches of 500/5=100 questions
#
# Each batch writes to benchmarks/longmemeval/output_b<i>/.  After all batches
# finish, merged_hypothesis.jsonl + merged_metrics.json land at
# benchmarks/longmemeval/output_merged/.

set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a
if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "ERROR: OPENAI_API_KEY not set" >&2
    exit 1
fi

N_PARALLEL="${1:-10}"
STRATIFIED="${2:-14}"   # 14 per type x 6 = 84; --limit cuts to TOTAL_LIMIT
TOTAL_LIMIT="${3:-80}"

# Round-down chunk size; last batch absorbs any remainder
CHUNK=$(( TOTAL_LIMIT / N_PARALLEL ))
REM=$(( TOTAL_LIMIT - CHUNK * N_PARALLEL ))

BASE="benchmarks/longmemeval"
mkdir -p logs

echo "Launching $N_PARALLEL parallel batches × ~$CHUNK questions each (total $TOTAL_LIMIT)"
PIDS=()
for ((i=0; i<N_PARALLEL; i++)); do
    OFFSET=$(( i * CHUNK ))
    LIMIT=$CHUNK
    # last batch picks up any remainder
    if [ "$i" -eq "$((N_PARALLEL - 1))" ]; then
        LIMIT=$(( CHUNK + REM ))
    fi
    OUTDIR="$BASE/output_b$((i+1))"
    LOG="logs/parallel_b$((i+1)).log"
    echo "  batch $((i+1)): offset=$OFFSET limit=$LIMIT  → $OUTDIR  (log: $LOG)"
    nohup .venv/bin/python -u -m benchmarks.longmemeval.run_eval \
        --model openai:gpt-5-mini \
        --writer-model openai:gpt-4o-mini \
        --judge-model openai:gpt-4o \
        --symbolic-resolver --symbolic-temporal --symbolic-bypass \
        --stratified "$STRATIFIED" \
        --offset "$OFFSET" \
        --limit "$LIMIT" \
        --output-dir "$OUTDIR" \
        --batch-mode \
        > "$LOG" 2>&1 &
    PIDS+=($!)
done

echo "PIDs: ${PIDS[*]}"
echo "Waiting for all batches..."
FAIL=0
for pid in "${PIDS[@]}"; do
    if ! wait "$pid"; then
        echo "  batch pid=$pid failed"
        FAIL=$((FAIL+1))
    fi
done

# Merge
MERGED="$BASE/output_merged"
mkdir -p "$MERGED"
cat "$BASE"/output_b*/hypothesis.jsonl > "$MERGED/hypothesis.jsonl"
N_TOTAL=$(wc -l < "$MERGED/hypothesis.jsonl")
echo "Merged $N_TOTAL records → $MERGED/hypothesis.jsonl"

# Recompute metrics from merged
.venv/bin/python <<PY
import json
from collections import Counter
hyps = [json.loads(l) for l in open("$MERGED/hypothesis.jsonl")]
c = Counter(h["verdict"] for h in hyps)
total = len(hyps)
strict = c["CORRECT"] / total * 100 if total else 0
partial = (c["CORRECT"] + 0.5 * c["PARTIAL"]) / total * 100 if total else 0
with open("$MERGED/metrics.json", "w") as f:
    json.dump({
        "correct": c["CORRECT"], "partial": c["PARTIAL"], "incorrect": c["INCORRECT"],
        "error": c.get("ERROR", 0), "total": total,
        "score_strict": strict, "score_partial": partial,
    }, f, indent=2)
print(f"merged metrics: {c['CORRECT']}/{total} = {strict:.2f}% strict, {partial:.2f}% partial")
PY

if [ "$FAIL" -gt 0 ]; then
    echo "WARNING: $FAIL batches failed; merged results may be incomplete"
    exit 1
fi
