#!/usr/bin/env bash
# Intentionally publish one source-pinned review through the user's gh session.
# Never invoked automatically by GitHub Actions or this repository.
set -Eeuo pipefail
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
command -v gh >/dev/null 2>&1 || fail "GitHub CLI gh is missing"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTE="$HERE/REVIEW_NOTE.md"
test -s "$NOTE" || fail "Missing reviewed note"
marker="leanvm-pr533-two-folds-reviewed-20261013-v1"
grep -Fq "$marker" "$NOTE" || fail "Missing stable publication marker"

login="$(gh api user --jq .login)" || fail "GitHub authentication unavailable"
[[ "$login" == "fraware" ]] || fail "Contributor login mismatch: $login"
head="$(gh api repos/leanEthereum/leanVM/pulls/533 --jq .head.sha)" \
  || fail "PR head not accessible"
[[ "$head" == "4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d" ]] \
  || fail "PR head moved: re-review exact source before publication"
existing="$(gh api 'repos/leanEthereum/leanVM/issues/533/comments?per_page=100' \
  --paginate --jq '.[] | select(.user.login=="fraware") | .body')" \
  || fail "Could not audit existing comments"
if grep -Fq "$marker" <<< "$existing"; then
  printf 'Review already posted. No duplicate created.\n'
  exit 0
fi

printf 'Validated identity and exact PR head. Review: %s\n' "$NOTE"
if [[ "${1:-}" != "--publish" ]]; then
  printf 'No GitHub comment was created. Use --publish to submit intentionally.\n'
  exit 0
fi
gh api -X POST repos/leanEthereum/leanVM/issues/533/comments \
  -f body="$(cat "$NOTE")" --jq '.html_url'
