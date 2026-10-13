# Upstream XMSS integration: reviewer decision record

Date: 2026-10-13

## Verified technical baseline

The current candidate is pinned to upstream `leanEthereum/leanSpec` PR #1204
(`e8f9c29da3c2b725b988ed85dac8dce3d89d0012`), with all six source
blobs verified. The [full local acceptance workflow](https://github.com/fraware/lean-project-evidence/actions/runs/38464729618)
passed 2,971 standard tests, 76 focused tests, and whole-project type checking.
The [independent macOS workflow](https://github.com/fraware/lean-project-evidence/actions/runs/38471306908)
passed the upstream three-node interoperability scenario, lint, and typing.

## Proposed maintainer decision

1. Preserve PR #1204's core principle: commit a reservation before a one-time signing operation.
2. Decide whether to add an atomic, monotone SQLite admission operation to support more
   than a single sequential writer. The parent PR explicitly assumes a single writer,
   so our independent-connection tests justify **optional hardening**, not a claim
   of an exploit in the supported deployment.
3. Decide how the node classifies memory-only or weakly synchronized local storage
   and whether a production validator without reliable persistent state must
   refuse signing. The current candidate reports unsupported configurations
   more accurately but does not change production signing policy.
4. Explicitly define signer-key identity: current signing records distinguish
   validator indices and roles, and the inspected registry does not enforce
   global uniqueness of all loaded public keys.
5. Document recovery: replaying a historical database snapshot cannot establish
   the high-water mark of previously signed slots.
6. Keep validation and key-readiness improvements in a distinct patch unless
   maintainers prefer a unified change.

## Publication strategy

Do not create a competing replacement of upstream PR #1204. Its current merge
state is `dirty` and its author is `adust09`. The narrowest first upstream
message is a technical clarification with the atomic-storage and persistence
evidence and a question about intended integration scope. Publication has
not been confirmed: this file is a local reviewer decision record, not a
posted GitHub comment.

Suggested engineering split:
- Part A: conditional SQLite reservation and narrowly scoped tests atop #1204.
- Part B: persistence configuration accuracy, crash/backups limitations, and
  production policy as agreed with maintainers.
- Part C: validator preconditions, separately based against main.

Upstream adoption is a **separate acceptance gate** from local CI success.
