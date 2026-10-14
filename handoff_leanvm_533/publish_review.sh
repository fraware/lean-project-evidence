#!/usr/bin/env bash
# Deliberate contributor-controlled upstream review submission.
# Not invoked automatically by CI, jobs, or source checkouts.
set -Eeuo pipefail

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
command -v gh >/dev/null 2>&1 || fail "GitHub CLI gh not installed"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
note="$here/REVIEW_NOTE.md"
test -s "$note" || fail "Missing review note"
marker="leanvm-pr533-swar42-reviewed-20261013-v1"
grep -Fq "$marker" "$note" || fail "Missing idempotency marker"
login="$(gh api user --jq .login)" || fail "No authenticated GitHub identity"
[[ "$login" == "fraware" ]] || fail "Contributor login mismatch: $login"
head="$(gh api repos/leanEthereum/leanVM/pulls/533 --jq .head.sha)" || fail "Cannot read upstream PR"
[[ "$head" == "4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d" ]] || fail "Upstream head changed; source pin needs revalidation"
existing="$(gh api 'repos/leanEthereum/leanVM/issues/533/comments?per_page=100' --paginate \
  --jq '.[] | select(.user.login=="fraware") | .body')" || fail "Cannot check existing comments"
if grep -Fq "$marker" <<< "$existing"; then
  printf 'Review already present; no duplicate.\n'
  exit 0
fi
if [[ "${1:-}" != "--publish" ]]; then
  printf 'Validated authenticated identity and upstream source. No review posted.\n'
  printf 'To post deliberately, run: bash %q --publish\n' "$0"
  exit 0
fi
gh api -X POST repos/leanEthereum/leanVM/issues/533/comments -f body="$(cat "$note")" --jq .html_url
