#!/usr/bin/env bash
# Deliberate, one-time publication using an explicitly authenticated contributor
# identity. No tool/agent or scheduled workflow invokes this file automatically.
set -Eeuo pipefail
fail() { printf '%s\n' "ERROR: $*" >&2; exit 1; }

command -v gh >/dev/null 2>&1 || fail "Install and authenticate GitHub CLI (gh)."
command -v git >/dev/null 2>&1 || fail "Missing Git CLI."
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTE="${HERE}/REVIEW_NOTE.md"
test -s "$NOTE" || fail "Review note not present: $NOTE"
marker="leanvm-pr533-fold12-reviewed-20261013-v1"
grep -Fq "$marker" "$NOTE" || fail "Idempotency marker absent"

login="$(gh api user --jq .login)" || fail "GitHub CLI user unavailable"
test "$login" = "fraware" || fail "Expected contributor identity fraware, got $login"
head="$(gh api repos/leanEthereum/leanVM/pulls/533 --jq .head.sha)" || fail "PR head query failed"
test "$head" = "4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d" \
  || fail "PR #533 head changed since proof review; re-evaluate before publishing"

existing="$(gh api 'repos/leanEthereum/leanVM/issues/533/comments?per_page=100' \
  --paginate --jq '.[] | select(.user.login=="fraware") | .body' 2>/dev/null)" \
  || fail "Cannot inspect existing PR comments"
if grep -Fq "$marker" <<< "$existing"; then
  printf 'Existing review with marker found; no duplicate published.\n'
  exit 0
fi

printf 'Authenticated as %s. Pinned PR head: %s\n' "$login" "$head"
printf 'Comment file: %s\n' "$NOTE"
printf 'To publish the checked review intentionally, invoke this script with --publish.\n'
if [[ "${1:-}" != "--publish" ]]; then exit 0; fi

gh api -X POST repos/leanEthereum/leanVM/issues/533/comments \
  -f body="$(cat "$NOTE")" --jq '.html_url'
