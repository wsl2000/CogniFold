#!/usr/bin/env bash
# LongMemEval smoketest — verify a fresh clone is ready for the full
# N=500 benchmark before the user spends ~60 min and ~$25 on a run.
#
# Nine ordered checks. Any failure halts with an actionable message.
# See .claude/skills/longmemeval-smoketest/SKILL.md for the contract.

set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# --- output helpers ---------------------------------------------------
PASS_PREFIX="✓"
FAIL_PREFIX="✗"
INFO_PREFIX="•"
ok()   { printf "  %s %s\n" "$PASS_PREFIX" "$*"; }
fail() { printf "  %s %s\n" "$FAIL_PREFIX" "$*" >&2; exit 1; }
info() { printf "  %s %s\n" "$INFO_PREFIX" "$*"; }
step() { printf "\n[%d/9] %s\n" "$1" "$2"; }

# --- 1: at repo root --------------------------------------------------
step 1 "Repo root + branch"
[ -d .git ] || fail "not in a git repo root — cd to the CogniFold checkout first"
[ -d benchmarks/longmemeval ] || fail "this isn't the CogniFold repo (no benchmarks/longmemeval/)"
ok "at CogniFold repo root"
branch=$(git branch --show-current 2>/dev/null || echo "")
info "branch = ${branch:-<detached>}"

# --- 2: Python + venv -------------------------------------------------
step 2 "Python 3.11+ and .venv"
if [ ! -x .venv/bin/python ]; then
    fail ".venv/bin/python missing — run: python3 -m venv .venv && .venv/bin/pip install -e \".[dev]\""
fi
PY=.venv/bin/python
PY_VER=$("$PY" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
case "$PY_VER" in
    3.11|3.12|3.13|3.14|3.15) ok "Python $PY_VER in .venv" ;;
    *) fail "Python $PY_VER too old — need 3.11+. Rebuild .venv with python3.11+." ;;
esac

# --- 3: imports -------------------------------------------------------
step 3 "Imports"
"$PY" -c "
import importlib, sys
mods = [
    'cognifold',
    'cognifold.graph',
    'cognifold.query.assembly',
    'cognifold.embeddings.providers',
    'benchmarks.longmemeval.run_eval',
    'benchmarks.longmemeval.symbolic_resolver',
]
fail = []
for m in mods:
    try:
        importlib.import_module(m)
    except Exception as e:
        fail.append((m, type(e).__name__, str(e)[:120]))
if fail:
    for m, t, msg in fail:
        print(f'  IMPORT FAILED  {m}: {t}: {msg}')
    sys.exit(1)
" || fail "Python imports failed — run: .venv/bin/pip install -e \".[dev]\""
ok "all required modules import"

# --- 4: dataset -------------------------------------------------------
step 4 "Dataset"
DS=benchmarks/longmemeval/data/longmemeval_s_cleaned.json
[ -f "$DS" ] || fail "dataset missing: $DS — pull data files (LFS or manual)."
N_QID=$("$PY" -c "import json; print(len(json.load(open('$DS'))))")
[ "$N_QID" = "500" ] || fail "dataset has $N_QID qids (expected 500) — corrupted file"
ok "dataset present (N=500)"

# --- 5: .env / chat key -----------------------------------------------
step 5 ".env + chat key"
if [ -f .env ]; then
    # shellcheck disable=SC1091
    set -a; source .env; set +a
fi
if [ -n "${OPENROUTER_API_KEY:-}" ]; then
    CHAT_PROVIDER="openrouter"
    CHAT_BASE_URL="https://openrouter.ai/api/v1"
    CHAT_API_KEY="$OPENROUTER_API_KEY"
    info "chat → OpenRouter"
elif [ -n "${COMMONSTACK_API_KEY:-}" ]; then
    CHAT_PROVIDER="commonstack"
    CHAT_BASE_URL="https://api.commonstack.ai/v1"
    CHAT_API_KEY="$COMMONSTACK_API_KEY"
    info "chat → commonstack.ai (warning: ak- keys typically cap at 50 RPM)"
elif [ -n "${OPENAI_API_KEY:-}" ]; then
    CHAT_PROVIDER="openai-direct"
    CHAT_BASE_URL="https://api.openai.com/v1"
    CHAT_API_KEY="$OPENAI_API_KEY"
    info "chat → OpenAI direct"
else
    fail "no chat key in .env — set OPENROUTER_API_KEY (recommended) or COMMONSTACK_API_KEY or OPENAI_API_KEY"
fi
ok "chat key found ($CHAT_PROVIDER)"

# Model defaults — match scripts/parallel_longmemeval.sh
READER_MODEL_RAW="${READER_MODEL:-openai:openai/gpt-5-mini}"
WRITER_MODEL_RAW="${WRITER_MODEL:-openai:openai/gpt-4o-mini}"
JUDGE_MODEL_RAW="${JUDGE_MODEL:-openai:openai/gpt-4o}"
EMBED_MODEL_RAW="${EMBED_MODEL:-openai:openai/text-embedding-3-small}"
RERANK_MODEL_RAW="${RERANK_MODEL:-openai:openai/gpt-5-mini}"

