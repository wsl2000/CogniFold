#!/usr/bin/env bash
# One-time setup of branch protection on the canonical repo's integration branch.
#
# Canonical repo : OpenNorve/CogniFold   (public, fork-based contribution model)
# Protected branch: main                 (the repo default / PR target)
#
# Effect: nobody can push directly to `main`; every change must arrive via a PR
# that (a) passes the "Lint, Type Check, Test" CI check, (b) has >= 1 maintainer
# approval, (c) has all review conversations resolved, and (d) is up to date with
# main before merge. This is exactly what a many-external-collaborator fork flow
# needs — external contributors keep ZERO write access and land work via PRs.
#
# Requires: gh CLI authenticated as a repo admin (you are: wsl2000, admin=true).
# Review the JSON below, then run:  bash scripts/setup_branch_protection.sh
#
# Revert (remove protection):
#   gh api -X DELETE repos/OpenNorve/CogniFold/branches/main/protection

set -euo pipefail

REPO="OpenNorve/CogniFold"
BRANCH="main"

# Notes on the chosen settings (tweak to taste before running):
# - required_status_checks.contexts: MUST match the GitHub Actions job display
#   name exactly. ci.yml job `quality` has `name: Lint, Type Check, Test`, and it
#   triggers on PRs to [main, cognifold-dev] — verified. The slower
#   "Docker Build Smoke Test" job is intentionally NOT required (keep it advisory).
# - strict=true: the PR branch must be up to date with main before merge.
# - enforce_admins=false: maintainers can still hotfix in an emergency. Set true
#   for maximum strictness (admins also blocked from direct push).
# - required_approving_review_count=1, dismiss_stale_reviews=true.
# - allow_force_pushes/allow_deletions=false: main cannot be force-pushed or deleted.
# - required_conversation_resolution=true: all PR threads must be resolved.
# - required_linear_history=false: works with squash/merge commits. Set true only
#   if you mandate rebase/squash.

echo "Applying branch protection to ${REPO}@${BRANCH} ..."
gh api -X PUT "repos/${REPO}/branches/${BRANCH}/protection" \
  -H "Accept: application/vnd.github+json" \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["Lint, Type Check, Test"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

echo "Done. Verify with:"
echo "  gh api repos/${REPO}/branches/${BRANCH}/protection --jq '{checks:.required_status_checks.contexts, reviews:.required_pull_request_reviews.required_approving_review_count, force_push:.allow_force_pushes.enabled}'"
