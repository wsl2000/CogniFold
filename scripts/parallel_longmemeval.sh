#!/usr/bin/env bash
# Run LongMemEval as N parallel batches with resume + merged single-dir output.
#
# Usage:
#   bash scripts/parallel_longmemeval.sh [N_PARALLEL] [STRATIFIED] [TOTAL_LIMIT]
#
# Examples:
#   bash scripts/parallel_longmemeval.sh 10              # 10 parallel, --stratified 14 --limit 80
#   bash scripts/parallel_longmemeval.sh 5 14 80         # 5 parallel, full 80 q
#   bash scripts/parallel_longmemeval.sh 10 84 500       # 10 parallel, full 500 q
#
# Behavior:
#   - Final output lands at benchmarks/longmemeval/output/ (same layout as a
#     non-parallel run: hypothesis.jsonl + metrics.json + wrong_cases.json).
#   - If output/hypothesis.jsonl already exists, only the missing qids get
#     processed (incremental resume).
#   - Per-batch scratch dirs (benchmarks/longmemeval/output_b*/) are deleted
#     after the merge succeeds.

set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a
# Route OpenAI SDK to OpenRouter when an OPENROUTER key is present.
if [ -n "${OPENROUTER_API_KEY:-}" ]; then
    export OPENAI_API_KEY="$OPENROUTER_API_KEY"
    export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
    unset OPENAI_ORGANIZATION
fi
if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "ERROR: neither OPENROUTER_API_KEY nor OPENAI_API_KEY set" >&2
    exit 1
fi

N_PARALLEL="${1:-10}"
STRATIFIED="${2:-14}"
TOTAL_LIMIT="${3:-80}"

BASE="benchmarks/longmemeval"
FINAL_DIR="$BASE/output"
mkdir -p "$FINAL_DIR" logs

# Step 1: determine TODO qids = target subset minus already-done.
TODO_FILE=$(mktemp)
trap "rm -f $TODO_FILE" EXIT
.venv/bin/python <<PY > "$TODO_FILE"
import json
import sys
from collections import defaultdict
from pathlib import Path

data = json.load(open("$BASE/data/longmemeval_s_cleaned.json"))
by_type = defaultdict(list)
for ex in data:
    by_type[ex.get("question_type", "?")].append(ex)
sel = []
for qt in sorted(by_type.keys()):
    sel.extend(by_type[qt][:$STRATIFIED])
sel = sel[:$TOTAL_LIMIT]
target_qids = [ex["question_id"] for ex in sel]

done_qids = set()
final_hyp = Path("$FINAL_DIR/hypothesis.jsonl")
if final_hyp.exists():
    for line in open(final_hyp):
        try:
            done_qids.add(json.loads(line)["question_id"])
        except Exception:
            pass

todo = [q for q in target_qids if q not in done_qids]
sys.stderr.write(
    f"Target {len(target_qids)} qids; already done {len(done_qids)}; todo {len(todo)}\n"
)
for q in todo:
    print(q)
PY

N_TODO=$(wc -l < "$TODO_FILE")
if [ "$N_TODO" -eq 0 ]; then
    echo "Nothing to do — all $TOTAL_LIMIT target qids already in $FINAL_DIR/hypothesis.jsonl"
    exit 0
fi

# Step 2: partition todo qids across N batches (don't oversubscribe).
if [ "$N_TODO" -lt "$N_PARALLEL" ]; then
    N_PARALLEL="$N_TODO"
fi
echo "Launching $N_PARALLEL parallel batches over $N_TODO todo qids"

CHUNK=$(( N_TODO / N_PARALLEL ))
REM=$(( N_TODO - CHUNK * N_PARALLEL ))

