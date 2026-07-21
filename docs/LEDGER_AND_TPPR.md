# Utility ledger and TPPR

## Utility ledger

### Purpose

Create a trustworthy record of how candidate artifacts become accepted and sustained project progress.

### Storage

SQLite event store plus content-addressed artifact directory.

### Guarantees

- append-only database table;
- update and delete triggers deny mutation;
- each event contains the prior event hash for the artifact stream;
- canonical JSON serialization;
- complete verification command;
- export to newline-delimited JSON.

### Event ordering

Events are ordered by database sequence and event timestamp.

Late events are allowed and preserve their original occurrence time.

### Correction policy

Incorrect events are never edited. A compensating `CORRECTION_RECORDED` event references the original event.

### Retention / compaction (prototype)

The live SQLite file is **never** rewritten, truncated, or compacted in place. Retention is **export then optional new ledger**:

1. `lpe ledger verify <live.sqlite3>` — confirm the working chain.
2. `lpe ledger archive <live.sqlite3> --output <dir/events.jsonl>` — verify → export → verify JSONL; live DB unchanged.
3. Optionally `lpe ledger init <fresh.sqlite3>` for a smaller working set; keep the verified JSONL as the offline audit artifact.

Compensating `CORRECTION_RECORDED` events remain the only in-chain way to retract meaning. Soft-delete by DELETE is rejected by triggers and is not a supported policy.

### External seal (snapshot attestation)

After a successful verify, operators may write a seal manifest:

```text
lpe ledger seal <live.sqlite3>
lpe ledger verify-seal <live.sqlite3>
```

Default path: `<ledger_dir>/.lpe/ledger.seal.json`. Prefer `lpe ledger seal --seal <path>` to write outside the ledger directory and `lpe ledger verify-seal --seal <path>` to verify from that copy. The seal records tip hashes, event count, export content hash, timestamp, and tool version. Optional HMAC when `LPE_LEDGER_SEAL_KEY` is set. This detects silent SQLite mutation only if the seal is stored separately or read-only; it is **not** hardware WORM and does not rewrite the append-only chain.

## Ledger threat model

**Scope:** host-filesystem SQLite utility ledger vs offline export verification and external seal snapshots.  
**Not in scope:** WORM appliances, remote consensus, or hardware-backed timestamping services.

Companion: [`SECURITY_AND_PRIVACY.md`](SECURITY_AND_PRIVACY.md).

### Assets

| Asset | Why it matters |
| --- | --- |
| Live SQLite ledger | Working set for TPPR, review history, pilot warehouse |
| Verified JSONL export | Offline audit artifact; portable hash-chain evidence |
| External seal manifest | Snapshot attestation of tips / count / export hash; useful only if stored separately or read-only |
| Host FS / OS credentials | Whoever can replace files owns the “live” story |

### Guarantees (what LPE actually provides)

- **Application append-only:** SQLite triggers refuse `UPDATE`/`DELETE` on `events` through the LPE connection path.
- **Per-artifact hash chain:** each row binds `previous_hash` → `event_hash`; `lpe ledger verify` and `verify_exported_jsonl` recompute it.
- **Export verify without SQLite:** a verified JSONL stands alone as an integrity check of that snapshot.
- **External seal snapshot:** `lpe ledger seal` (after verify) writes tip hashes, event count, export content hash, timestamp, and tool version; `lpe ledger verify-seal` fails closed on mismatch. Optional HMAC via `LPE_LEDGER_SEAL_KEY`.

### Non-guarantees (residual risk)

- **Not WORM / not hardware root of trust:** a host adversary can replace the `.sqlite3` file, drop triggers outside LPE, or rewrite bytes on disk.
- **Verify ≠ provenance of the host:** a valid chain means “internally consistent,” not “untouched by someone with root.”
- **Seal ≠ WORM:** if the seal sits writable next to the DB, an adversary who rewrites both can forge a matching seal (especially content-hash-only custody). Detection requires a **separately stored or read-only** seal (and a secret key when using HMAC).
- **Fresh ledger after archive** does not migrate history into the new DB; history lives in the JSONL (by design).

### Tabletop scenarios

| # | Adversary / fault | Detection | Residual outcome |
| --- | --- | --- | --- |
| T1 | Honest operator; bit-rot in SQLite | `lpe ledger verify` fails | Restore from last **verified** JSONL; do not “repair” rows in place |
| T2 | Malicious edit via SQL after dropping triggers | Live `verify` fails if hashes not recomputed carefully; forged recompute can pass **live** verify | Only offline copies taken **before** compromise remain trustworthy; compare to external archive **and** a separately stored seal |
| T3 | Whole-file swap of `ledger.sqlite3` with attacker-built chain | Live verify may succeed on the planted DB; `verify-seal` fails if seal was not rewritten | Treat host as compromised if seal was co-writable; rely on externally stored seal + verified JSONL |
| T4 | Tamper JSONL (`event_hash` / `previous_hash`) | `verify_exported_jsonl` / `lpe ledger archive` fails | Reject archive; re-export from known-good live ledger if still trusted |
| T5 | Retention: archive then open fresh ledger | N/A (procedure) | Live working set shrinks; audit trail is the JSONL — never DELETE live events “to compact” |
| T6 | Append after seal without resealing | `lpe ledger verify-seal` fails (count / tips / export hash) | Expected: reseal after legitimate growth; keep prior seals offline if needed |

### Operator checklist

1. Store verified JSONL **and** seal manifests **off-host** (or in access-controlled / read-only storage) when the ledger backs pilot/review claims.
2. Prefer `LPE_LEDGER_SEAL_KEY` for HMAC seals when operators can keep the key out of the ledger host; without it, custody is content-hash-only.
3. After any integrity failure, supersede downstream evidence packets (see incident rule in [`SECURITY_AND_PRIVACY.md`](SECURITY_AND_PRIVACY.md)).
4. Do not treat a green `verify` on a host you no longer trust as historical proof.
5. `lpe doctor --ledger` warns when no seal exists, when a seal is **co-located** with the ledger directory, and when the ledger looks world-writable (POSIX). Prefer `lpe ledger seal --seal <off-host-path>` and verify from that path.

### Explicitly deferred

- Hardware WORM / transparency log integration
- Signed export manifests (cosign / Sigstore)
- Multi-writer Byzantine agreement

## TPPR measurement

### Credit

An obligation contributes only when:

- its weight was registered before candidate generation;
- semantic fidelity was accepted;
- repository acceptance occurred;
- declared downstream use was enabled;
- persistence was confirmed.

### Hours

Record separately:

- specification;
- review;
- repair;
- integration.

### Report

Every report includes:

- weighted numerator;
- each hour category;
- TPPR;
- compute cost;
- wall-clock latency;
- unresolved persistence obligations;
- exclusions and corrections.

### Gaming controls

- no retrospective obligation creation;
- no duplicate credit for task splitting;
- no credit for unrelated easy theorems;
- no sustained credit before the follow-up condition;
- rejected and abandoned candidates remain visible.
