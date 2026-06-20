#!/usr/bin/env bash
# Run LongMemEval as N parallel batches with resume + merged single-dir output.
#
# Usage:
#   bash scripts/parallel_longmemeval.sh [N_PARALLEL] [STRATIFIED] [TOTAL_LIMIT] [ITER_LABEL]
#
# Examples:
#   bash scripts/parallel_longmemeval.sh 10                              # legacy: output/ dir
#   bash scripts/parallel_longmemeval.sh 100 84 500                      # legacy: output/ dir, full 500
#   bash scripts/parallel_longmemeval.sh 100 84 500 iter05_order_among   # writes to runs/iter05_order_among/
#
# Behavior:
#   - If ITER_LABEL is given, output lands at benchmarks/longmemeval/runs/<ITER_LABEL>/.
#     A CHANGES.md stub is auto-created if missing, listing the stack + score for later edit.
#   - If ITER_LABEL is omitted, falls back to benchmarks/longmemeval/output/ (legacy).
#   - If <FINAL_DIR>/hypothesis.jsonl already exists, only the missing qids get
#     processed (incremental resume).
#   - Per-batch scratch dirs (benchmarks/longmemeval/output_b*/) are deleted
#     after the merge succeeds.

set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && set -a && source .env && set +a
# Route OpenAI SDK. Priority: COMMONSTACK > OPENROUTER.
# When using commonstack (no /embeddings endpoint), also route embedding
# through OpenRouter via EMBEDDING_API_KEY / EMBEDDING_BASE_URL.
if [ -n "${COMMONSTACK_API_KEY:-}" ]; then
    export OPENAI_API_KEY="$COMMONSTACK_API_KEY"
    export OPENAI_BASE_URL="https://api.commonstack.ai/v1"
    unset OPENAI_ORGANIZATION
    echo "  routing chat → commonstack.ai"
    if [ -n "${EMBEDDING_API_KEY:-}" ]; then
        echo "  routing embedding → caller-supplied EMBEDDING_API_KEY (likely OpenAI direct)"
    elif [ -n "${OPENROUTER_API_KEY:-}" ]; then
        export EMBEDDING_API_KEY="$OPENROUTER_API_KEY"
        export EMBEDDING_BASE_URL="https://openrouter.ai/api/v1"
        echo "  routing embedding → openrouter (commonstack has no /embeddings)"
    fi
elif [ -n "${OPENROUTER_API_KEY:-}" ]; then
    export OPENAI_API_KEY="$OPENROUTER_API_KEY"
    export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
    unset OPENAI_ORGANIZATION
fi
if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "ERROR: no API key set (need COMMONSTACK_API_KEY, OPENROUTER_API_KEY, or OPENAI_API_KEY)" >&2
    exit 1
fi

# iter28b: judge can route to a SEPARATE provider via JUDGE_API_KEY /
# JUDGE_BASE_URL. Useful when chat is via commonstack (which lacks gpt-4o)
# but the user wants the canonical LongMemEval gpt-4o judge from OpenAI
# direct. If JUDGE_API_KEY is unset but the caller is on commonstack and
# we have an EMBEDDING_API_KEY (OpenAI direct), reuse it as the judge key
# so the canonical gpt-4o judge "just works" without extra env vars.
if [ -z "${JUDGE_API_KEY:-}" ] && [ -n "${COMMONSTACK_API_KEY:-}" ] && \
   [ -n "${EMBEDDING_API_KEY:-}" ] && \
   [[ "${EMBEDDING_API_KEY:-}" != "$COMMONSTACK_API_KEY" ]]; then
    export JUDGE_API_KEY="$EMBEDDING_API_KEY"
    export JUDGE_BASE_URL="${EMBEDDING_BASE_URL:-https://api.openai.com/v1}"
    echo "  routing judge → reusing EMBEDDING_API_KEY (likely OpenAI direct)"
elif [ -n "${JUDGE_API_KEY:-}" ]; then
    echo "  routing judge → caller-supplied JUDGE_API_KEY"
fi

N_PARALLEL="${1:-10}"
STRATIFIED="${2:-14}"
TOTAL_LIMIT="${3:-80}"
ITER_LABEL="${4:-}"

