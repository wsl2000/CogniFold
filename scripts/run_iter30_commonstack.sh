#!/usr/bin/env bash
# iter30 launcher — commonstack chat + OpenRouter judge/embed split.
#
# Routing (B+X profile per user decision 2026-06-05):
#   Chat  (writer/reader/rerank) → commonstack openai/gpt-5.4-mini
#   Judge                        → OpenRouter  openai/gpt-4o   (~$0.50 total)
#   Embed                        → OpenRouter  openai/text-embedding-3-small (~$0.30 total)
#
# Why split:
#   - Commonstack has no /embeddings endpoint (404) and no gpt-4o in model list.
#   - The LongMemEval canonical judge is gpt-4o; downgrading to gpt-4o-mini
#     would make verdicts incomparable with iter27 baseline.
#   - Total OpenRouter spend ~$0.80 for the whole N=500 run is acceptable.
#
# Concurrency:
#   Commonstack has a ~50 RPM aggregate cap. Default N_PARALLEL=5 keeps
#   each worker at ~10 RPM. Going higher floods with 429s (Tier 3 history:
#   10-parallel × commonstack = 26K 429 errors in one run).
#
# Usage:
#   bash scripts/run_iter30_commonstack.sh <QID_LIST_FILE> <LABEL> [N_PARALLEL]

set -uo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a

QID_LIST_FILE="${1:?need QID_LIST_FILE path}"
LABEL="${2:?need LABEL}"
N_PARALLEL="${3:-5}"

if [ -z "${COMMONSTACK_API_KEY:-}" ]; then
    echo "ERROR: COMMONSTACK_API_KEY missing in .env" >&2; exit 1
fi
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
    echo "ERROR: OPENROUTER_API_KEY missing in .env" >&2; exit 1
fi

# Chat path (writer / reader / rerank) → commonstack
export OPENAI_API_KEY="$COMMONSTACK_API_KEY"
export OPENAI_BASE_URL="https://api.commonstack.ai/v1"
unset OPENAI_ORGANIZATION

# Don't accidentally inherit iter29c WRITER/READER overrides
unset WRITER_API_KEY WRITER_BASE_URL
unset READER_API_KEY READER_BASE_URL

# Judge → OpenRouter (gpt-4o canonical)
export JUDGE_API_KEY="$OPENROUTER_API_KEY"
export JUDGE_BASE_URL="https://openrouter.ai/api/v1"

# Embed → OpenRouter (commonstack has no /embeddings)
export EMBEDDING_API_KEY="$OPENROUTER_API_KEY"
export EMBEDDING_BASE_URL="https://openrouter.ai/api/v1"

export WRITER_REASONING_EFFORT="low"
export REFLECTOR_REASONING_EFFORT="low"

BASE="benchmarks/longmemeval"
FINAL_DIR="$BASE/runs/$LABEL"
mkdir -p "$FINAL_DIR" logs

echo "iter30 (B+X) run: $LABEL"
echo "  qid file:  $QID_LIST_FILE"
echo "  parallel:  $N_PARALLEL  (commonstack 50 RPM cap)"
echo "  chat:      commonstack  → openai/gpt-5.4-mini"
echo "  judge:     openrouter   → openai/gpt-4o"
echo "  embed:     openrouter   → openai/text-embedding-3-small"
echo "  reflector: ON"
echo "  W3 START:  ON  (--extract-start-events)"
echo "  TR-α:      ON  (--tr-topic-timeline)"
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
    OUTDIR="$BASE/output_i30cs_b$((i+1))"
    LOG="logs/iter30cs_b$((i+1)).log"
    BATCH_DIRS+=("$OUTDIR")
    echo "  batch $((i+1)): $LIMIT qid → $OUTDIR (log: $LOG)"
    rm -rf "$OUTDIR" && mkdir -p "$OUTDIR"
    nohup .venv/bin/python -u -m benchmarks.longmemeval.run_eval \
        --model openai:openai/gpt-5.4-mini \
        --writer-model openai:openai/gpt-5.4-mini \
        --judge-model openai:openai/gpt-4o \
        --embedding openai:openai/text-embedding-3-small \
        --writer-reasoning-effort low \
        --extract-typed-attributes \
        --resolve-event-dates \
        --extract-start-events \
        --reflector \
        --tr-topic-timeline \
        --symbolic-resolver --symbolic-temporal --symbolic-bypass \
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
echo "Waiting..."
FAIL=0
for pid in "${PIDS[@]}"; do
    if ! wait "$pid"; then
        echo "  batch pid=$pid failed (see logs/iter30cs_b*.log)"
        FAIL=$((FAIL+1))
    fi
done

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
for batch in sorted(Path("$BASE").glob("output_i30cs_b*")):
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
        "correct": c["CORRECT"], "partial": c["PARTIAL"],
        "incorrect": c["INCORRECT"], "error": c.get("ERROR", 0),
        "total": total,
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
