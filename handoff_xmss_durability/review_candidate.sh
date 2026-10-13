#!/usr/bin/env bash
# Rebuild the source-pinned six-file leanSpec XMSS candidate for local review.
# This script never pushes, forks, opens a PR, or uses GitHub credentials.
set -Eeuo pipefail

PIN="e8f9c29da3c2b725b988ed85dac8dce3d89d0012"
EVIDENCE="79b27bba5154298de32681dcadcc8ec8628de54b"
RAW="https://raw.githubusercontent.com/fraware/lean-project-evidence/${EVIDENCE}"
UPSTREAM="https://github.com/leanEthereum/leanSpec.git"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
for executable in git curl mktemp; do
  command -v "$executable" >/dev/null 2>&1 || fail "Missing executable: $executable"
done

ROOT="$(mktemp -d "${TMPDIR:-/tmp}/lean-xmss-review.XXXXXXXX")"
REPO="${ROOT}/leanSpec"
printf 'Isolated review workspace: %s\n' "$ROOT"
git clone --filter=blob:none "$UPSTREAM" "$REPO" || fail "Unable to clone upstream"
git -C "$REPO" fetch origin pull/1204/head || fail "Unable to fetch PR #1204"
git -C "$REPO" checkout --detach "$PIN"
[[ "$(git -C "$REPO" rev-parse HEAD)" == "$PIN" ]] || fail "Unexpected upstream source revision"

# Source path | target path | expected git blob SHA, all pinned to EVIDENCE.
while IFS='|' read -r source target expected; do
  [[ -n "$source" ]] || continue
  curl --fail --silent --show-error --location "${RAW}/${source}" --output "${REPO}/${target}" \
    || fail "Unable to retrieve candidate: $source"
  actual="$(git -C "$REPO" hash-object "$target")"
  [[ "$actual" == "$expected" ]] || fail "Blob identity mismatch for $target: $actual"
  printf 'Verified %s: %s\n' "$target" "$actual"
done <<'FILES'
candidate_pr1204/database.py|src/lean_spec/node/storage/database.py|355dfbb5bd2bd50b1b9d24c67a417b04b4363af0
candidate_pr1204/sqlite.py|src/lean_spec/node/storage/sqlite.py|6cc850de693b88a26cff7756585f0dcc916add4b
candidate_pr1204/signing_protection.py|src/lean_spec/node/validator/signing_protection.py|80ad929a583f6e0f88b3be2a9a8935922d951090
candidate_pr1204/test_signing_protection.py|tests/node/validator/test_signing_protection.py|501379d3712b9104dd8f2dfc06b07b3f4d337702
candidate_composed/service.py|src/lean_spec/node/validator/service.py|fae6296e8afb2c020a0535d7a6b68370f7240fd0
candidate_composed/test_service.py|tests/node/validator/test_service.py|3dcb21d63b33b449b035ab5193bf06f842808c35
FILES

git -C "$REPO" diff --check || fail "Whitespace-integrity gate failed"
git -C "$REPO" diff --binary > "${ROOT}/xmss-combined.patch"
[[ -s "${ROOT}/xmss-combined.patch" ]] || fail "No changes recorded"
git -C "$REPO" diff --stat

printf '\nReview checkout: %s\n' "$REPO"
printf 'Complete combined patch: %s\n' "${ROOT}/xmss-combined.patch"
printf 'No repository write or upstream PR operation was performed.\n'
