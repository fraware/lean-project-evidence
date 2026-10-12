# Atomic, monotone SQLite XMSS reservation: stacked correction to leanSpec PR #1204

**Base**: `leanEthereum/leanSpec@e8f9c29da3c2b725b988ed85dac8dce3d89d0012` (exact head of upstream PR #1204 checked 12 October 2026). This is a reviewable patch **on top of PR #1204**, not a patch to current upstream main.

The correction replaces separate read/check/unconditional replacement with one conditional SQLite UPSERT and a committed success/failure return. It removes the unrestricted `put_last_signed_slot` method so the public database protocol no longer exposes a downgrade path. The existing `SigningProtectionError` duty contract and in-process fallback are retained.

The candidate includes three native regression tests: two SQLite handles claiming the same slot concurrently, refusal of a delayed lower-slot claim, and independence of two role-specific keys.

## Scope and limitations

- Safety relies on the committed shared SQLite file and a single agreed logical validator/role key identity. Two independent database files, backups rolled back to prior states, and accidental reuse of the same XMSS secret across logical identities are **outside** this patch.
- No cryptographic equivalence or end-to-end formal proof is claimed.
- Full acceptance results are tracked on the isolated branch `research/ethereum-xmss-pr1204-atomic-20261012`. Do not describe pending tests as successful.

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