PIDS=()
BATCH_DIRS=()
START=1
for ((i=0; i<N_PARALLEL; i++)); do
    LIMIT=$CHUNK
    if [ "$i" -lt "$REM" ]; then LIMIT=$((CHUNK + 1)); fi
    END=$(( START + LIMIT - 1 ))
    IDS_CSV=$(sed -n "${START},${END}p" "$TODO_FILE" | paste -sd, -)
    OUTDIR="$BASE/output_b$((i+1))"
    LOG="logs/parallel_b$((i+1)).log"
    BATCH_DIRS+=("$OUTDIR")
    echo "  batch $((i+1)): $LIMIT qid  → $OUTDIR  (log: $LOG)"
    rm -rf "$OUTDIR"
    mkdir -p "$OUTDIR"
    nohup .venv/bin/python -u -m benchmarks.longmemeval.run_eval \
        --model openai:openai/gpt-5-mini \
        --writer-model openai:openai/gpt-4o-mini \
        --judge-model openai:openai/gpt-4o \
        --embedding openai:openai/text-embedding-3-small \
        --symbolic-resolver --symbolic-temporal --symbolic-bypass \
        --llm-rerank --rerank-model openai:openai/gpt-5-mini \
        --rerank-reasoning-effort low --rerank-pool 100 \
        --question-ids "$IDS_CSV" \
        --output-dir "$OUTDIR" \
        --batch-mode --llm-eval \
        > "$LOG" 2>&1 &
    PIDS+=($!)
    START=$(( END + 1 ))
done

echo "PIDs: ${PIDS[*]}"
echo "Waiting for all batches..."
FAIL=0
for pid in "${PIDS[@]}"; do
    if ! wait "$pid"; then
        echo "  batch pid=$pid failed (see logs/parallel_b*.log)"
        FAIL=$((FAIL+1))
    fi
done

# Step 3: merge all batch hypothesis.jsonl + existing into FINAL_DIR.
# Dedupe by question_id (latest write wins).
.venv/bin/python <<PY
import json
from collections import Counter
from pathlib import Path

final_hyp = Path("$FINAL_DIR/hypothesis.jsonl")
records = {}
if final_hyp.exists():
    for line in open(final_hyp):
        try:
            r = json.loads(line)
            records[r["question_id"]] = r
        except Exception:
            pass

for batch in sorted(Path("$BASE").glob("output_b*")):
    hp = batch / "hypothesis.jsonl"
    if not hp.exists():
        continue
    for line in open(hp):
        try:
            r = json.loads(line)
            records[r["question_id"]] = r
        except Exception:
            pass

with open(final_hyp, "w") as f:
    for r in records.values():
        f.write(json.dumps(r) + "\n")

c = Counter(r.get("verdict") for r in records.values())
total = len(records)
strict = c["CORRECT"] / total * 100 if total else 0
partial = (c["CORRECT"] + 0.5 * c["PARTIAL"]) / total * 100 if total else 0
with open("$FINAL_DIR/metrics.json", "w") as f:
    json.dump({
        "correct": c["CORRECT"], "partial": c["PARTIAL"], "incorrect": c["INCORRECT"],
        "error": c.get("ERROR", 0), "total": total,
        "score_strict": strict, "score_partial": partial,
    }, f, indent=2)

# Recompute wrong_cases.json
wrong = [r for r in records.values() if r.get("verdict") != "CORRECT"]
data = json.load(open("$BASE/data/longmemeval_s_cleaned.json"))
qt = {ex["question_id"]: ex.get("question_type", "?") for ex in data}
cats = Counter()
for w in wrong:
    cats["by_type:" + qt.get(w["question_id"], "?")] += 1
with open("$FINAL_DIR/wrong_cases.json", "w") as f:
    json.dump({
        "total_results": total,
        "total_wrong": len(wrong),
        "wrong_rate": len(wrong) / total if total else 0,
        "category_breakdown": dict(cats),
        "wrong_cases": wrong,
    }, f, indent=2, default=str)

print(f"merged: {total} results — {c['CORRECT']}/{total} = {strict:.2f}% strict, {partial:.2f}% partial")
PY

# Step 4: delete per-batch scratch dirs (only on success).
if [ "$FAIL" -eq 0 ]; then
    for d in "${BATCH_DIRS[@]}"; do
        rm -rf "$d"
    done
    echo "Cleaned up ${#BATCH_DIRS[@]} per-batch scratch dirs."
else
    echo "WARNING: $FAIL batches failed; per-batch dirs preserved at $BASE/output_b* for inspection."
    exit 1
fi

echo "Done. Final output at $FINAL_DIR/{hypothesis.jsonl,metrics.json,wrong_cases.json}"
