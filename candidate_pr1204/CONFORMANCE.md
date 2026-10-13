# Bounded conformance of atomic SQLite reservations to the Lean high-water model

This branch extends the source-pinned four-file correction for leanSpec PR #1204 with **eight deterministic seeded traces, 64 steps each**. The traces select validator indices, key roles and signing slots from bounded sets. Each step predicts acceptance using the monotone high-water reference rule and executes the real `SigningProtection.reserve` method against `SQLiteDatabase`.

Each accepted or rejected reservation is followed by reopening the database and checking **every known key's** persisted high-water mark against the reference model. The test exercises 512 admission attempts and repeated recovery from a fresh SQLite handle.

This is a bounded conformance test, not a formal refinement theorem. The [Lean model](https://github.com/fraware/lean-project-evidence/blob/research/ethereum-xmss-reservations-20261012/experiments/ethereum-xmss/XmssReservation.lean) proves replay exclusion for an abstract ledger under atomic, durable commit and stable key identity. The trace test maps those abstract transitions onto concrete Python/SQLite operations, and does not establish failure-free storage recovery, key-fingerprint correctness, or safety across independent databases.

The previously green [strict 2,964-test atomic-reservation candidate](https://github.com/fraware/lean-project-evidence/actions/runs/38319468627) is maintained unchanged on its own branch. A CI failure here must not be interpreted as invalidating that separate run.
