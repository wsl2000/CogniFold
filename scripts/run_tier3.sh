#!/usr/bin/env bash
# Tier 3 runner — Mastra-style observational memory on our concept graph.
#
# Routing (split across 2 providers in a single process via WRITER/READER/
# JUDGE_API_KEY env overrides):
#   Writer  → commonstack ak-          (openai/gpt-4o-mini, cheap, cap ~50 RPM)
#   Reader  → OpenAI direct (sk-proj-) (gpt-5-mini, reasoning_effort=high)
#   Judge   → OpenAI direct (sk-proj-) (gpt-4o, canonical)
#
# Usage:
#   bash scripts/run_tier3.sh <QID_LIST_FILE> <LABEL> [N_PARALLEL]
#
# Example:
#   bash scripts/run_tier3.sh benchmarks/longmemeval/qid_sets/hard100.txt \
#        tier3_hard100_smoke 5
#
# Behavior:
#   - Skips retrieval, rerank, embedding (Tier 3 mode dumps full graph as
#     observation list).
#   - Resumes from <FINAL_DIR>/hypothesis.jsonl (incremental, same as the
#     standard launcher).
#   - Per-batch outputs at output_t3_b<i>/, merged into runs/<LABEL>/.

set -uo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a

QID_LIST_FILE="${1:?need QID_LIST_FILE path}"
LABEL="${2:?need LABEL}"
N_PARALLEL="${3:-5}"

if [ -z "${COMMONSTACK_API_KEY:-}" ]; then
    echo "ERROR: COMMONSTACK_API_KEY missing in .env" >&2
    exit 1
fi
if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "ERROR: OPENAI_API_KEY missing in .env" >&2
    exit 1
fi

# Per-role routing — each chat call's call_llm reads these via config.
export WRITER_API_KEY="$COMMONSTACK_API_KEY"
export WRITER_BASE_URL="https://api.commonstack.ai/v1"
export READER_API_KEY="$OPENAI_API_KEY"
export READER_BASE_URL=""    # OpenAI direct
export JUDGE_API_KEY="$OPENAI_API_KEY"
export JUDGE_BASE_URL=""     # OpenAI direct

export TIER3_OBSERVATIONS=1

# The global OPENAI_* should NOT be set to commonstack (would break embed
# config validation even though we don't use embed). Keep them as the
# OpenAI-direct fallback.
export OPENAI_API_KEY="$OPENAI_API_KEY"
unset OPENAI_BASE_URL
unset OPENAI_ORGANIZATION

BASE="benchmarks/longmemeval"
FINAL_DIR="$BASE/runs/$LABEL"
mkdir -p "$FINAL_DIR" logs

echo "Tier 3 run: $LABEL"
echo "  qid file: $QID_LIST_FILE"
echo "  parallel: $N_PARALLEL"
echo "  writer:   commonstack → openai/gpt-4o-mini"
echo "  reader:   OpenAI direct → gpt-5-mini high"
echo "  judge:    OpenAI direct → gpt-4o"
echo "  embed:    none (Tier 3 skips retrieval)"
echo "  output:   $FINAL_DIR"

# Step 1: compute TODO qids (resume support).
TODO_FILE=$(mktemp)
trap "rm -f $TODO_FILE" EXIT
.venv/bin/python <<PY > "$TODO_FILE"
import json, sys
from pathlib import Path
text = Path("$QID_LIST_FILE").read_text().strip()
raw = [t.strip() for chunk in text.split("\n") for t in chunk.split(",")]
target_qids = [q for q in raw if q]
done = set()
final_hyp = Path("$FINAL_DIR/hypothesis.jsonl")
if final_hyp.exists():
    for line in open(final_hyp):
        try:
            done.add(json.loads(line)["question_id"])
        except Exception:
            pass
todo = [q for q in target_qids if q not in done]
sys.stderr.write(f"target={len(target_qids)} done={len(done)} todo={len(todo)}\n")
for q in todo:
    print(q)
PY

N_TODO=$(wc -l < "$TODO_FILE")
if [ "$N_TODO" -eq 0 ]; then
    echo "Nothing to do — all qids already in $FINAL_DIR/hypothesis.jsonl"
    exit 0
fi
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
    OUTDIR="$BASE/output_t3_b$((i+1))"
    LOG="logs/tier3_b$((i+1)).log"
    BATCH_DIRS+=("$OUTDIR")
    echo "  batch $((i+1)): $LIMIT qid → $OUTDIR (log: $LOG)"
    rm -rf "$OUTDIR" && mkdir -p "$OUTDIR"
    nohup .venv/bin/python -u -m benchmarks.longmemeval.run_eval \
        --model openai:gpt-5-mini \
        --writer-model openai:openai/gpt-4o-mini \
        --judge-model openai:gpt-4o \
        --embedding openai:text-embedding-3-small \
        --no-symbolic-temporal \
        --symbolic-resolver --symbolic-bypass \
        --question-ids "$IDS_CSV" \
        --output-dir "$OUTDIR" \
        --batch-mode --llm-eval \
        > "$LOG" 2>&1 &
    PIDS+=($!)
    START=$(( END + 1 ))
done

echo "PIDs: ${PIDS[*]}"
echo "Waiting..."
FAIL=0
for pid in "${PIDS[@]}"; do
    if ! wait "$pid"; then
        echo "  batch pid=$pid failed (see logs/tier3_b*.log)"
        FAIL=$((FAIL+1))
    fi
done

# Step 3: merge.
.venv/bin/python <<PY
import json
from collections import Counter
from pathlib import Path

final_hyp = Path("$FINAL_DIR/hypothesis.jsonl")
records = {}
if final_hyp.exists():
    for line in open(final_hyp):
        try:
            r = json.loads(line); records[r["question_id"]] = r
        except Exception:
            pass
for batch in sorted(Path("$BASE").glob("output_t3_b*")):
    hp = batch / "hypothesis.jsonl"
    if not hp.exists():
        continue
    for line in open(hp):
        try:
            r = json.loads(line); records[r["question_id"]] = r
        except Exception:
            pass

with open(final_hyp, "w") as f:
    for r in records.values():
        f.write(json.dumps(r) + "\n")

c = Counter(r.get("verdict") for r in records.values())
total = len(records)
strict = c["CORRECT"]/total*100 if total else 0
partial = (c["CORRECT"] + 0.5*c["PARTIAL"])/total*100 if total else 0
with open("$FINAL_DIR/metrics.json", "w") as f:
    json.dump({
        "correct": c["CORRECT"], "partial": c["PARTIAL"], "incorrect": c["INCORRECT"],
        "error": c.get("ERROR", 0), "total": total,
        "score_strict": strict, "score_partial": partial,
    }, f, indent=2)
print(f"merged: {total} results — {c['CORRECT']}/{total} = {strict:.2f}% strict, {partial:.2f}% partial")
PY

if [ "$FAIL" -eq 0 ]; then
    for d in "${BATCH_DIRS[@]}"; do rm -rf "$d"; done
    echo "Done. Result at $FINAL_DIR/{hypothesis,metrics}.json"
else
    echo "WARNING: $FAIL batches failed; per-batch dirs preserved." >&2
    exit 1
fi
