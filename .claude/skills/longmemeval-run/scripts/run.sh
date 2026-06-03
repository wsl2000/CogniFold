#!/usr/bin/env bash
# LongMemEval one-shot run — verify env, then run the full N=500
# benchmark. Single command, no parameters to think about.
#
# Usage:
#     bash .claude/skills/longmemeval-run/scripts/run.sh [LABEL] [--check-only]
#
# LABEL: optional run name (defaults to run_YYYYMMDD_HHMM). Results land
#        at benchmarks/longmemeval/runs/<LABEL>/.
# --check-only: stop after env+API checks; do not launch the full run.
#
# Flow:
#     1. Eight env + API checks (~30 s, ~$0.01) — halts on any failure.
#     2. Full N=500 run on the verified provider — ~2-4 h wall-clock,
#        ~$80-150 on the recommended gpt-5 stack.
#
# Concurrency is auto-tuned to the chat provider: 100 on OpenRouter or
# OpenAI direct, 10 on commonstack (ak- keys typically cap at 50 RPM).
#
# See .claude/skills/longmemeval-run/SKILL.md for the contract.

set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# --- args -------------------------------------------------------------
LABEL=""
CHECK_ONLY=0
for a in "$@"; do
    case "$a" in
        --check-only) CHECK_ONLY=1 ;;
        -h|--help)
            sed -n '2,18p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            if [ -z "$LABEL" ]; then LABEL="$a"; else
                echo "unexpected arg: $a (use --help)" >&2; exit 2
            fi
            ;;
    esac
done
[ -n "$LABEL" ] || LABEL="run_$(date +%Y%m%d_%H%M)"

# --- output helpers ---------------------------------------------------
PASS_PREFIX="✓"
FAIL_PREFIX="✗"
INFO_PREFIX="•"
ok()   { printf "  %s %s\n" "$PASS_PREFIX" "$*"; }
fail() { printf "  %s %s\n" "$FAIL_PREFIX" "$*" >&2; exit 1; }
info() { printf "  %s %s\n" "$INFO_PREFIX" "$*"; }
step() { printf "\n[%d/8] %s\n" "$1" "$2"; }

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

# Model defaults — MUST match scripts/parallel_longmemeval.sh
# (source of truth). Mirrored here only so the ping checks at steps
# 6-8 know what to test. If you change defaults in one place, change
# them in the other or the user will see one stack at the ping step
# and a different stack in the full run.
READER_MODEL_RAW="${READER_MODEL:-openai:openai/gpt-5}"
WRITER_MODEL_RAW="${WRITER_MODEL:-openai:openai/gpt-5}"
JUDGE_MODEL_RAW="${JUDGE_MODEL:-openai:openai/gpt-4o}"
EMBED_MODEL_RAW="${EMBED_MODEL:-openai:openai/text-embedding-3-large}"
RERANK_MODEL_RAW="${RERANK_MODEL:-openai:openai/gpt-5}"

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

# --- 6: chat ping -----------------------------------------------------
step 6 "Chat ping (writer model: $WRITER_MODEL)"
# Detect reasoning models (gpt-5/o1/o3) — they reject `max_tokens`/
# `temperature` and require `max_completion_tokens` + `reasoning_effort`.
case "$WRITER_MODEL" in
    *gpt-5*|*/o1*|*/o3*)
        body=$(jq -n --arg m "$WRITER_MODEL" \
            '{model:$m, messages:[{role:"user", content:"Reply with the single token: OK"}], max_completion_tokens:100, reasoning_effort:"low"}')
        ;;
    *)
        body=$(jq -n --arg m "$WRITER_MODEL" \
            '{model:$m, messages:[{role:"user", content:"Reply with the single token: OK"}], max_tokens:5, temperature:0}')
        ;;
esac
resp=$(curl -sS -m 90 -X POST "$CHAT_BASE_URL/chat/completions" \
    -H "Authorization: Bearer $CHAT_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$body" 2>&1)
echo "$resp" | jq -e '.choices[0].message.content' >/dev/null 2>&1 || \
    fail "writer chat call failed: $(echo "$resp" | head -c 220)"
ok "chat OK"

# --- 7: embed ping ----------------------------------------------------
step 7 "Embed ping"
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
    -d "$(jq -n --arg m "$EMBED_MODEL_TO_TEST" '{model:$m, input:"hello", dimensions:1536}')" \
    2>&1)
dim=$(echo "$resp" | jq -r '.data[0].embedding | length' 2>/dev/null || echo "")
if [ -z "$dim" ] || [ "$dim" = "null" ]; then
    fail "embed call failed: $(echo "$resp" | head -c 220) — set EMBEDDING_API_KEY+EMBEDDING_BASE_URL to a /embeddings-capable provider (OpenAI direct works)"
fi
if [ "$dim" != "1536" ]; then
    fail "embed model returned dim=$dim (expected 1536 to match cognifold/embeddings/config.py). Check that the provider honors the API \`dimensions\` parameter."
fi
ok "embed OK (1536 dim)"

# --- 8: judge ping ----------------------------------------------------
step 8 "Judge ping (model: $JUDGE_MODEL)"
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

# --- summary ----------------------------------------------------------
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

# --- launch full N=500 ------------------------------------------------
# Auto-tune parallelism by provider.
case "$CHAT_PROVIDER" in
    commonstack)  N_PARALLEL=10  ;;  # ak- keys cap at ~50 RPM
    *)            N_PARALLEL=100 ;;
esac

if [ "$CHECK_ONLY" = "1" ]; then
    echo "--check-only set; not launching the full run."
    echo "When ready:"
    echo "    bash $0 $LABEL"
    exit 0
fi

echo "Launching full N=500 (label: $LABEL, parallel=$N_PARALLEL)"
echo "Expected ~2-4 h wall-clock, ~\$80-150 cost (gpt-5 recommended stack)."
echo "Result will land at benchmarks/longmemeval/runs/$LABEL/"
printf "\n"

EXTRACT_TYPED_ATTRIBUTES="${EXTRACT_TYPED_ATTRIBUTES:-1}" \
exec bash scripts/parallel_longmemeval.sh "$N_PARALLEL" 133 500 "$LABEL"
