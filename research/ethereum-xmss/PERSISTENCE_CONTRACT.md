# XMSS persistence classification and backup-rollback boundary

Source baseline: `leanEthereum/leanSpec` PR #1204, exact head
`e8f9c29da3c2b725b988ed85dac8dce3d89d0012`.
Stacked on the six-file combined candidate from
`research/ethereum-xmss-composed-20261013`, whose independent CI previously
passed 73 focused and 2,968 repository-wide tests.

## Findings

1. A configured SQLite `:memory:` database is not persistent across process
   restarts. The original `SigningProtection.is_durable` implementation
   classified it as durable because it checked only `database is not None`.
2. A file-backed SQLite connection with `journal_mode=MEMORY/OFF` or
   `synchronous=NORMAL/OFF` lacks the full-sync rollback-journal contract
   assumed for local signer persistence. A file path alone is insufficient.
3. Restoring a database copy from an older point in time discards later committed
   reservations. **A local SQLite flag cannot prevent rollback.**

## Candidate change

- `SQLiteDatabase.has_persistent_signing_storage` reads SQLite's current
  `database_list`, `journal_mode`, and `synchronous` configuration.
- `SigningProtection.is_durable` conservatively accepts only a known SQLite
  connection with a file-backed main database, persistent journaling, and
  `synchronous >= FULL`; unknown database implementations report False.
- Existing signing and fallback behavior stays unchanged. An unsupported
  configuration now receives an accurate warning at validator-loop startup.
- New native tests cover `:memory:` data loss, unsafe SQLite PRAGMAs, and
  an **expected** replay of previously committed state after restoring an old
  database snapshot. The snapshot test does not sign any cryptographic keys.

## Explicit limits

The flag is a **configuration indication**, not a formal proof of SQLite
transaction refinement, storage hardware durability, filesystem semantics,
exclusive key custody, or database anti-rollback. SQLite FULL synchronization
still relies on the filesystem and device honoring sync semantics. The
existing monotone reservation rule applies only to the state that is actually
present and shared by the relevant signer instances. Independent copies of the
same key and database may each admit the same one-time slot.

This is an isolated experimental candidate. The GitHub Actions workflow
`ethereum-xmss-durability-contract-20261013.yml` validates it against the pinned
PR head; no upstream change or maintainer acceptance is asserted.