BASE="benchmarks/longmemeval"
if [ -n "$ITER_LABEL" ]; then
    FINAL_DIR="$BASE/runs/$ITER_LABEL"
    echo "ITER_LABEL='$ITER_LABEL' → results will land at $FINAL_DIR/"
else
    FINAL_DIR="$BASE/output"
    echo "(no ITER_LABEL given — using legacy $FINAL_DIR/)"
fi
mkdir -p "$FINAL_DIR" logs

# Step 1: determine TODO qids = target subset minus already-done.
# If QID_LIST_FILE env var is set, use its contents as the target qid list
# (overrides the stratified selection); otherwise compute from STRATIFIED.
TODO_FILE=$(mktemp)
trap "rm -f $TODO_FILE" EXIT
.venv/bin/python <<PY > "$TODO_FILE"
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

qid_list_file = os.environ.get("QID_LIST_FILE", "")
if qid_list_file and Path(qid_list_file).exists():
    text = Path(qid_list_file).read_text().strip()
    # Accept CSV or newline-delimited.
    raw = [t.strip() for chunk in text.split("\n") for t in chunk.split(",")]
    target_qids = [q for q in raw if q]
    sys.stderr.write(
        f"Using QID_LIST_FILE={qid_list_file} with {len(target_qids)} qids "
        f"(stratified/limit args ignored)\n"
    )
else:
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

# Optional env-var driven extra flags (so iter-specific configurations don't
# require editing this script).
EXTRA_FLAGS=()
# Aggregation context bump: "how many X" / "how much" type questions need
# ~3x the default 6000-char retrieval context to fit a 50-node candidate
# set without assembly truncation. iter05+ validated 15000 as the sweet
# spot — without it the aggregation cluster regresses by ~1-2 pp overall.
AGG_MAX_CONTEXT_CHARS="${AGG_MAX_CONTEXT_CHARS:-15000}"
EXTRA_FLAGS+=(--agg-max-context-chars "$AGG_MAX_CONTEXT_CHARS")
echo "  + --agg-max-context-chars $AGG_MAX_CONTEXT_CHARS"
if [ -n "${MAX_CONTEXT_CHARS:-}" ]; then
    EXTRA_FLAGS+=(--max-context-chars "$MAX_CONTEXT_CHARS")
    echo "  + --max-context-chars $MAX_CONTEXT_CHARS"
fi
if [ "${EXTRACT_TYPED_ATTRIBUTES:-0}" = "1" ]; then
    EXTRA_FLAGS+=(--extract-typed-attributes)
    echo "  + --extract-typed-attributes"
fi
if [ "${RESOLVE_EVENT_DATES:-0}" = "1" ]; then
    EXTRA_FLAGS+=(--resolve-event-dates)
    echo "  + --resolve-event-dates"
fi
# Writer reasoning_effort: writer extraction is mechanical JSON; high
# effort on a gpt-5-class model would make full N=500 take many hours
# without measurable quality gain. Default to low; allow env override.
WRITER_REASONING_EFFORT="${WRITER_REASONING_EFFORT:-low}"
EXTRA_FLAGS+=(--writer-reasoning-effort "$WRITER_REASONING_EFFORT")
echo "  + --writer-reasoning-effort $WRITER_REASONING_EFFORT"

# Allow model overrides via env. Defaults = recommended stack.
WRITER_MODEL="${WRITER_MODEL:-openai:gpt-5}"
READER_MODEL="${READER_MODEL:-openai:gpt-5}"
JUDGE_MODEL="${JUDGE_MODEL:-openai:gpt-4o}"
RERANK_MODEL="${RERANK_MODEL:-openai:gpt-5}"
EMBED_MODEL="${EMBED_MODEL:-openai:text-embedding-3-large}"
echo "  reader: $READER_MODEL"
echo "  writer: $WRITER_MODEL"
echo "  judge: $JUDGE_MODEL"
echo "  rerank: $RERANK_MODEL"
echo "  embed: $EMBED_MODEL"

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
        --model "$READER_MODEL" \
        --writer-model "$WRITER_MODEL" \
        --judge-model "$JUDGE_MODEL" \
        --embedding "$EMBED_MODEL" \
        --symbolic-resolver --symbolic-temporal --symbolic-bypass \
        --llm-rerank --rerank-model "$RERANK_MODEL" \
        --rerank-reasoning-effort low --rerank-pool 100 \
        "${EXTRA_FLAGS[@]}" \
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

