#!/usr/bin/env bash
# Lean Ethereum upstream delivery gate.
# Default is offline verification; 'status' is read-only.
# Only 'publish leanvm' or 'publish signing' performs a GitHub write.
set -Eeuo pipefail
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-verify}"
TARGET="${2:-}"
EXPECTED_ACCOUNT="fraware"
VM_REPO="leanEthereum/leanVM"
VM_PR=533
VM_HEAD="4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d"
SIGN_REPO="leanEthereum/leanSpec"
SIGN_PR=1204
SIGN_HEAD="e8f9c29da3c2b725b988ed85dac8dce3d89d0012"

usage() {
  cat <<'USAGE'
Usage: bash delivery/ship.sh {verify|status|publish leanvm|publish signing}
  verify            offline, read-only: verify exact 11 source artifact blobs
  status            read-only: verify blobs, account, current upstream PR heads
  publish leanvm    post one source-pinned review on leanVM PR #533
  publish signing   post one source-pinned review on leanSpec PR #1204

Never run handoff_pr1204/post_review.sh to test it: direct invocation posts.
The 'publish' operations are explicit external GitHub actions.
USAGE
}

verify_files() {
  command -v git >/dev/null 2>&1 || fail "Git is required"
  while IFS='|' read -r expected relative; do
    [[ -n "$expected" ]] || continue
    local path="$ROOT/$relative"
    [[ -f "$path" ]] || fail "Missing file: $relative"
    local actual
    actual="$(git hash-object "$path")" || fail "Cannot hash: $relative"
    [[ "$actual" == "$expected" ]] ||
      fail "Modified/unverified file: $relative (got $actual; expected $expected)"
  done <<'SHA_MANIFEST'
55f806cd137c5b01a633ad10fb063c2cfa1e2b52|handoff_leanvm_533/README.md
5a79b334e213f0233af25a263424f6dfd5cb5d6a|handoff_leanvm_533/REVIEW_NOTE.md
051ee7f283264c6176dd722d7c81714373fe0968|handoff_leanvm_533/both-folds.patch
fe81287eb57742cb84548fc07560e3f08e1a6621|handoff_leanvm_533/publish_review.sh
0d943c99c9710d9ae1f677399305ddcfaae39468|handoff_pr1204/CLAIMS.md
13b5d66a722840ed872f50c190aae6a18c719ce3|handoff_pr1204/README.md
9805fa0be79e88ff3e79c381522d3698e0d058d7|handoff_pr1204/REVIEW_NOTE.md
f84e0983a12a5fdcba4aba9de5e1f74eca3dce8c|handoff_pr1204/THREAT_MODEL.md
f12a16ec782666cac42b2a6e7418b772362d1644|handoff_pr1204/post_review.sh
cd48735630e688832a380377af8a83eab03ec32a|handoff_pr1204/pr1204-atomic-reservation.patch
f79d1f7e788084b0e93798b1e47b0baf8834df1d|handoff_pr1204/test_post_review.py
SHA_MANIFEST
  printf 'PASS: 11 source-pinned upstream delivery files match Git blob identities.\n'
}

require_gh_identity() {
  command -v gh >/dev/null 2>&1 || fail "Install/authenticate GitHub CLI (gh)"
  gh auth status >/dev/null 2>&1 || fail "No authenticated GitHub CLI session"
  local login
  login="$(gh api user --jq .login)" || fail "Cannot read GitHub identity"
  [[ "$login" == "$EXPECTED_ACCOUNT" ]] ||
    fail "Expected GitHub account $EXPECTED_ACCOUNT, got $login"
  printf 'PASS: authenticated GitHub account %s.\n' "$login"
}

check_head() {
  local repo="$1" pr="$2" expected="$3"
  local observed state
  observed="$(gh api "repos/${repo}/pulls/${pr}" --jq .head.sha)" ||
    fail "Cannot read PR $repo#$pr"
  state="$(gh api "repos/${repo}/pulls/${pr}" --jq .state)" ||
    fail "Cannot read PR state $repo#$pr"
  [[ "$state" == "open" ]] || fail "PR $repo#$pr is $state"
  [[ "$observed" == "$expected" ]] ||
    fail "PR $repo#$pr moved ($observed). Reassess evidence before publishing."
  printf 'PASS: %s#%s is open at pinned head %.12s.\n' "$repo" "$pr" "$observed"
}

case "$ACTION" in
  verify)
    [[ -z "$TARGET" ]] || { usage; fail "Unexpected argument to verify"; }
    verify_files
    printf 'Read-only verification completed. No GitHub write.\n'
    ;;
  status)
    [[ -z "$TARGET" ]] || { usage; fail "Unexpected argument to status"; }
    verify_files
    require_gh_identity
    check_head "$VM_REPO" "$VM_PR" "$VM_HEAD"
    check_head "$SIGN_REPO" "$SIGN_PR" "$SIGN_HEAD"
    printf 'Read-only status completed. No review was posted.\n'
    ;;
  publish)
    [[ "$TARGET" == "leanvm" || "$TARGET" == "signing" ]] ||
      { usage; fail "Select exactly one PR: leanvm or signing"; }
    [[ "$#" -eq 2 ]] || fail "Unexpected argument(s)"
    verify_files
    require_gh_identity
    if [[ "$TARGET" == "leanvm" ]]; then
      check_head "$VM_REPO" "$VM_PR" "$VM_HEAD"
      exec bash "$ROOT/handoff_leanvm_533/publish_review.sh" --publish
    else
      check_head "$SIGN_REPO" "$SIGN_PR" "$SIGN_HEAD"
      # IMPORTANT: this script posts by default; it has its own head, identity,
      # source-blob and deduplication checks. Only invoke on explicit 'publish'.
      exec bash "$ROOT/handoff_pr1204/post_review.sh"
    fi
    ;;
  *)
    usage
    fail "Unknown action: $ACTION"
    ;;
esac
