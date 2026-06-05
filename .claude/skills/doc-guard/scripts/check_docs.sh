#!/usr/bin/env bash
# Doc-Guard: Git change analysis script for Cognifold
# Analyzes the current branch's changes vs base branch to determine
# which documentation files may need updating.

set -euo pipefail

# Detect base branch
detect_base_branch() {
    local current_branch
    current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

    # Try cognifold-dev first, then main
    if git rev-parse --verify origin/cognifold-dev &>/dev/null; then
        echo "origin/cognifold-dev"
    elif git rev-parse --verify origin/main &>/dev/null; then
        echo "origin/main"
    elif git rev-parse --verify main &>/dev/null; then
        echo "main"
    else
        echo "HEAD~10"  # Fallback: last 10 commits
    fi
}

# Get merge base
get_merge_base() {
    local base="$1"
    git merge-base HEAD "$base" 2>/dev/null || echo "$base"
}

echo "=== Doc-Guard: Branch Analysis ==="
echo ""

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
BASE_BRANCH=$(detect_base_branch)
MERGE_BASE=$(get_merge_base "$BASE_BRANCH")
COMMIT_COUNT=$(git rev-list --count "$MERGE_BASE"..HEAD 2>/dev/null || echo "0")

echo "Current branch: $CURRENT_BRANCH"
echo "Base branch:    $BASE_BRANCH"
echo "Merge base:     ${MERGE_BASE:0:12}"
echo "Commits ahead:  $COMMIT_COUNT"
echo ""

# Get all changed files
CHANGED_FILES=$(git diff --name-only "$MERGE_BASE"..HEAD 2>/dev/null || echo "")

if [ -z "$CHANGED_FILES" ]; then
    echo "No changes detected vs base branch."
    exit 0
fi

# Categorize changed files
echo "=== Changed Files by Category ==="
echo ""

echo "--- Source files (src/) ---"
echo "$CHANGED_FILES" | grep -E '^src/' || echo "(none)"
echo ""

echo "--- Test files (tests/) ---"
echo "$CHANGED_FILES" | grep -E '^tests/' || echo "(none)"
echo ""

echo "--- Config files ---"
echo "$CHANGED_FILES" | grep -E '^(pyproject\.toml|Makefile|\.github/|\.claude/|ruff\.toml|pyrightconfig)' || echo "(none)"
echo ""

echo "--- Documentation files (docs/ + CLAUDE.md) ---"
echo "$CHANGED_FILES" | grep -E '^(docs/|CLAUDE\.md|README\.md)' || echo "(none)"
echo ""

echo "--- Other files ---"
echo "$CHANGED_FILES" | grep -vE '^(src/|tests/|docs/|CLAUDE\.md|README\.md|pyproject\.toml|Makefile|\.github/|\.claude/|ruff\.toml|pyrightconfig)' || echo "(none)"
echo ""

# Check which doc files are modified vs unchanged
echo "=== Documentation File Status ==="
echo ""

DOC_FILES=(
    "docs/RESUME.md"
    "docs/CHANGELOG.md"
    "docs/ARCHITECTURE.md"
    "docs/SERVICE_API.md"
    "docs/PROMPTS.md"
    "docs/PHASES.md"
    "docs/CONTRIBUTING.md"
    "docs/WISHLIST.md"
    "docs/WISHLIST_QUERY_MEMORY.md"
    "docs/BENCHMARK.md"
    "docs/COGNITION_PRINCIPLES.md"
    "CLAUDE.md"
    "README.md"
)

for doc in "${DOC_FILES[@]}"; do
    if echo "$CHANGED_FILES" | grep -qx "$doc"; then
        echo "  MODIFIED: $doc"
    else
        echo "  unchanged: $doc"
    fi
done
echo ""

# Detect specific change patterns
echo "=== Detected Change Patterns ==="
echo ""

# New modules
NEW_DIRS=$(git diff --name-only --diff-filter=A "$MERGE_BASE"..HEAD 2>/dev/null | grep -E '^src/cognifold/[^/]+/__init__\.py$' | sed 's|src/cognifold/||;s|/__init__.py||' || true)
if [ -n "$NEW_DIRS" ]; then
    echo "NEW MODULES: $NEW_DIRS"
fi

# CLI changes
if echo "$CHANGED_FILES" | grep -qE '^src/cognifold/cli/'; then
    echo "CLI CHANGES detected (src/cognifold/cli/)"
fi

# Service/API changes
if echo "$CHANGED_FILES" | grep -qE '^src/cognifold/service/'; then
    echo "SERVICE/API CHANGES detected (src/cognifold/service/)"
fi

# Prompt changes
if echo "$CHANGED_FILES" | grep -qE '^src/cognifold/agent/prompt'; then
    echo "PROMPT CHANGES detected (src/cognifold/agent/prompts)"
fi

# Model/schema changes
if echo "$CHANGED_FILES" | grep -qE '^src/cognifold/models/'; then
    echo "MODEL/SCHEMA CHANGES detected (src/cognifold/models/)"
fi

# Dependency changes
if echo "$CHANGED_FILES" | grep -qx "pyproject.toml"; then
    echo "DEPENDENCY CHANGES detected (pyproject.toml)"
fi

# Skills/commands changes
if echo "$CHANGED_FILES" | grep -qE '^\.claude/(commands|skills)/'; then
    echo "SKILL/COMMAND CHANGES detected (.claude/)"
fi

# Core module changes (cognition principles alignment)
if echo "$CHANGED_FILES" | grep -qE '^src/cognifold/(agent|query|graph|scoring|intent)/'; then
    echo "CORE MODULE CHANGES detected — verify COGNITION_PRINCIPLES.md alignment"
fi

# Check if no patterns detected
if [ -z "$NEW_DIRS" ] && \
   ! echo "$CHANGED_FILES" | grep -qE '^src/cognifold/(cli|service|agent/prompt|models)/' && \
   ! echo "$CHANGED_FILES" | grep -qx "pyproject.toml" && \
   ! echo "$CHANGED_FILES" | grep -qE '^\.claude/(commands|skills)/' && \
   ! echo "$CHANGED_FILES" | grep -qE '^src/cognifold/(agent|query|graph|scoring|intent)/'; then
    echo "(no special patterns detected beyond general source changes)"
fi
echo ""

# Recent commit messages for phase detection
echo "=== Recent Commit Messages ==="
echo ""
git log --oneline "$MERGE_BASE"..HEAD 2>/dev/null | head -20 || echo "(no commits)"
echo ""

echo "=== End Doc-Guard Analysis ==="
