# Security review: the exact claim boundary in leanSpec PR #1204

Source reviewed: [PR #1204](https://github.com/leanEthereum/leanSpec/pull/1204), head `e8f9c29da3c2b725b988ed85dac8dce3d89d0012`. This is a research review, **not** an upstream comment or merged correction.

## Finding 1 — read / check / write is not a single atomic reservation

The pending `SigningProtection.reserve` calls `last_signed_slot` **before** opening `database.batch_write()`. The SQLite implementation inserts through an unconditional `INSERT OR REPLACE`, with primary key `(validator_index, key_role)`.

Under two independent connections accessing the same SQLite file:
1. Signer A reads `None`; signer B also reads `None`.
2. A commits a reservation for slot 5.
3. B commits a reservation for the same key and slot 5.
4. Both `reserve` calls report success. Neither caller saw a refusal.

A second interleaving reads `None` twice, commits slot 8, then commits a delayed slot 5. The final high-water mark becomes **5**, contradicting a monotonic highest-slot record.

This **does not refute the PR under its explicitly documented single-writer/exclusive-key ownership assumption**. It establishes that the design needs that assumption and cannot be presented as linearizable across concurrent nodes sharing signing material.

## Finding 2 — logical role is not necessarily cryptographic key identity

The database primary key `(validator_index, key_role)` distinguishes an attestation slot from a proposal slot. Normal operation uses independent key pairs. If the same XMSS master secret is erroneously installed under multiple validator/role identities, the schema admits a reservation under each identity for the same secret and slot. A canonical, domain-separated fingerprint of the true signing secret is needed for a key-scoped invariant. Production derivation and secret-handling details need independent cryptographic review.

## Tested countermeasures and recommended narrow change

An atomic SQLite conditional UPSERT, returning success only on `cursor.rowcount == 1`, resolves the two *single-DB concurrent-writer* schedules used in our tests:

```sql
INSERT INTO signing_records (validator_index, key_role, last_signed_slot)
VALUES (?, ?, ?)
ON CONFLICT (validator_index, key_role) DO UPDATE
SET last_signed_slot = excluded.last_signed_slot
WHERE signing_records.last_signed_slot < excluded.last_signed_slot;
```

Commit this atomic statement **before** invoking XMSS signing; on no changed row, refuse the duty. Crucially, move the admission decision into the database operation and do not implement it as a separate SELECT/check/INSERT sequence. Never use an unconditional `INSERT OR REPLACE` for the high-water mark.

For the stronger cross-role/cross-index key identity policy, design a unique `key_fingerprint` record, possibly retaining human-readable validator/role metadata as auxiliary fields. Key fingerprints must be unambiguous and not disclose secret key bytes. A real multi-node deployment also needs a shared authoritative reservation service; two independent database files cannot enforce a global invariant.

## Evidence and limitation

- [Seven stdlib SQLite adversarial tests](./test_reservation_sqlite.py), including deterministic two-connection same-slot acceptance, high-water regression, atomic UPSERT comparison, alias model, and restart. These reproduce the SQL/control-flow pattern without importing leanSpec.
- [Exact-PR Python adapter tests](./pr1204_race.py) execute the actual `SigningProtection.reserve` method from the pinned PR head. Its adapter duplicates the PR table and SQL behavior and injects barriers to force adverse schedules; it is not a test using the node's complete `SQLiteDatabase`.
- [Lean 4 reservation model](./XmssReservation.lean) proves replay exclusion, older-slot refusal, unrelated-key isolation, and recovery properties for an abstract per-key ledger. Its linearizable durable commit and stable key identity assumptions are **not established** by the proof.
- [Proof and SQLite model CI](https://github.com/fraware/lean-project-evidence/actions/runs/38316932452).
- [Exact-PR adapter CI, run #38317231036](https://github.com/fraware/lean-project-evidence/actions/runs/38317231036): **2 passed** against the actual `SigningProtection.reserve` implementation from pinned PR #1204, including same-slot concurrent double acceptance and high-water decrease. The first run (#38316932514) did not run assertions because standalone import encountered an initialization cycle; the corrected run uses upstream pytest/conftest.
- [Updated Lean reservation and SQLite-model CI](https://github.com/fraware/lean-project-evidence/actions/runs/38317050285): kernel check passed, including a distinct-logical-identity countermodel, and all seven SQLite schedule tests passed.

Beyond SQLite atomicity, storage rollback, independent replicas, database replacement, power-loss durability and corruption remain explicit deployment obligations. The tests do not claim an actual attack against a running node, and the PR remains open.

## Current finding disposition

The two schedules have now been reproduced in both an isolated SQL protocol and the pending PR's exact `SigningProtection.reserve` method (using the instrumented adapter). This is a **verified concurrency limitation**, not proof that an unsupported multi-writer deployment is currently in production. The PR's `SQLiteDatabase` documentation explicitly limits writes to a single writer on the node event-loop thread; its signing protection also says concurrent nodes sharing keys are unsupported. The model exposes what would need to change if those limitations were removed or if configuration errors must fail safely.

The smallest atomicity improvement is a conditionally updating, committed claim statement with a success indicator, replacing the separate application-level check and unconditional replacement. True cross-host key-safety additionally needs a shared authoritative ledger or exclusive signing-key custody; a better SQLite statement cannot coordinate two unrelated database files. Key identity must be defined in cryptographic terms before sharing reservation records across logical roles.

## Reviewer acceptance questions

1. Is exclusive signing-key ownership intended as a hard deployment requirement, or does the guard aim to tolerate accidentally concurrent signers?
2. Does the identity record refer to a logical validator-role pairing or the actual XMSS master secret?
3. Which rollback/recovery guarantees are claimed for database backups and replicas?
4. Can the reservation be implemented as a one-statement conditional update with a regression test against two SQLite handles?
