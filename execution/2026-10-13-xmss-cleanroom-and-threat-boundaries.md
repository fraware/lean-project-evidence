# XMSS clean-room acceptance and boundary audit

**Evidence date:** 2026-10-13  
**Upstream pinned parent:** `leanEthereum/leanSpec` [PR #1204](https://github.com/leanEthereum/leanSpec/pull/1204) @ `e8f9c29da3c2b725b988ed85dac8dce3d89d0012`  
**Candidate pinned:** `fraware/lean-project-evidence@79b27bba5154298de32681dcadcc8ec8628de54b`  
**Independent CI:** [run #38471306908](https://github.com/fraware/lean-project-evidence/actions/runs/38471306908), job `cleanroom-interop`, successful.  
**Previous acceptance:** [run #38464729618](https://github.com/fraware/lean-project-evidence/actions/runs/38464729618), full suite 2,971 passed, focused 76 passed, measured 91.79% branch coverage.

## A1 — Pinned independent reconstruction (complete)

A clean macOS GitHub Actions runner fetched upstream PR #1204 at exactly the pinned SHA, reconstructed the six-file overlay **through the original reviewer handoff script**, computed Git blob identities independently using `git hash-object`, checked `git diff --check`, and generated a complete patch with **384 added lines and 92 removed lines**. Each expected/observed blob identity matched:

| Target in leanSpec | Git blob SHA |
|---|---|
| `src/lean_spec/node/storage/database.py` | `355dfbb5bd2bd50b1b9d24c67a417b04b4363af0` |
| `src/lean_spec/node/storage/sqlite.py` | `6cc850de693b88a26cff7756585f0dcc916add4b` |
| `src/lean_spec/node/validator/signing_protection.py` | `80ad929a583f6e0f88b3be2a9a8935922d951090` |
| `tests/node/validator/test_signing_protection.py` | `501379d3712b9104dd8f2dfc06b07b3f4d337702` |
| `src/lean_spec/node/validator/service.py` | `fae6296e8afb2c020a0535d7a6b68370f7240fd0` |
| `tests/node/validator/test_service.py` | `3dcb21d63b33b449b035ab5193bf06f842808c35` |

The wrapper that discovers the temporary review checkout had two earlier non-substantive failures on macOS. In both, the actual reconstruction verified all six hashes, then the wrapper's temporary-directory lookup exited before testing. The successful revision passes the complete gate, so the failed historical attempts are not counted as acceptance.

## A2 — Upstream excluded interoperability suite (complete, narrow scope)

The upstream `pyproject.toml` explicitly excludes `tests/interop` from its normal pytest tree. The separate macOS Python 3.14 job ran the upstream interoperability invocation with `LEAN_ENV=test`, no coverage, `--timeout=120`, and `--log-cli-level=INFO`.

Result: **1 passed in 37.39 seconds**, `test_consensus_lifecycle`:

1. Three-node QUIC peer connectivity formed.
2. Blocks propagated, parent chains preserved ordering, proposer assignment checked.
3. All nodes processed attestations.
4. Chain grew through at least slot 3; attestation-bearing blocks observed and checkpoint monotonicity checked.

This test **does not cover** sustained consensus finalization, hardware power-loss durability, copied signing secrets, or independently cloned SQLite files. It is one scenario rather than a full network/security model.

The same job checked Ruff lint, exact Ruff formatting, and whole-project `ty` on the reconstructed checkout. All passed.

## A3 — Source-grounded outstanding threat boundaries

| Scenario | What source currently establishes | Missing decision / experimental check |
|---|---|---|
| Multiple writers sharing **one SQLite file** | Conditional monotone UPSERT; focused tests for competing connections to one path and nonregressing high-water record | Document supported concurrency/process sharing model, SQLite filesystem/locking prerequisites, and signed-key custody. No proof of a distributed atomic ledger. |
| Same secret material registered under **different validator indices** | `SigningProtection` uses `(validator_index, key_role)` to identify a record. `ValidatorRegistry.add` replaces an entry at a given index and `ValidatorRegistry.from_yaml` checks proposal-versus-attestation key inequality **within** each validator; no global uniqueness enforcement is apparent in the inspected implementation | Decide whether to reject duplicate cryptographic identities across roles **and validators** at key load, with a regression check. Index-based reservations cannot by themselves detect shared underlying secrets. Do not claim observed exploitation. |
| Same key copied to another machine/database | Local database state and in-memory state are independent | Key custody and anti-copy restrictions are explicitly operational; multi-host replay needs a shared coordinator or key exclusivity. |
| Restore an old DB snapshot | Controlled test demonstrates a previously committed slot can be re-admitted after restoring the old file | Decide on trusted anti-rollback source (or prohibit restoring signing databases). SQLite journal configuration is insufficient. |
| `:memory:`/unsafe SQLite journaling | Latest candidate reports `is_durable=False` for memory-only or unsupported settings; focus tests confirm the classification | Decide whether production validator signing must **fail closed**; the current candidate logs a warning, preserving dev/test signing behavior. |
| Unexpected process crash after reservation commit but before signing | Persisted monotone slot forfeits the duty on restart, preserving the no-reuse model under its environmental assumptions | Fault-injection at actual sign/commit boundaries and separately justified OS/filesystem behavior; ordinary test-process restart is not power-loss testing. |
| Desynchronizing service clock or cross-slot retry | Tests reject nonincreasing slots, and service preconditions align signing with the current slot | Review clock-inversion window and the consistency of service-level errors with source-level reservations in actual duty execution. |
| Consensus interoperability | Four-phase three-node test above completed | Distinct liveness/finality and long-run test campaigns remain outside the claimed acceptance. |

**Risk characterization:** These observations concern assumptions and unsupported deployment modes, not a verified exploit in a documented production configuration. The upstream parent PR itself states exclusive key ownership and single-writer assumptions.

## Prioritized follow-up

**P0:** Present the minimal atomic signing reservation and persistence classification to the owner of upstream PR #1204. Explicitly request scope decisions on global key identity, production fail-closed behavior, and backup recovery.

**P0:** Keep interop and exact full test success linked to the **pinned candidate**. Any modified/rebased candidate requires fresh CI; these hashes will no longer match.

**P1:** Add tests for accidental duplicate secrets across independent registry entries if upstream author confirms that key-loading code should enforce the assumption. Avoid inventing a rejection policy without reviewer guidance.

**P1:** Model crash/recovery transitions as a formal separate obligation, with documented hardware and filesystem assumptions; never generalize the successful snapshot test into anti-rollback protection.

## Status vocabulary

- A1: **checked** (reconstruction is independently reproducible).
- A2: **checked for the single declared multi-node interop scenario**, not a system-wide result.
- A3: **audited, unresolved policy and operational assumptions**.
- A4–A7: **not accepted upstream** at the time of this record.
