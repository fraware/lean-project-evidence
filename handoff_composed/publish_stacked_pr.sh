#!/usr/bin/env bash
# Publish a stacked PR from fraware/leanSpec into the author's PR #1204 branch.
# Review the script and PR_BODY_STACKED.md before executing with local gh auth.
set -Eeuo pipefail

UPSTREAM="leanEthereum/leanSpec"
BASE_REPO="adust09/leanSpec"
BASE_BRANCH="feat/durable-signing-protection"
PIN="e8f9c29da3c2b725b988ed85dac8dce3d89d0012"
BRANCH="fix/atomic-xmss-preflight-on-pr1204-20261013"
REF="0fbba82f9658f58a4515a2767cc7c1b98f946170"
PATCH_URL="https://raw.githubusercontent.com/fraware/lean-project-evidence/${REF}/handoff_composed/xmss-composed.patch"
BODY_URL="https://raw.githubusercontent.com/fraware/lean-project-evidence/${REF}/handoff_composed/PR_BODY_STACKED.md"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
for tool in gh git curl awk; do command -v "$tool" >/dev/null 2>&1 || fail "Missing $tool"; done
gh auth status >/dev/null 2>&1 || fail "Run gh auth login as fraware first"
LOGIN="$(gh api user --jq '.login')"
[[ "$LOGIN" == "fraware" ]] || fail "Expected authenticated user fraware, got ${LOGIN}"
CURRENT_BASE="$(git ls-remote --exit-code "https://github.com/${BASE_REPO}.git" "refs/heads/${BASE_BRANCH}" | awk '{print $1}')"
[[ "$CURRENT_BASE" == "$PIN" ]] || fail "Author branch changed (${CURRENT_BASE}); rebase and revalidate first"

if gh repo view "${LOGIN}/leanSpec" --json nameWithOwner >/dev/null 2>&1; then
  printf 'Reusing existing fork %s/leanSpec\n' "$LOGIN"
else
  printf 'Forking %s under %s\n' "$UPSTREAM" "$LOGIN"
  gh repo fork "$UPSTREAM" --clone=false
fi
PARENT="$(gh api "repos/${LOGIN}/leanSpec" --jq '.parent.full_name')"
[[ "$PARENT" == "$UPSTREAM" ]] || fail "Existing repository is not a fork of ${UPSTREAM}: ${PARENT}"

ROOT="$(mktemp -d "${TMPDIR:-/tmp}/leanspec-composed-pr.XXXXXXXX")"
printf 'Reviewable working directory: %s\n' "$ROOT"
gh repo clone "${LOGIN}/leanSpec" "$ROOT/leanSpec" -- --quiet
REPO="$ROOT/leanSpec"
git -C "$REPO" fetch --quiet "https://github.com/${BASE_REPO}.git" "$BASE_BRANCH"
git -C "$REPO" cat-file -e "${PIN}^{commit}" || fail "Expected upstream PR commit unavailable"
git -C "$REPO" switch -c "$BRANCH" "$PIN"

curl -fsSL "$PATCH_URL" -o "$ROOT/composed.patch"
curl -fsSL "$BODY_URL" -o "$ROOT/PR_BODY_STACKED.md"
[[ -s "$ROOT/composed.patch" && -s "$ROOT/PR_BODY_STACKED.md" ]] || fail "Missing immutable handoff files"
git -C "$REPO" apply --check "$ROOT/composed.patch"
git -C "$REPO" apply "$ROOT/composed.patch"
git -C "$REPO" diff --check

# All six hashes are from the successful exact-patch witness and combined CI files.
while read -r file expected; do
  [[ "$(git -C "$REPO" hash-object "$file")" == "$expected" ]] || fail "Git blob mismatch: $file"
done <<'BLOBS'
src/lean_spec/node/storage/database.py 355dfbb5bd2bd50b1b9d24c67a417b04b4363af0
src/lean_spec/node/storage/sqlite.py 660c3dfff3fbc7ad384929831dfd5761812cd773
src/lean_spec/node/validator/signing_protection.py 5d7baef324dde273cc8b67ddfba6b6a0c6000236
tests/node/validator/test_signing_protection.py 063c055588bdb2818ce73e4af1f0d766dd94d350
src/lean_spec/node/validator/service.py 9851994dc3bde0b4fb48c6d68d3a7b075b40960e
tests/node/validator/test_service.py 2d83eaa71529bafda6e914e9c8c66b81e98d3870
BLOBS

if git -C "$REPO" ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  fail "Remote fork branch already exists; refusing to overwrite it"
fi
git -C "$REPO" add -- src/lean_spec/node/storage/database.py \
  src/lean_spec/node/storage/sqlite.py \
  src/lean_spec/node/validator/signing_protection.py \
  tests/node/validator/test_signing_protection.py \
  src/lean_spec/node/validator/service.py \
  tests/node/validator/test_service.py
git -C "$REPO" diff --cached --check
git -C "$REPO" commit -m 'fix(validator): atomic XMSS reservation and pre-signing validation'
git -C "$REPO" push --set-upstream origin "$BRANCH"

# Target the PR author's feature branch; avoids adding duplicate PR #1204 changes
# to a separate pull request against leanEthereum/leanSpec main.
gh pr create --repo "$BASE_REPO" --base "$BASE_BRANCH" --head "${LOGIN}:${BRANCH}" \
  --title 'fix(validator): atomic XMSS reservations and signing preflight' \
  --body-file "$ROOT/PR_BODY_STACKED.md"

printf '\nStacked PR submitted to https://github.com/%s/pulls\n' "$BASE_REPO"
printf 'PR #1204 remains separate at https://github.com/%s/pull/1204\n' "$UPSTREAM"
printf 'Local working files retained in %s\n' "$ROOT"
