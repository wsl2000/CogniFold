#!/usr/bin/env bash
# iter32 MS-focus run — R7+R9 ledger + M1/M2/M3 + top gate.
# MEDIUM writer + default HIGH reader (run_eval default).
# 3 parallel workers, MS=133 qids.
#
# Stack:
#   Reader:    openai:openai/gpt-5.4-mini (default high effort)
#   Writer:    openai:openai/gpt-5.4-mini at medium effort
#   Rerank:    openai:openai/gpt-5.4-mini at low effort
#   Judge:     openai:openai/gpt-4o (OpenRouter)
#   Embed:     text-embedding-3-small (OpenRouter)
#
# Usage:
#   bash scripts/run_iter32_ms_medium.sh <LABEL> [N_PARALLEL]

set -uo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a

LABEL="${1:?need LABEL}"
N_PARALLEL="${2:-3}"
QID_LIST_FILE="benchmarks/longmemeval/qid_sets/ms_only.txt"
LABEL_SAFE="$(printf '%s' "$LABEL" | tr -c 'A-Za-z0-9._-' '_')"

if [ -z "${COMMONSTACK_API_KEY:-}" ]; then
    echo "ERROR: COMMONSTACK_API_KEY missing in .env" >&2; exit 1
fi
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
    echo "ERROR: OPENROUTER_API_KEY missing in .env" >&2; exit 1
fi

# Chat → commonstack
export OPENAI_API_KEY="$COMMONSTACK_API_KEY"
export OPENAI_BASE_URL="https://api.commonstack.ai/v1"
unset OPENAI_ORGANIZATION WRITER_API_KEY WRITER_BASE_URL READER_API_KEY READER_BASE_URL

# Judge → OpenRouter (commonstack lacks gpt-4o)
export JUDGE_API_KEY="$OPENROUTER_API_KEY"
export JUDGE_BASE_URL="https://openrouter.ai/api/v1"

# Embed → OpenRouter
export EMBEDDING_API_KEY="$OPENROUTER_API_KEY"
export EMBEDDING_BASE_URL="https://openrouter.ai/api/v1"

export WRITER_REASONING_EFFORT="medium"

BASE="benchmarks/longmemeval"
FINAL_DIR="$BASE/runs/$LABEL"
BATCH_ROOT="$FINAL_DIR/batches"
BATCH_DIRS_FILE="$FINAL_DIR/batch_dirs.txt"
LOG_FILES_FILE="$FINAL_DIR/log_files.txt"
mkdir -p "$FINAL_DIR" "$BATCH_ROOT" logs
: > "$BATCH_DIRS_FILE"
: > "$LOG_FILES_FILE"

echo "iter32 MS run: $LABEL"
echo "  qid file:  $QID_LIST_FILE (133 MS qids)"
echo "  parallel:  $N_PARALLEL"
echo "  writer:    gpt-5.4-mini medium"
echo "  reader:    gpt-5.4-mini default (high)"
echo "  rerank:    gpt-5.4-mini low"
echo "  modules:   M1 top gate + M2 COUNT_CANDIDATES + M3 ARITH_OPERANDS"
echo "  output:    $FINAL_DIR"

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
    OUTDIR="$BATCH_ROOT/b$((i+1))"
    LOG="logs/${LABEL_SAFE}_b$((i+1)).log"
    BATCH_DIRS+=("$OUTDIR")
    echo "  batch $((i+1)): $LIMIT qid → $OUTDIR (log: $LOG)"
    printf '%s\n' "$OUTDIR" >> "$BATCH_DIRS_FILE"
    printf '%s\n' "$LOG" >> "$LOG_FILES_FILE"
    rm -rf "$OUTDIR" && mkdir -p "$OUTDIR"
    rm -f "$LOG"
    nohup .venv/bin/python -u -m benchmarks.longmemeval.run_eval \
        --model openai:openai/gpt-5.4-mini \
        --writer-model openai:openai/gpt-5.4-mini \
        --judge-model openai:openai/gpt-4o \
        --embedding openai:openai/text-embedding-3-small \
        --writer-reasoning-effort medium \
        --symbolic-resolver --symbolic-temporal --symbolic-bypass \
        --tr-topic-timeline \
        --llm-rerank --rerank-model openai:openai/gpt-5.4-mini \
        --rerank-reasoning-effort low --rerank-pool 100 \
        --agg-max-context-chars 15000 \
        --question-ids "$IDS_CSV" \
        --output-dir "$OUTDIR" \
        --batch-mode --llm-eval \
        > "$LOG" 2>&1 &
    PIDS+=($!)
    START=$(( END + 1 ))
done

echo "PIDs: ${PIDS[*]}"
echo "${PIDS[*]}" > "$FINAL_DIR/workers.pids"

# Don't wait — let the HC monitor do that
disown ${PIDS[*]}
echo "Workers detached. HC monitor handles merge + cost check."
