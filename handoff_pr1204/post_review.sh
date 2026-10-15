#!/usr/bin/env bash
# Post the verified atomic-reservation review to the existing leanSpec PR #1204.
# Deliberately does not fork, push, merge, or open a competing pull request.
set -Eeuo pipefail

UPSTREAM="leanEthereum/leanSpec"
PR=1204
EXPECTED_ACCOUNT="fraware"
EXPECTED_HEAD="e8f9c29da3c2b725b988ed85dac8dce3d89d0012"
REVIEW_COMMIT="cbbe83dfd19b858d2ec928da58e520625beb9351"
REVIEW_BLOB="9805fa0be79e88ff3e79c381522d3698e0d058d7"
REVIEW_MARKER="fraware-xmss-atomic-review-v1-e8f9c29"
REVIEW_URL="https://raw.githubusercontent.com/fraware/lean-project-evidence/${REVIEW_COMMIT}/handoff_pr1204/REVIEW_NOTE.md"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
for binary in gh git curl; do
    command -v "$binary" >/dev/null 2>&1 || fail "Missing executable: $binary"
done

gh auth status >/dev/null 2>&1 || fail "Authenticate locally with 'gh auth login' first"
account="$(gh api user --jq '.login')"
[[ "$account" == "$EXPECTED_ACCOUNT" ]] || fail "Expected account $EXPECTED_ACCOUNT, got $account"

head="$(gh api "repos/${UPSTREAM}/pulls/${PR}" --jq '.head.sha')"
[[ "$head" == "$EXPECTED_HEAD" ]] || fail "PR head changed to $head; review the patch anew"
state="$(gh api "repos/${UPSTREAM}/pulls/${PR}" --jq '.state')"
[[ "$state" == "open" ]] || fail "PR is no longer open"

# Fail closed on a previous matching comment by this account. GitHub issues/comments
# includes ordinary PR discussion comments. The review marker is unique to this note.
previous_reviews="$(gh api "repos/${UPSTREAM}/issues/${PR}/comments?per_page=100" \
    --paginate --jq '.[] | select(.user.login == "fraware") | .body')" \
    || fail "Unable to verify existing PR comments safely"
if grep -Fq "$REVIEW_MARKER" <<< "$previous_reviews"; then
    printf 'Already posted an identical review marker. No duplicate comment created.\n'
    exit 0
fi

note="$(mktemp "${TMPDIR:-/tmp}/xmss-pr1204-review.XXXXXXXX")"
trap 'rm -f "$note"' EXIT
curl --fail --silent --show-error --location "$REVIEW_URL" --output "$note"
[[ -s "$note" ]] || fail "Empty review download"
[[ "$(git hash-object "$note")" == "$REVIEW_BLOB" ]] || fail "Review bytes differ from pinned evidence"
grep -Fq "$REVIEW_MARKER" "$note" || fail "Review marker absent"

# External account-level action; the script never claims success before gh returns.
gh pr comment "$PR" --repo "$UPSTREAM" --body-file "$note"
printf 'Upstream review submitted to https://github.com/%s/pull/%s\n' "$UPSTREAM" "$PR"