# Normalize for direct provider (strip "openai:" wrapper).
strip_wrap() { echo "$1" | sed 's/^openai://; s/^gemini://'; }
READER_MODEL=$(strip_wrap "$READER_MODEL_RAW")
WRITER_MODEL=$(strip_wrap "$WRITER_MODEL_RAW")
JUDGE_MODEL=$(strip_wrap  "$JUDGE_MODEL_RAW")
EMBED_MODEL=$(strip_wrap  "$EMBED_MODEL_RAW")

# On OpenAI direct the model name has no `openai/` namespace prefix.
if [ "$CHAT_PROVIDER" = "openai-direct" ]; then
    READER_MODEL=$(echo "$READER_MODEL" | sed 's|^openai/||')
    WRITER_MODEL=$(echo "$WRITER_MODEL" | sed 's|^openai/||')
    JUDGE_MODEL=$(echo "$JUDGE_MODEL"   | sed 's|^openai/||')
    EMBED_MODEL=$(echo "$EMBED_MODEL"   | sed 's|^openai/||')
fi
info "reader=$READER_MODEL  writer=$WRITER_MODEL  judge=$JUDGE_MODEL  embed=$EMBED_MODEL"

# --- 6: chat smoke ----------------------------------------------------
step 6 "Chat smoke (writer model: $WRITER_MODEL)"
# Writer is non-reasoning, accepts max_tokens.
resp=$(curl -sS -m 30 -X POST "$CHAT_BASE_URL/chat/completions" \
    -H "Authorization: Bearer $CHAT_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg m "$WRITER_MODEL" \
        '{model:$m, messages:[{role:"user", content:"Reply with the single token: OK"}], max_tokens:5, temperature:0}')" \
    2>&1)
echo "$resp" | jq -e '.choices[0].message.content' >/dev/null 2>&1 || \
    fail "writer chat call failed: $(echo "$resp" | head -c 220)"
ok "chat OK"

# --- 7: embed smoke ---------------------------------------------------
step 7 "Embed smoke"
# Cognifold uses dim=1536 hard-coded for OpenAI embeddings (config.py).
# Force OpenAI direct for embed if explicitly set; otherwise use chat provider.
EMBED_API_KEY="${EMBEDDING_API_KEY:-$CHAT_API_KEY}"
EMBED_BASE_URL="${EMBEDDING_BASE_URL:-$CHAT_BASE_URL}"
# Strip namespace for OpenAI direct base.
EMBED_MODEL_TO_TEST="$EMBED_MODEL"
case "$EMBED_BASE_URL" in
    *api.openai.com*) EMBED_MODEL_TO_TEST=$(echo "$EMBED_MODEL_TO_TEST" | sed 's|^openai/||') ;;
esac
resp=$(curl -sS -m 30 -X POST "$EMBED_BASE_URL/embeddings" \
    -H "Authorization: Bearer $EMBED_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg m "$EMBED_MODEL_TO_TEST" '{model:$m, input:"hello"}')" \
    2>&1)
dim=$(echo "$resp" | jq -r '.data[0].embedding | length' 2>/dev/null || echo "")
if [ -z "$dim" ] || [ "$dim" = "null" ]; then
    fail "embed call failed: $(echo "$resp" | head -c 220) — set EMBEDDING_API_KEY+EMBEDDING_BASE_URL to a /embeddings-capable provider (OpenAI direct works)"
fi
if [ "$dim" != "1536" ]; then
    fail "embed model returned dim=$dim (expected 1536 — text-embedding-3-small native). cognifold/embeddings/config.py expects 1536; mismatched dim will crash retrieval."
fi
ok "embed OK (1536 dim)"

# --- 8: judge smoke ---------------------------------------------------
step 8 "Judge smoke (model: $JUDGE_MODEL)"
JUDGE_API_KEY_TO_TEST="${JUDGE_API_KEY:-$CHAT_API_KEY}"
JUDGE_BASE_URL_TO_TEST="${JUDGE_BASE_URL:-$CHAT_BASE_URL}"
JUDGE_MODEL_TO_TEST="$JUDGE_MODEL"
case "$JUDGE_BASE_URL_TO_TEST" in
    *api.openai.com*) JUDGE_MODEL_TO_TEST=$(echo "$JUDGE_MODEL_TO_TEST" | sed 's|^openai/||') ;;
esac
resp=$(curl -sS -m 30 -X POST "$JUDGE_BASE_URL_TO_TEST/chat/completions" \
    -H "Authorization: Bearer $JUDGE_API_KEY_TO_TEST" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg m "$JUDGE_MODEL_TO_TEST" \
        '{model:$m, messages:[{role:"user", content:"Reply with the word: CORRECT"}], max_tokens:5, temperature:0}')" \
    2>&1)
echo "$resp" | jq -e '.choices[0].message.content' >/dev/null 2>&1 || \
    fail "judge call failed: $(echo "$resp" | head -c 220) — set JUDGE_API_KEY+JUDGE_BASE_URL to a provider that hosts $JUDGE_MODEL"
