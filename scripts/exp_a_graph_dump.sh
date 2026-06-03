#!/usr/bin/env bash
# Exp A: graph-dump diagnostic. For each qid, ingest sessions, dump full
# graph, SKIP the QA step. Used to classify "I don't have memory of X"
# failures as writer-extraction misses vs retrieval rank-out.
#
# Usage: bash scripts/exp_a_graph_dump.sh <LABEL> "qid1,qid2,..."
# Output: runs/<LABEL>/graph_<qid>.json + hypothesis.jsonl (one record per qid)

set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a
if [ -n "${OPENROUTER_API_KEY:-}" ]; then
    export OPENAI_API_KEY="$OPENROUTER_API_KEY"
    export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
    unset OPENAI_ORGANIZATION
fi

LABEL="${1:?LABEL required}"
QIDS_CSV="${2:?CSV of question ids required}"

BASE="benchmarks/longmemeval"
FINAL_DIR="$BASE/runs/$LABEL"
mkdir -p "$FINAL_DIR" logs
rm -f "$FINAL_DIR/hypothesis.jsonl"

IFS=',' read -ra QIDS <<< "$QIDS_CSV"
echo "Exp A graph dump: $LABEL  #qids=${#QIDS[@]}"

PIDS=()
BATCH_DIRS=()
for i in "${!QIDS[@]}"; do
    QID="${QIDS[$i]}"
    OUTDIR="$BASE/output_expa_b$((i+1))"
    LOG="logs/expa_${LABEL}_b$((i+1))_${QID}.log"
    BATCH_DIRS+=("$OUTDIR")
    rm -rf "$OUTDIR" && mkdir -p "$OUTDIR"
    echo "  [$((i+1))] $QID → $OUTDIR (log: $LOG)"
    nohup .venv/bin/python -u -m benchmarks.longmemeval.run_eval \
        --writer-model openai:openai/gpt-5 \
        --writer-reasoning-effort low \
        --embedding openai:openai/text-embedding-3-large \
        --dump-graph-only \
        --no-llm-eval \
        --question-ids "$QID" \
        --output-dir "$OUTDIR" \
        --batch-mode \
        > "$LOG" 2>&1 &
    PIDS+=($!)
done

echo "PIDs: ${PIDS[*]}"
FAIL=0
for pid in "${PIDS[@]}"; do
    wait "$pid" || FAIL=$((FAIL+1))
done

# Merge: copy each batch's hypothesis.jsonl + graph_*.json into FINAL_DIR
.venv/bin/python <<PY
import json, shutil
from pathlib import Path
final_dir = Path("$FINAL_DIR")
records = []
for batch in sorted(Path("$BASE").glob("output_expa_b*")):
    hp = batch / "hypothesis.jsonl"
    if hp.exists():
        for line in open(hp):
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    # Move graph_*.json files
    for gj in batch.glob("graph_*.json"):
        shutil.copy(gj, final_dir / gj.name)
with open(final_dir / "hypothesis.jsonl", "w") as f:
    for r in records:
        f.write(json.dumps(r) + "\n")
print(f"Exp A merged: {len(records)} qids dumped to {final_dir}")
PY

if [ "$FAIL" -eq 0 ]; then
    for d in "${BATCH_DIRS[@]}"; do rm -rf "$d"; done
fi
echo "Done. Output: $FINAL_DIR"
