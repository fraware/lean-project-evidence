#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_OWNER:?Set GITHUB_OWNER}"
REPO_NAME="${REPO_NAME:-lean-project-evidence}"
VISIBILITY="${VISIBILITY:-public}"

command -v gh >/dev/null 2>&1 || {
  echo "GitHub CLI 'gh' is required" >&2
  exit 2
}

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  git init
  git add .
  git commit -m "chore: initialize Lean Project Evidence"
  git branch -M main
fi

gh repo create "${GITHUB_OWNER}/${REPO_NAME}" \
  "--${VISIBILITY}" \
  --description "Project-grounded evidence and review infrastructure for AI-assisted Lean development" \
  --source . \
  --remote origin \
  --push

echo "Repository created."
echo "Next steps:"
echo "  1. Replace placeholders in .github/CODEOWNERS (see MAINTAINERS.md)"
echo "  2. python scripts/github_launch.py labels --apply"
echo "  3. python scripts/github_launch.py milestones --apply"
echo "  4. python scripts/github_launch.py import-issues --apply"
echo "  5. Configure branch protection per docs/16_REPOSITORY_LAUNCH.md"
echo "  6. python scripts/verify_clean_clone.py"
