# Composed XMSS signing correction — exact patch

Pinned base: `leanEthereum/leanSpec@e8f9c29da3c2b725b988ed85dac8dce3d89d0012` (open PR #1204 head).

This combines a database-backed **atomic monotonic signing reservation** with the independently tested **XMSS validator pre-signing checks and bounded preparation**. The claim is recorded only once preparation has succeeded and before requesting any one-time signature. The block store is restored only on a known pre-signature refusal. The candidate includes the original PR tests, three reservation-concurrency regressions, and three validator preflight regressions.

## Claims and limits

The combined candidate is **not** a proof of crash durability, multicopy storage consistency, key identity across aliases, or security under two independent SQLite files. The current data key is the logical validator index and role. In-process in-memory fallback remains single-owner only.

The [atomic-only candidate](https://github.com/fraware/lean-project-evidence/actions/runs/38319468627) previously passed Ruff, ty, 69 focused tests and 2,964 full-suite tests. The [pre-signing-only candidate](https://github.com/fraware/lean-project-evidence/actions/runs/38311670261) passed its own full suite and interop. **Those separate results do not validate the composition**. Refer to the latest [combined CI workflow](https://github.com/fraware/lean-project-evidence/actions/workflows/ethereum-xmss-pr1204-composed.yml) for its independently executed outcome.

## Pinned file identities

- `src/lean_spec/node/storage/database.py` — `3023a3aed674fba16e46bda5722a691081c0d20a` → `355dfbb5bd2bd50b1b9d24c67a417b04b4363af0`; +3/-3 lines, 1 hunks
- `src/lean_spec/node/storage/sqlite.py` — `0df19c168bc23751e235f1eef4d56f9b9242933a` → `660c3dfff3fbc7ad384929831dfd5761812cd773`; +17/-6 lines, 1 hunks
- `src/lean_spec/node/validator/signing_protection.py` — `218c66c035949a1b59f834245273acfa4e46d638` → `5d7baef324dde273cc8b67ddfba6b6a0c6000236`; +16/-12 lines, 1 hunks
- `tests/node/validator/test_signing_protection.py` — `c31631acd1b9db5bf16dfc5bf15cf03c78eb62d2` → `063c055588bdb2818ce73e4af1f0d766dd94d350`; +53/-0 lines, 3 hunks
- `src/lean_spec/node/validator/service.py` — `3cbaaa6c66b4a2a7461931a76939d24344e7aa46` → `9851994dc3bde0b4fb48c6d68d3a7b075b40960e`; +122/-58 lines, 9 hunks
- `tests/node/validator/test_service.py` — `6eb3cd197275d390c4c0dc4e55e0429521604140` → `2d83eaa71529bafda6e914e9c8c66b81e98d3870`; +69/-0 lines, 3 hunks

Do not submit this patch against unmodified upstream main. It is stacked on PR #1204.

## Publish a stacked review PR

PR #1204's contributor branch is `adust09/leanSpec:feat/durable-signing-protection` at the pinned SHA. The preferred next contribution is a **stacked PR to that exact feature branch**, then a link from the upstream PR #1204 conversation. It avoids duplicating the entire unmerged feature against upstream main.

The connected GitHub integration cannot create forks or write upstream PR comments. An account-authenticated local helper is available. It checks the `fraware` login, the live author-branch commit, the fork parent, the exact patch and all six output Git blobs, then pushes a separate branch and requests review.

```bash
curl -fsSLo publish_stacked_pr.sh \
  https://raw.githubusercontent.com/fraware/lean-project-evidence/4290f283374f4fdd7d20ebaa9b0951cebd41a299/handoff_composed/publish_stacked_pr.sh
bash -n publish_stacked_pr.sh
bash publish_stacked_pr.sh
```

The script needs `gh`, `git`, `curl`, GitHub authentication as `fraware`, and locally configured Git commit identity. Inspect [publish_stacked_pr.sh](./publish_stacked_pr.sh) and [PR_BODY_STACKED.md](./PR_BODY_STACKED.md) before execution. It makes public GitHub changes, refuses stale revisions or overwrite of the target fork branch, and retains its working directory. It does not automatically merge or alter the upstream contributor's branch.

[Composed native CI, 72 focused and 2,967 standard tests](https://github.com/fraware/lean-project-evidence/actions/runs/38340641997) · [Patch and publication-helper witness](https://github.com/fraware/lean-project-evidence/actions/runs/38377803843).

