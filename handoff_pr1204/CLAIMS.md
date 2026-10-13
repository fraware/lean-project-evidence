# XMSS atomic signing reservation: claim–evidence register

Baseline: leanEthereum/leanSpec PR #1204 at `e8f9c29da3c2b725b988ed85dac8dce3d89d0012` (not merged). The production patch is stacked on this exact source and changes four files.

| ID | Claim | Evidence | Boundary / status |
| --- | --- | --- | --- |
| C1 | The pending PR's separate precheck and `INSERT OR REPLACE` admit two reservations for the same validator-role-slot under a forced two-connection shared-file schedule. | [2 actual-method tests](https://github.com/fraware/lean-project-evidence/actions/runs/38317231036) executing the unmodified `SigningProtection.reserve` against instrumented SQLite adapter; [7 direct SQLite schedule tests](https://github.com/fraware/lean-project-evidence/actions/runs/38317050285). | **Reproduced under an unsupported multi-writer schedule.** No claim of exploitation in the documented single-writer environment. |
| C2 | A later stale unconditional replacement can decrease the recorded high-water mark. | Same unmodified method reproduction, slot 8 then slot 5. | Same deployment scope as C1. |
| C3 | The corrected implementation admits only an increased slot for a logical validator-role identity using one conditional SQLite write. | [Strict native CI](https://github.com/fraware/lean-project-evidence/actions/runs/38319468627): 69 focused tests and 2,964 full-suite tests; independent [exact four-file patch witness](https://github.com/fraware/lean-project-evidence/actions/runs/38319568933). | **Test-supported**, not universally proved; assumes shared SQLite storage and the configured logical identity. |
| C4 | The corrected reservation decision survives an ordinary database connection close/reopen and rejects the already committed slot. | Native PR signing-protection restart tests, passed in C3 run. | No machine power-loss or filesystem durability proof. |
| C5 | In an abstract, atomically committed, high-water ledger, a committed slot cannot be reserved again or earlier. | [Lean 4 model](https://github.com/fraware/lean-project-evidence/blob/research/ethereum-xmss-reservations-20261012/experiments/ethereum-xmss/XmssReservation.lean), kernel-checked in [CI](https://github.com/fraware/lean-project-evidence/actions/runs/38317050285). | **Machine-checked for the abstract model only**; atomic persistence is an assumption, not a verified property of SQLite/Python. |
| C6 | If two *logical* IDs refer to one XMSS signing secret, role-scoped records permit reservation under both IDs. | Lean distinct-ID countermodel and direct SQLite logical alias test in C5 run. | **Conditional configuration hazard**; no evidence that default leanSpec key generation duplicates secrets. |
| C7 | The Python/SQLite implementation refines the Lean ledger for all relevant histories. | [Bounded model-based trace harness](https://github.com/fraware/lean-project-evidence/tree/research/ethereum-xmss-pr1204-conformance-20261013/candidate_pr1204). | **Not formally established.** CI conformance result must be checked separately; passing bounded traces never proves unbounded equivalence. |
| C8 | This work has been reviewed, accepted, merged, or deployed by leanEthereum maintainers. | None. | **Unestablished.** Connected upstream write/review attempts returned HTTP 403. |

## Exact reproducibility

- [Source-pinned four-file patch](./pr1204-atomic-reservation.patch) and [application instructions](./README.md)
- [Native CI run #38319468627](https://github.com/fraware/lean-project-evidence/actions/runs/38319468627) with Ruff, ty, 69 focused tests, 2,964 repository-wide tests, 92% reported coverage
- [Exact Git blob patch witness #38319568933](https://github.com/fraware/lean-project-evidence/actions/runs/38319568933)
- [Proposed upstream reviewer note](./REVIEW_NOTE.md) with explicit single-writer caveat

The model uses one high-water mark for each signing-key identity. The current concrete patch stores logical `(validator_index, role)` identities. Any claim that those domains agree needs an explicit no-alias assumption or a verified canonical key-identity mechanism.

## Remaining proof and engineering obligations

1. Define the operational identity of an XMSS signing key and establish whether validator/role uniqueness is enforced.
2. Verify the commit-before-sign ordering at all relevant signing call sites, including failure paths.
3. Specify permissible crash and restart states, database replacement and backup rollback behavior.
4. If multi-host signing is in scope, introduce a single authoritative reservation service or enforce exclusive key custody.
5. Prove or systematically refine the abstract reservation transition against the concrete implementation.
6. Obtain maintainer review and upstream CI on a submitted change.
