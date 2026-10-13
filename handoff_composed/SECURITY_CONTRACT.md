# XMSS signing contract — claim boundaries and evidence

Pinned integration baseline: `leanEthereum/leanSpec` PR #1204 commit `e8f9c29da3c2b725b988ed85dac8dce3d89d0012`.

## Security goal

For every actual XMSS signing key and signing slot, the node must request **at most one signature**, including across restarts, preparation failures, and two concurrent invocations. The implementation here enforces a narrower contract: each logical `(validator_index, key_role)` has at most one **successful committed reservation** at a given or earlier slot per *shared, non-rolled-back SQLite database*.

A successful reservation does **not** prove a signature was produced. Crashes between reservation and signing intentionally consume a duty. Database restore, split-brain, identity aliasing, and secret-key duplication remain outside the proven/tested invariant.

## Proof-to-implementation correspondence

| Obligation | Mechanism | Evidence | Limit |
| --- | --- | --- | --- |
| Strictly increasing successful claims | SQLite `ON CONFLICT … DO UPDATE … WHERE old < new` and affected-row decision | PR #1204 atomic-candidate native tests; [SQLite model](https://github.com/fraware/lean-project-evidence/actions/runs/38340936760) | Applies to one SQLite file |
| One winner for the same key/slot | Single conditional statement under SQLite write serialization | Two-handle native regression and negative control | Does not serialize independent databases |
| Claim survives a normal reopen | Commit from `batch_write` before signing; same persisted database | Native restart test | Restore of an older DB copy defeats it |
| An invalid activation slot consumes no reservation | Preparation bounds checked before `signing_protection.reserve` | Combined native regression `test_ci_inactive_key_refused_before_preparation` | Preparation is assumed not to sign |
| Local key matches registered key | Compare commitment derived from local key with state public key | Proposal and attestation mismatch regressions | Does not verify every internal secret field |
| Bad proof inputs do not cause proposal signing | Validate proof participants and public keys first | Source-exact negative controls and native validator test suite | Exceptions after a signature do not imply unspent key |
| Correct proposer identity | Separate proposer index from attestation participant indices | Earlier differential regression | Cryptographic aggregate verified only within exercised tests |
| Refusal isolation across duties | Catch typed preparation and reservation refusals | Native validator-duty tests | Unexpected errors propagate |
| Per-key monotone replay exclusion | Abstract `Ledger → Option Ledger` transition | [Lean 4 kernel checks](https://github.com/fraware/lean-project-evidence/actions/runs/38340936760) | Abstract atomic-commit and stable-key-ID assumptions |

## Counterexamples not discharged by this patch

1. **Stale backup rollback:** an old SQLite file is substituted for one containing a committed reservation. The slot is admitted again. Reproduced in the eight-test SQLite suite.
2. **Independent database files:** two nodes each hold a local reservation history. Neither sees the other's commit.
3. **Key alias:** two logical validator/role records refer to the same underlying XMSS secret. Both records can admit that slot independently. Modelled in SQLite and a Lean countermodel.
4. **In-memory mode:** reservations do not survive process restart. The service exposes an `is_durable` distinction, not a persistence guarantee.
5. **Database failure before durable commit:** the caller must not issue a signature. The current synchronous path is designed to abort on transaction errors; storage crash/power-loss guarantees need separate validation.

## Why the order matters

```text
check on-chain identity + block/attestation prerequisites
  → bound and advance key preparation (no signature)
  → atomically reserve and COMMIT the slot
  → request one XMSS signature
  → persist updated local preparation state
  → construct / publish proof
```

This order protects one-time-signature usage under the stated shared-ledger assumptions. It does not make block publication or key-state persistence transactional with signature generation. Post-signature errors must never trigger an unqualified rollback of the reservation ledger.

## Adoption

The [six-file patch](./xmss-composed.patch) is stacked on the exact open PR #1204 head. [Patch witness](https://github.com/fraware/lean-project-evidence/actions/runs/38340808450) passed exact file hashes and compilation. The [native combined CI](https://github.com/fraware/lean-project-evidence/actions/workflows/ethereum-xmss-pr1204-composed.yml) is the separate gate for the composed Python implementation. Distinguish its result from previously green atomic-only and preflight-only suites.

No upstream PR is published or merged. This is a technical contract and evidence map, not a system-level cryptographic proof.
