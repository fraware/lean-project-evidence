# Ledger threat model (tabletop)

**Scope:** host-filesystem SQLite utility ledger vs offline export verification.  
**Not in scope:** WORM appliances, remote consensus, or cryptographic timestamping services.

Companion: [09_SECURITY_AND_PRIVACY.md](09_SECURITY_AND_PRIVACY.md) (trust boundary), [06_UTILITY_LEDGER_SPEC.md](06_UTILITY_LEDGER_SPEC.md) (retention).

## Assets

| Asset | Why it matters |
| --- | --- |
| Live SQLite ledger | Working set for TPPR, review history, pilot warehouse |
| Verified JSONL export | Offline audit artifact; portable hash-chain evidence |
| Host FS / OS credentials | Whoever can replace files owns the “live” story |

## Guarantees (what LPE actually provides)

- **Application append-only:** SQLite triggers refuse `UPDATE`/`DELETE` on `events` through the LPE connection path.
- **Per-artifact hash chain:** each row binds `previous_hash` → `event_hash`; `lpe ledger verify` and `verify_exported_jsonl` recompute it.
- **Export verify without SQLite:** a verified JSONL stands alone as an integrity check of that snapshot.

## Non-guarantees (residual risk)

- **Not WORM / not root of trust:** a host adversary can replace the `.sqlite3` file, drop triggers outside LPE, or rewrite bytes on disk.
- **Verify ≠ provenance of the host:** a valid chain means “internally consistent,” not “untouched by someone with root.”
- **Fresh ledger after archive** does not migrate history into the new DB; history lives in the JSONL (by design).

## Tabletop scenarios

| # | Adversary / fault | Detection | Residual outcome |
| --- | --- | --- | --- |
| T1 | Honest operator; bit-rot in SQLite | `lpe ledger verify` fails | Restore from last **verified** JSONL; do not “repair” rows in place |
| T2 | Malicious edit via SQL after dropping triggers | Live `verify` fails if hashes not recomputed carefully; forged recompute can pass **live** verify | Only offline copies taken **before** compromise remain trustworthy; compare to external archive |
| T3 | Whole-file swap of `ledger.sqlite3` with attacker-built chain | Live verify may succeed on the planted DB | Treat host as compromised; rely on externally stored, previously verified JSONL + access controls |
| T4 | Tamper JSONL (`event_hash` / `previous_hash`) | `verify_exported_jsonl` / `lpe ledger archive` fails | Reject archive; re-export from known-good live ledger if still trusted |
| T5 | Retention: archive then open fresh ledger | N/A (procedure) | Live working set shrinks; audit trail is the JSONL — never DELETE live events “to compact” |

## Retention posture (prototype)

```text
lpe ledger verify <live.sqlite3>
lpe ledger archive <live.sqlite3> --output <archive/events.jsonl>
# optional new working set:
lpe ledger init <fresh.sqlite3>
```

`lpe ledger archive` verifies the live chain, copies a verified JSONL, and **does not** mutate the live database. Compaction = new empty ledger + retained archive, not in-place rewrite.

## Operator checklist

1. Store verified JSONL **off-host** (or in access-controlled object storage) when the ledger backs pilot/review claims.
2. After any integrity failure, supersede downstream evidence packets (see incident rule in [09_SECURITY_AND_PRIVACY.md](09_SECURITY_AND_PRIVACY.md)).
3. Do not treat a green `verify` on a host you no longer trust as historical proof.

## Explicitly deferred

- Hardware WORM / transparency log integration
- Signed export manifests (cosign / Sigstore)
- Multi-writer Byzantine agreement
