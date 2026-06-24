#!/usr/bin/env bash
# deploy-pages.sh — one command to publish docs-site/ to wsl2000.github.io/CogniFold
#
# It does the whole "old process" for you, race-free:
#   1. commit any pending docs-site/ changes  (optional message: ./deploy-pages.sh "msg")
#   2. push HEAD -> wsl2000/CogniFold:main     (detached-HEAD safe)
#   3. wait until GitHub registers the new tip (no fixed sleep — polls the API)
#   4. dispatch pages.yml on that exact commit (fork pushes don't auto-build)
#   5. watch the Pages build to success
#   6. verify the live site returns 200
#
# Safety: only ever touches the remote whose URL is wsl2000/CogniFold.
#         It will refuse to run if that remote looks like OpenNorve.
#         OpenNorve/CogniFold and PR #24 are never touched.
set -euo pipefail

REPO="wsl2000/CogniFold"
BRANCH="main"
WORKFLOW="pages.yml"
LIVE_URL="https://wsl2000.github.io/CogniFold/"
SITE_DIR="docs-site"

cd "$(git rev-parse --show-toplevel)"

# --- find the remote that points at wsl2000/CogniFold (push) ---
REMOTE="$(git remote -v | awk -v r="$REPO" '$2 ~ r && $3=="(push)"{print $1; exit}')"
if [ -z "${REMOTE:-}" ]; then
  echo "✗ no git remote points at $REPO. Add one:" >&2
  echo "    git remote add fork git@github.com:$REPO.git" >&2
  exit 1
fi
URL="$(git remote get-url "$REMOTE")"
case "$URL" in
  *OpenNorve*|*opennorve*) echo "✗ remote '$REMOTE' ($URL) is OpenNorve — refusing. Deploy only targets $REPO." >&2; exit 1;;
esac
echo "→ remote '$REMOTE' → $REPO  (branch $BRANCH)"

# --- commit pending docs-site changes (if any) ---
MSG="${1:-}"
if [ -n "$(git status --porcelain -- "$SITE_DIR")" ]; then
  [ -z "$MSG" ] && MSG="site(wsl2000): update docs-site"
  git add -A -- "$SITE_DIR"
  git commit -q -m "$MSG"
  echo "→ committed: $MSG"
else
  echo "→ no pending $SITE_DIR/ changes; deploying current HEAD"
fi

SHA="$(git rev-parse HEAD)"
echo "→ HEAD = $SHA"

# --- push HEAD -> wsl2000:main ---
git push "$REMOTE" "HEAD:$BRANCH"
echo "→ pushed to $REPO:$BRANCH"

# --- wait until GitHub reports the branch tip == our SHA (race-free dispatch) ---
echo "→ waiting for $REPO:$BRANCH tip to register $SHA …"
for _ in $(seq 1 30); do
  TIP="$(gh api "repos/$REPO/branches/$BRANCH" --jq '.commit.sha' 2>/dev/null || true)"
  [ "$TIP" = "$SHA" ] && break
  sleep 2
done
[ "${TIP:-}" = "$SHA" ] || { echo "✗ branch tip never matched $SHA (last: ${TIP:-none})" >&2; exit 1; }

# --- dispatch pages.yml on that commit (fork pushes don't auto-trigger) ---
gh workflow run "$WORKFLOW" --repo "$REPO" --ref "$BRANCH"
echo "→ dispatched $WORKFLOW"

# --- find the dispatched run for our SHA, then watch it ---
echo "→ locating the Pages build for $SHA …"
RUN_ID=""
for _ in $(seq 1 30); do
  RUN_ID="$(gh run list --repo "$REPO" --workflow "$WORKFLOW" --limit 12 \
            --json databaseId,headSha,event \
            --jq "[.[] | select(.headSha==\"$SHA\" and .event==\"workflow_dispatch\")][0].databaseId" 2>/dev/null || true)"
  [ -n "$RUN_ID" ] && [ "$RUN_ID" != "null" ] && break
  sleep 3
done
[ -n "$RUN_ID" ] && [ "$RUN_ID" != "null" ] || { echo "✗ no dispatched run found for $SHA" >&2; exit 1; }
echo "→ run $RUN_ID building $SHA — watching…"
if ! gh run watch "$RUN_ID" --repo "$REPO" --exit-status >/dev/null 2>&1; then
  echo "✗ Pages build failed (run $RUN_ID):" >&2
  gh run view "$RUN_ID" --repo "$REPO" --log-failed 2>/dev/null | tail -30 >&2 || true
  exit 1
fi
echo "✓ Pages build succeeded (run $RUN_ID)"

# --- verify live (CDN can lag a few seconds) ---
echo "→ verifying $LIVE_URL …"
CODE=000
for _ in $(seq 1 20); do
  CODE="$(curl -s -o /dev/null -w '%{http_code}' "$LIVE_URL" || true)"
  [ "$CODE" = "200" ] && break
  sleep 3
done
[ "$CODE" = "200" ] && echo "✓ live: $LIVE_URL (HTTP 200)" || echo "⚠ live check returned HTTP $CODE — build is done; CDN may still be propagating."
echo "Done."
