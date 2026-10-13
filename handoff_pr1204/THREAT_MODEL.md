# Threat and recovery model for stateful XMSS slot reservation

## Asset and invariant

An XMSS one-time signing position indexed by slot must not be consumed for distinct messages using the same underlying cryptographic signing key. The reservation protocol models a durable per-key high-water mark, which refuses the same slot and any earlier slot following a committed claim.

This is intentionally stronger than counting successful publications: a signing operation might consume a one-time key before downstream proof construction or publication completes.

## Execution cases

| Case | What can go wrong? | Present evidence | Required boundary |
| --- | --- | --- | --- |
| Sequential repeated signing in one process | The same one-time slot is reused. | Existing signing-protection unit tests plus strict native CI. | A shared, monotone reservation record; reserve before sign. |
| Process crash and ordinary restart using unchanged committed database | The node forgets a previous reservation. | Native reopen/restart tests passed; abstract Lean restart theorem. | Committed SQLite contents must survive the restart. |
| Two writers sharing **one SQLite file** and the same logical key | Two reads may both see `None`, or a delayed lower-slot write may replace a higher slot. | Reproduced with the pending PR's method under an injected schedule. Atomic UPSERT candidate and native two-handle tests passed. | Make admission conditional inside the atomic database update; commit before signing. |
| Two processes each with an independent database file | Both record the same signing slot independently. | Not tested as a vulnerability in deployed leanSpec; the condition follows from unshared storage. | Exclusive signing-key custody or an authoritative shared reservation service. |
| Restoring an old database backup or filesystem image | Reservations committed since the backup disappear. | Not verified. | Rollback-resistant custody, an external monotone authority, or explicit operational prohibition. |
| Sudden power loss and storage failure | A claimed transaction reported committed may not persist as assumed. | Not verified. | SQLite journaling, synchronous mode and filesystem/device durability contract must be inspected and tested. |
| One master secret bound to multiple logical validator/role records | Each logical record separately permits signing the same position. | Abstract Lean countermodel and SQLite alias-model test; no claim default keys alias. | Canonical non-secret key identifier or enforced one-to-one mapping. |
| Database corruption or disk-full failures | The claimed position is not durably recorded. | Not exhaustively tested. | Fail closed if the write or commit fails; do not sign. |

## Scope of the atomic correction

The patch is deliberately minimal and stacked on upstream PR #1204. It replaces the admission precheck and unconditional `INSERT OR REPLACE` with a conditional SQL UPSERT returning a success indicator, committing before signing. It also deletes the unrestricted writer from the database API to reduce accidental bypasses.

The PR documents single-writer, exclusive-key assumptions. The corrected implementation strengthens behavior for a shared SQLite database with concurrent handles. It does **not** establish cross-host coordination or protection from database rollback; those are separate execution contracts.

## Cryptographic and formal boundaries

The accompanying Lean proofs characterize an abstract transition system and rely on an atomic persisted ledger. They do not prove that the Python/SQLite code implements the transition, that a cryptographic secret has a unique persistent identity, or that the XMSS signer itself meets the cryptographic specification.

The [bounded conformance exercise](https://github.com/fraware/lean-project-evidence/tree/research/ethereum-xmss-pr1204-conformance-20261013) is an implementation-level test, not a machine-checked refinement. Record its CI result only once observed.

## Maintainer decision

Before broadening the patch, establish whether the supported deployment contract strictly excludes multiple signing processes sharing a key. Under that assumption, the atomic UPSERT is defense-in-depth; outside that assumption, a global key-custody/reservation architecture is necessary.
