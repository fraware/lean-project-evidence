# Atomic, monotone SQLite XMSS reservation: stacked correction to leanSpec PR #1204

**Base**: `leanEthereum/leanSpec@e8f9c29da3c2b725b988ed85dac8dce3d89d0012` (exact head of upstream PR #1204 checked 12 October 2026). This is a reviewable patch **on top of PR #1204**, not a patch to current upstream main.

The correction replaces separate read/check/unconditional replacement with one conditional SQLite UPSERT and a committed success/failure return. It removes the unrestricted `put_last_signed_slot` method so the public database protocol no longer exposes a downgrade path. The existing `SigningProtectionError` duty contract and in-process fallback are retained.

The candidate includes three native regression tests: two SQLite handles claiming the same slot concurrently, refusal of a delayed lower-slot claim, and independence of two role-specific keys.

## Scope and limitations

- Safety relies on the committed shared SQLite file and a single agreed logical validator/role key identity. Two independent database files, backups rolled back to prior states, and accidental reuse of the same XMSS secret across logical identities are **outside** this patch.
- No cryptographic equivalence or end-to-end formal proof is claimed.
- Full acceptance results are tracked on the isolated branch `research/ethereum-xmss-pr1204-atomic-20261012`, with a strict hosted run completed successfully.

## Apply and independently verify against PR #1204

```sh
git fetch origin pull/1204/head
git checkout --detach e8f9c29da3c2b725b988ed85dac8dce3d89d0012
git apply --check pr1204-atomic-reservation.patch
git apply pr1204-atomic-reservation.patch
git diff --check
```

Expected Git blob hashes (source then modified):

- `src/lean_spec/node/storage/database.py`: `3023a3aed674fba16e46bda5722a691081c0d20a` → `355dfbb5bd2bd50b1b9d24c67a417b04b4363af0`
- `src/lean_spec/node/storage/sqlite.py`: `0df19c168bc23751e235f1eef4d56f9b9242933a` → `660c3dfff3fbc7ad384929831dfd5761812cd773`
- `src/lean_spec/node/validator/signing_protection.py`: `218c66c035949a1b59f834245273acfa4e46d638` → `5d7baef324dde273cc8b67ddfba6b6a0c6000236`
- `tests/node/validator/test_signing_protection.py`: `c31631acd1b9db5bf16dfc5bf15cf03c78eb62d2` → `063c055588bdb2818ce73e4af1f0d766dd94d350`

The corresponding [sqlite protocol reproducer](https://github.com/fraware/lean-project-evidence/blob/research/ethereum-xmss-reservations-20261012/experiments/ethereum-xmss/test_reservation_sqlite.py) and [exact PR reserve-method race reproducer](https://github.com/fraware/lean-project-evidence/actions/runs/38317231036) establish the pre-correction failure under forced concurrent schedules.

## Verified native acceptance — 12 October 2026

- [Strict CI run #38319468627](https://github.com/fraware/lean-project-evidence/actions/runs/38319468627) — **success**, using the committed four-file candidate with **no runtime autofixing**. Ruff lint and formatting passed, whole-project `ty check` passed, **69 focused signing-protection/validator tests passed**, and the complete standard pytest suite reported **2,964 passed**, total coverage **92%**.
- [Exact patch reproduction #38319568933](https://github.com/fraware/lean-project-evidence/actions/runs/38319568933) — **success**: fresh PR #1204 checkout at `e8f9c29d`, Git blob preconditions, `git apply --check`, `git diff --check`, exact output Git blob IDs, Python compilation.
- [Actual PR-method two-connection reproducer #38317231036](https://github.com/fraware/lean-project-evidence/actions/runs/38317231036) — **2 passed** under intentionally injected schedules against the uncorrected PR reserve method (using an instrumented SQLite adapter). Those tests demonstrate the multi-connection behavior outside the existing single-writer deployment assumption.
- [Lean model and SQLite protocol #38317050285](https://github.com/fraware/lean-project-evidence/actions/runs/38317050285) — kernel-checked abstract reservation lemmas and seven adversarial SQLite tests passed.

The successful native suite exercises a checkout of **PR #1204's exact head**, not the unmodified upstream main. It does not include an external multi-node key-sharing guarantee. Interoperability tests were **not run separately** for this atomic-only candidate; the repository standard suite follows upstream pytest configuration.

## Publication sequence

This is a **stacked correction for PR #1204**, whose source has not merged into upstream main. Posting this patch as a direct, standalone PR against main without the parent changes would conflate two reviews. The immediate maintainer action is to review the [precise review note](./REVIEW_NOTE.md) and [four-file diff](./pr1204-atomic-reservation.patch) alongside the open [PR #1204](https://github.com/leanEthereum/leanSpec/pull/1204).

Upstream writes from the connected GitHub integration have returned HTTP 403; the research repository has write access, but no authorized fraware fork of leanSpec exists. As a result this evidence has **not** been posted to upstream PR #1204, and no upstream merge or review is asserted.

## Authenticated upstream review publication

The connected GitHub integration does not have permission to comment on the upstream repository (HTTP 403), and a `fraware/leanSpec` fork is not available. The tested publication helper uses GitHub CLI authentication **on the user's machine** to post the precise review note to the existing PR #1204 without making a competing PR.

```bash
gh auth status
curl -fsSLo post_review.sh https://raw.githubusercontent.com/fraware/lean-project-evidence/fd37c9f946dd2b326b52182a89621ad1cc8265a0/handoff_pr1204/post_review.sh
bash -n post_review.sh
bash post_review.sh
```

Before posting, it checks the authenticated account is `fraware`, the PR is open at the exact reviewed head `e8f9c29d`, the comment marker has not already been posted, and the downloaded note matches its immutable Git blob hash. If the comment-history API request fails, the helper refuses to post. It does not store credentials or use a token in a URL.

The helper has [seven offline process-level contract tests](./test_post_review.py) which simulate GitHub CLI and download operations, including rejection paths; **those tests do not create an actual upstream comment**. Running the helper with authorized GitHub CLI credentials is still a user-authorized external action.

## Provenance

- [Strict full-suite native validation](https://github.com/fraware/lean-project-evidence/actions/runs/38319468627) — 69 focused tests, 2,964 standard tests, 92% coverage, Ruff, and ty.
- [Source-exact four-file patch reconstruction](https://github.com/fraware/lean-project-evidence/actions/runs/38319568933) — successful.
- [Actual open PR head, #1204](https://github.com/leanEthereum/leanSpec/pull/1204).
