#!/usr/bin/env bash
# Pre-commit doc-guard hook for Claude Code
# Blocks git commit if source files are staged and /doc-guard hasn't been run recently.

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only intercept git commit commands
if [[ ! "$COMMAND" =~ git\ commit ]] && [[ ! "$COMMAND" =~ git\ .*commit ]]; then
  exit 0
fi

# Check if any source files are staged
STAGED_SRC=$(git diff --cached --name-only | grep -E '^src/' || true)
if [ -z "$STAGED_SRC" ]; then
  exit 0  # No source changes staged, allow commit
fi

# Check sentinel file
SENTINEL=".claude/docguard_last_run"
if [ ! -f "$SENTINEL" ]; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Source files are staged but /doc-guard has not been run. Please run /doc-guard to generate documentation updates before committing."}}'
  exit 0
fi

# Check if sentinel is fresh (written after the most recent staged src file edit)
SENTINEL_TS=$(stat -f %m "$SENTINEL" 2>/dev/null || stat -c %Y "$SENTINEL" 2>/dev/null || echo 0)
LATEST_SRC_TS=0
for f in $STAGED_SRC; do
  if [ -f "$f" ]; then
    TS=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null || echo 0)
    if [ "$TS" -gt "$LATEST_SRC_TS" ]; then
      LATEST_SRC_TS=$TS
    fi
  fi
done

if [ "$SENTINEL_TS" -lt "$LATEST_SRC_TS" ]; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Source files were modified after the last /doc-guard run. Please re-run /doc-guard to update documentation before committing."}}'
  exit 0
fi

# Doc-guard was run recently enough, allow
exit 0
