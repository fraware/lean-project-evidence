#!/usr/bin/env bash
# Review and execute locally with the authenticated fraware GitHub account.
# Publishes ONE maintainer-visible comment on leanSpec PR #1204.
set -Eeuo pipefail

UPSTREAM="leanEthereum/leanSpec"
PR="1204"
PIN="e8f9c29da3c2b725b988ed85dac8dce3d89d0012"
MARKER="XMSS-atomic-composed-20261012-e8f9c29d"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
command -v gh >/dev/null 2>&1 || fail "Install GitHub CLI (gh)"
gh auth status >/dev/null 2>&1 || fail "Run gh auth login first"
LOGIN="$(gh api user --jq '.login')"
[[ "$LOGIN" == "fraware" ]] || fail "Expected fraware; authenticated as $LOGIN"

ACTUAL="$(gh api "repos/$UPSTREAM/pulls/$PR" --jq '.head.sha')"
[[ "$ACTUAL" == "$PIN" ]] || fail "PR head changed from pinned $PIN to $ACTUAL: refresh evidence"

if gh api --paginate "repos/$UPSTREAM/issues/$PR/comments?per_page=100" \
   --jq '.[] | select(.user.login == "fraware") | .body' | grep -Fq "$MARKER"; then
  fail "A comment with this evidence marker has already been published."
fi

BODY="$(cat <<'COMMENT'
Review note for the XMSS signing reservation change, pinned to PR #1204 head `e8f9c29d`.

The current check of `last_signed_slot` precedes the database write transaction, and `INSERT OR REPLACE` is unconditional. Two instrumented SQLite connections both successfully reserve the same validator/role/slot under an interleaved schedule. A delayed lower-slot writer also reduces the high-water mark. The actual `SigningProtection.reserve` method reproduces both schedules in [two passing tests](https://github.com/fraware/lean-project-evidence/actions/runs/38317231036).

I prepared a narrowly scoped conditional SQLite UPSERT with an affected-row success check, and removed the unrestricted write method. It is committed before any XMSS signing request. Native [strict CI](https://github.com/fraware/lean-project-evidence/actions/runs/38319468627) passes Ruff, whole-project ty, **69 focused validator/signing tests** and **2,964 standard tests** (92% total coverage). A [four-file patch witness](https://github.com/fraware/lean-project-evidence/actions/runs/38319568933) confirms source-pinned application and exact output Git blobs.

A second [six-file combined patch](https://github.com/fraware/lean-project-evidence/blob/research/ethereum-xmss-composed-handoff-20261012/handoff_composed/xmss-composed.patch) composes the atomic reservation with bounded XMSS preparation and pre-signing key/state validation. It has a [verified exact patch reproduction](https://github.com/fraware/lean-project-evidence/actions/runs/38340405191). See the [combined CI](https://github.com/fraware/lean-project-evidence/actions/workflows/ethereum-xmss-pr1204-composed.yml) for current test status; **separate passing suites must not be represented as a passing combined suite**.

This demonstrates a concurrency limitation *outside* the PR's documented single-writer, exclusive-key-ownership deployment contract. The proposed SQLite change protects against two writers sharing the *same database file*. It does not coordinate independent replicas, backup rollback, or duplicated XMSS secrets under different validator/role IDs. I have not submitted a separate upstream PR because the connected GitHub integration does not have upstream write permission.

Review materials: [atomic patch and note](https://github.com/fraware/lean-project-evidence/blob/research/ethereum-xmss-pr1204-atomic-handoff-20261012/handoff_pr1204/REVIEW_NOTE.md).
COMMENT
)"
BODY="$BODY

<!-- $MARKER -->"

printf 'Upstream: %s PR #%s at %s\n' "$UPSTREAM" "$PR" "$ACTUAL"
printf 'Publishing one signed-in GitHub account comment now.\n'
gh pr comment "$PR" --repo "$UPSTREAM" --body "$BODY"
printf 'Submitted review comment to https://github.com/%s/pull/%s\n' "$UPSTREAM" "$PR"
