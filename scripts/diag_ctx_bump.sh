#!/usr/bin/env bash
# Diagnostic run for a fixed qid list with audit visibility + context-bump flags.
# Usage: bash scripts/diag_ctx_bump.sh <LABEL> <AGG_MAX_CTX> "qid1,qid2,..."
# Spawns one process per qid in parallel; merges into runs/<LABEL>/.

set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a
if [ -n "${OPENROUTER_API_KEY:-}" ]; then
    export OPENAI_API_KEY="$OPENROUTER_API_KEY"
    export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
    unset OPENAI_ORGANIZATION
fi

LABEL="${1:?LABEL required}"
AGG_MAX_CTX="${2:?AGG_MAX_CTX required (e.g. 15000)}"
QIDS_CSV="${3:?CSV of question ids required}"

BASE="benchmarks/longmemeval"
FINAL_DIR="$BASE/runs/$LABEL"
mkdir -p "$FINAL_DIR" logs
rm -f "$FINAL_DIR/hypothesis.jsonl"

EXTRA_FLAGS=()
if [ "${EXTRACT_TYPED_ATTRIBUTES:-0}" = "1" ]; then
    EXTRA_FLAGS+=(--extract-typed-attributes)
fi

IFS=',' read -ra QIDS <<< "$QIDS_CSV"
echo "Diagnostic: $LABEL  agg_ctx=$AGG_MAX_CTX  #qids=${#QIDS[@]}  typed_attrs=${EXTRACT_TYPED_ATTRIBUTES:-0}"

PIDS=()
BATCH_DIRS=()
for i in "${!QIDS[@]}"; do
    QID="${QIDS[$i]}"
    OUTDIR="$BASE/output_diag_b$((i+1))"
    LOG="logs/diag_${LABEL}_b$((i+1))_${QID}.log"
    BATCH_DIRS+=("$OUTDIR")
    rm -rf "$OUTDIR" && mkdir -p "$OUTDIR"
    echo "  [$((i+1))] $QID → $OUTDIR (log: $LOG)"
    nohup .venv/bin/python -u -m benchmarks.longmemeval.run_eval \
        --model openai:openai/gpt-5 \
        --writer-model openai:openai/gpt-5 \
        --writer-reasoning-effort low \
        --judge-model openai:openai/gpt-4o \
        --embedding openai:openai/text-embedding-3-large \
        --symbolic-resolver --symbolic-temporal --symbolic-bypass \
        --llm-rerank --rerank-model openai:openai/gpt-5 \
        --rerank-reasoning-effort low --rerank-pool 100 \
        --agg-max-context-chars "$AGG_MAX_CTX" \
        "${EXTRA_FLAGS[@]}" \
        --question-ids "$QID" \
        --output-dir "$OUTDIR" \
        --batch-mode --llm-eval \
        > "$LOG" 2>&1 &
    PIDS+=($!)
done

echo "PIDs: ${PIDS[*]}"
FAIL=0
for pid in "${PIDS[@]}"; do
    wait "$pid" || FAIL=$((FAIL+1))
done

.venv/bin/python <<PY
import json
from pathlib import Path
from collections import Counter
records = {}
for batch in sorted(Path("$BASE").glob("output_diag_b*")):
    hp = batch / "hypothesis.jsonl"
    if hp.exists():
        for line in open(hp):
            try:
                r = json.loads(line)
                records[r["question_id"]] = r
            except Exception:
                pass
with open("$FINAL_DIR/hypothesis.jsonl", "w") as f:
    for r in records.values():
        f.write(json.dumps(r) + "\n")
c = Counter(r.get("verdict") for r in records.values())
print(f"Diag merged: {len(records)} qids  verdicts={dict(c)}")
PY

if [ "$FAIL" -eq 0 ]; then
    for d in "${BATCH_DIRS[@]}"; do rm -rf "$d"; done
fi
echo "Done. Output: $FINAL_DIR"