# Merge per-batch call_stats.json → FINAL_DIR/call_stats.json. Cost is
# summed from the provider-reported `cost_usd` field per record (OpenRouter
# populates `usage.cost`; OpenAI direct does not, so cost_usd stays 0 in
# direct mode — token totals are still recorded).
merged_stats: dict = {"chat": {}, "embed": {}}
for batch in sorted(Path("$BASE").glob("output_b*")):
    cp = batch / "call_stats.json"
    if not cp.exists():
        continue
    try:
        bs = json.loads(cp.read_text())
    except Exception:
        continue
    for section in ("chat", "embed"):
        defaults = (
            {"calls": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "cost_usd": 0.0}
            if section == "chat"
            else {"calls": 0, "input_tokens": 0, "cost_usd": 0.0}
        )
        for model, bucket in (bs.get(section) or {}).items():
            mb = merged_stats[section].setdefault(model, dict(defaults))
            for k, v in bucket.items():
                if k == "cost_usd":
                    mb[k] = float(mb.get(k, 0.0)) + float(v or 0.0)
                else:
                    mb[k] = int(mb.get(k, 0)) + int(v or 0)

agg = {"chat_calls": 0, "chat_input_tokens": 0, "chat_output_tokens": 0, "chat_reasoning_tokens": 0,
       "embed_calls": 0, "embed_input_tokens": 0, "cost_usd": 0.0}
for model, b in merged_stats["chat"].items():
    agg["chat_calls"] += b.get("calls", 0)
    agg["chat_input_tokens"] += b.get("input_tokens", 0)
    agg["chat_output_tokens"] += b.get("output_tokens", 0)
    agg["chat_reasoning_tokens"] += b.get("reasoning_tokens", 0)
    agg["cost_usd"] += float(b.get("cost_usd", 0.0))
for model, b in merged_stats["embed"].items():
    agg["embed_calls"] += b.get("calls", 0)
    agg["embed_input_tokens"] += b.get("input_tokens", 0)
    agg["cost_usd"] += float(b.get("cost_usd", 0.0))
agg["cost_usd"] = round(agg["cost_usd"], 4)
merged_stats["aggregate"] = agg

with open("$FINAL_DIR/call_stats.json", "w") as f:
    json.dump(merged_stats, f, indent=2)
cost_note = "provider-reported" if agg["cost_usd"] > 0 else "(provider did not report cost — only tokens recorded)"
print(f"call stats: {agg['chat_calls']} chat + {agg['embed_calls']} embed calls; "
      f"in={agg['chat_input_tokens']+agg['embed_input_tokens']:,} out={agg['chat_output_tokens']:,} "
      f"reasoning={agg['chat_reasoning_tokens']:,} tokens; \${agg['cost_usd']:.4f} {cost_note}")

# Auto-stub CHANGES.md if this is an iter folder and the doc doesn't exist yet.
final_dir = Path("$FINAL_DIR")
iter_label = "$ITER_LABEL"
changes = final_dir / "CHANGES.md"
if iter_label and not changes.exists():
    import datetime
    by_type = Counter()
    for r in records.values():
        if r.get("verdict") != "CORRECT":
            by_type[qt.get(r["question_id"], "?")] += 1
    stub = f"""# {iter_label}

> Stub generated automatically. **Fill in the WHAT/WHY before this run can be evaluated.**

## Score
- **strict: {strict:.2f}%** ({c['CORRECT']}/{total})
- partial: {partial:.2f}%
- run date: {datetime.date.today()}

## What changed vs prior iter
- (TODO: list code/profile/resolver diffs)

## Why (target failure cluster)
- (TODO: which of the hardcore-49 modes was this aimed at?)

## NET vs iter02 (bar = 83.2%)
- delta correct: {c['CORRECT'] - 416:+d}
- delta strict pts: {strict - 83.2:+.2f}

## Wrong-case breakdown by type
""" + "\n".join(f"- {t}: {n}" for t, n in sorted(by_type.items())) + """

## Decision
- (TODO: KEEP / REVERT / NEEDS-CONFIRMATION-RUN)
- (Reader stochasticity ≈ ±35 cases — deltas < 7 are noise.)

## Commit
- (TODO: hash if pushed, or "local only — not pushed")
"""
    changes.write_text(stub)
    print(f"wrote stub: {changes}")
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
