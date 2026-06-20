#!/usr/bin/env bash
# Setup verification — run once on a fresh clone before the loop.
# Halts on any failure so the loop never starts in a broken state.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

fail() { echo "✗ $*" >&2; exit 1; }
ok()   { echo "✓ $*"; }

# 1. Branch
branch=$(git branch --show-current)
[ "$branch" = "longmemeval-iter" ] || fail "Wrong branch: '$branch' (expected longmemeval-iter). git checkout longmemeval-iter"
ok "branch = longmemeval-iter"

# 2. Remote points at OpenNorve/CogniFold
remote_url=$(git remote get-url origin 2>/dev/null || echo "")
echo "$remote_url" | grep -q "OpenNorve/CogniFold" || \
    fail "origin remote is '$remote_url' — expected to contain OpenNorve/CogniFold"
ok "origin → OpenNorve/CogniFold"

# 3. Push credentials (dry-run)
git push origin longmemeval-iter --dry-run 2>&1 | grep -qE "(longmemeval-iter -> longmemeval-iter|Everything up-to-date)" || \
    fail "git push --dry-run failed. SSH key or HTTPS credentials missing."
ok "push credentials OK"

# 4. OPENAI_API_KEY (or OPENROUTER_API_KEY as fallback)
[ -n "${OPENAI_API_KEY:-}" ] || [ -n "${OPENROUTER_API_KEY:-}" ] || [ -f .env ] || \
    fail "Neither OPENAI_API_KEY nor OPENROUTER_API_KEY in env, and no .env file"
ok "API key present"

# 5. Parallel script uses correct models
grep -q 'READER_MODEL=.*openai/gpt-5"\|READER_MODEL=.*openai:gpt-5"'  scripts/parallel_longmemeval.sh || fail "parallel script doesn't use gpt-5 reader"
grep -q 'WRITER_MODEL=.*openai/gpt-5"\|WRITER_MODEL=.*openai:gpt-5"' scripts/parallel_longmemeval.sh || fail "parallel script doesn't use gpt-5 writer"
grep -q 'JUDGE_MODEL=.*openai/gpt-4o"\|JUDGE_MODEL=.*openai:gpt-4o"' scripts/parallel_longmemeval.sh || fail "parallel script doesn't use gpt-4o JUDGE — DANGER"
grep -q 'EMBED_MODEL=.*text-embedding-3-large' scripts/parallel_longmemeval.sh || fail "parallel script doesn't use text-embedding-3-large"
ok "parallel script model stack correct"

# 6. history_max_effort.md exists (bootstrap if not)
if [ ! -f history_max_effort.md ]; then
    echo "# Max-Effort Campaign — gpt-5 writer / gpt-5 reader / gpt-4o judge / text-embedding-3-large" \
        > history_max_effort.md
    git add history_max_effort.md
    git -c user.email="wsuli615@gmail.com" -c user.name="wsl2000" \
        commit -m "Bootstrap max-effort campaign log"
    ok "bootstrapped history_max_effort.md"
else
    ok "history_max_effort.md exists"
fi

# 7. ROUND counter
if [ ! -f .max_effort_round ]; then
    echo "0" > .max_effort_round
    ok "bootstrapped .max_effort_round = 0"
else
    ok ".max_effort_round = $(cat .max_effort_round)"
fi

echo
echo "Setup verified. Safe to enter §8.2 loop."