ok "judge OK"

# --- 9: tiny benchmark ------------------------------------------------
if [ "${SMOKETEST_SKIP_TINY:-}" = "1" ]; then
    step 9 "Tiny N=6 benchmark (skipped: SMOKETEST_SKIP_TINY=1)"
    info "set SMOKETEST_SKIP_TINY= (empty) to run end-to-end"
else
    step 9 "Tiny N=6 benchmark (1 qid per type, ~3-5 min, ~\$0.20)"
    # Generate 6 stratified qids — first 1 per type.
    "$PY" - <<PY
import json
from collections import defaultdict
from pathlib import Path
data = json.load(open("$DS"))
by_type = defaultdict(list)
for q in data:
    by_type[q["question_type"]].append(q["question_id"])
qids = [by_type[t][0] for t in sorted(by_type)]
Path("/tmp/smoketest_qids.txt").write_text("\n".join(qids) + "\n")
print(f"  selected {len(qids)} qids: {', '.join(q[:12] for q in qids)}")
PY
    # Clean any previous output_b* / tiny run dir
    rm -rf benchmarks/longmemeval/output_b* benchmarks/longmemeval/runs/smoketest
    info "launching... (logs in /tmp/smoketest_run.log)"

    QID_LIST_FILE=/tmp/smoketest_qids.txt \
    EXTRACT_TYPED_ATTRIBUTES="${EXTRACT_TYPED_ATTRIBUTES:-1}" \
    bash scripts/parallel_longmemeval.sh 6 200 500 smoketest \
        > /tmp/smoketest_run.log 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo
        tail -25 /tmp/smoketest_run.log >&2
        fail "tiny run exited with code $rc — see /tmp/smoketest_run.log"
    fi
    # Sanity: metrics file present + strict ≥ 50%
    METRICS=benchmarks/longmemeval/runs/smoketest/metrics.json
    [ -f "$METRICS" ] || fail "tiny run produced no metrics.json"
    STRICT=$("$PY" -c "import json; m=json.load(open('$METRICS')); print(f\"{m['score_strict']:.1f}\")")
    N_RES=$("$PY" -c "import json; m=json.load(open('$METRICS')); print(m['total'])")
    if [ "$N_RES" -lt 6 ]; then
        fail "tiny run produced $N_RES results (expected 6) — some batches failed silently. Inspect /tmp/smoketest_run.log"
    fi
    # Strict floor — 50% on 6 stratified is very forgiving; if it's lower
    # then the pipeline is producing junk answers (e.g. empty hypothesis).
    awk -v s="$STRICT" 'BEGIN { if (s < 50.0) exit 1 }' || \
        fail "tiny run strict=$STRICT% < 50% — pipeline producing junk. Inspect benchmarks/longmemeval/runs/smoketest/hypothesis.jsonl"
    ok "tiny run: $N_RES results, strict=$STRICT% (≥ 50% sanity floor)"
fi

# --- summary + next-step ----------------------------------------------
printf "\n"
echo "═════════════════════════════════════════════════════════════════"
echo "✓ ALL CHECKS PASSED"
echo "═════════════════════════════════════════════════════════════════"
printf "\n"
echo "Verified stack:"
echo "  reader  $READER_MODEL_RAW"
echo "  writer  $WRITER_MODEL_RAW"
echo "  judge   $JUDGE_MODEL_RAW"
echo "  embed   $EMBED_MODEL_RAW  (1536 dim)"
echo "  rerank  $RERANK_MODEL_RAW"
echo "  chat    → $CHAT_PROVIDER"
if [ "${EMBEDDING_API_KEY:-}" != "" ] && [ "${EMBEDDING_BASE_URL:-}" != "$CHAT_BASE_URL" ]; then
    echo "  embed   → caller-supplied EMBEDDING_API_KEY ($EMBED_BASE_URL)"
fi
if [ "${JUDGE_API_KEY:-}" != "" ] && [ "${JUDGE_BASE_URL:-}" != "$CHAT_BASE_URL" ]; then
    echo "  judge   → caller-supplied JUDGE_API_KEY ($JUDGE_BASE_URL_TO_TEST)"
fi
printf "\n"
echo "To run the full N=500 benchmark with the verified stack:"
echo
case "$CHAT_PROVIDER" in
    commonstack)
        echo "  # commonstack ak- keys often cap at 50 RPM — use parallelism ≤ 10"
        echo "  bash scripts/parallel_longmemeval.sh 10 200 500 my_first_run"
        ;;
    openrouter|openai-direct)
        echo "  bash scripts/parallel_longmemeval.sh 100 200 500 my_first_run"
        ;;
esac
echo
echo "Expected cost ~\$15-25; wall-clock ~60-90 min."
echo "Results land at benchmarks/longmemeval/runs/my_first_run/"
echo
echo "Read the result with:"
echo "  cat benchmarks/longmemeval/runs/my_first_run/metrics.json"
