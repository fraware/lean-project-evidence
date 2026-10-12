#!/usr/bin/env bash
# Publish the source-pinned, CI-tested leanSpec XMSS validator correction.
# Invocations require an authenticated GitHub CLI and make public GitHub changes.
set -Eeuo pipefail

UPSTREAM="leanEthereum/leanSpec"
PIN="0b7d33ecbc9ee2435759c92de4da4d08d7faf1c8"
PATCH_COMMIT="4fee17e4245534ed439678dad8d49bbe78ffeb92"
PATCH_URL="https://raw.githubusercontent.com/fraware/lean-project-evidence/${PATCH_COMMIT}/handoff/leanSpec-xmss-preconditions.patch"
BODY_URL="https://raw.githubusercontent.com/fraware/lean-project-evidence/cb5f8f6a244233a5c14014edc7ad03aae27ebff9/handoff/PR_BODY.md"
BRANCH="fix/xmss-signing-preconditions-20261012"
EXPECTED_SERVICE="b5b2869c51740baf78de5a829ea36597dc480fec"
EXPECTED_TESTS="a055b66048f20d15c6c58c9ddc5954537e76c0b2"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
for program in gh git curl; do
  command -v "$program" >/dev/null 2>&1 || fail "Missing ${program} executable"
done
# Avoid using a personal access token in the command line or in a workflow secret.
gh auth status >/dev/null 2>&1 || fail "Please sign in locally first: gh auth login"
LOGIN="$(gh api user --jq '.login')"
[[ "$LOGIN" =~ ^[a-zA-Z0-9-]+$ ]] || fail "Unexpected GitHub login string"

if gh repo view "${LOGIN}/leanSpec" --json nameWithOwner >/dev/null 2>&1; then
  printf 'Using existing repository %s/leanSpec\n' "$LOGIN"
else
  printf 'Creating fork of %s under GitHub user %s\n' "$UPSTREAM" "$LOGIN"
  gh repo fork "$UPSTREAM" --clone=false
fi
PARENT="$(gh api "repos/${LOGIN}/leanSpec" --jq '.parent.full_name')"
[[ "$PARENT" == "$UPSTREAM" ]] || fail "${LOGIN}/leanSpec is not a fork of ${UPSTREAM} (parent: ${PARENT})"

ROOT="$(mktemp -d "${TMPDIR:-/tmp}/leanspec-xmss-publish.XXXXXXXX")"
printf 'Isolated working folder: %s\n' "$ROOT"
printf 'This folder is retained for inspection on success or failure.\n'
gh repo clone "${LOGIN}/leanSpec" "${ROOT}/leanSpec" -- --quiet
REPO="${ROOT}/leanSpec"
git -C "$REPO" cat-file -e "${PIN}^{commit}" || fail "Pinned source commit not present in fork clone"
# The source-pinned patch must be applied to its exact upstream ancestor.
git -C "$REPO" switch --create "$BRANCH" "$PIN"
curl --fail --silent --show-error --location "$PATCH_URL" --output "${ROOT}/correction.patch"
[[ -s "${ROOT}/correction.patch" ]] || fail "Empty patch download"
git -C "$REPO" apply --check "${ROOT}/correction.patch"
git -C "$REPO" apply "${ROOT}/correction.patch"
git -C "$REPO" diff --check
SERVICE_SHA="$(git -C "$REPO" hash-object src/lean_spec/node/validator/service.py)"
TESTS_SHA="$(git -C "$REPO" hash-object tests/node/validator/test_service.py)"
[[ "$SERVICE_SHA" == "$EXPECTED_SERVICE" ]] || fail "Production code hash mismatch: $SERVICE_SHA"
[[ "$TESTS_SHA" == "$EXPECTED_TESTS" ]] || fail "Regression-test hash mismatch: $TESTS_SHA"

# Fail before pushing if this candidate branch already exists remotely.
if git -C "$REPO" ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  fail "Branch ${BRANCH} already exists on ${LOGIN}/leanSpec; refusing to overwrite it"
fi

curl --fail --silent --show-error --location "$BODY_URL" --output "${ROOT}/PR_BODY.md"
[[ -s "${ROOT}/PR_BODY.md" ]] || fail "Empty PR description download"
git -C "$REPO" add -- src/lean_spec/node/validator/service.py tests/node/validator/test_service.py
git -C "$REPO" diff --cached --check
git -C "$REPO" commit -m 'fix(validator): enforce pre-signing XMSS key and preparation checks'
git -C "$REPO" push --set-upstream origin "$BRANCH"

# Let GitHub enforce the fork-network constraint and upstream PR creation permissions.
# The patch's source revision is pinned; upstream main must still be checked for drift.
gh pr create --repo "$UPSTREAM" --base main --head "${LOGIN}:${BRANCH}" \
  --title 'fix(validator): fail closed on XMSS signing preconditions' \
  --body-file "${ROOT}/PR_BODY.md"
printf '\nPUBLISHED: upstream PR was created. Working folder: %s\n' "$ROOT"