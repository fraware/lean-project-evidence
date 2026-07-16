# Utility Ledger specification

## Purpose

Create a trustworthy record of how candidate artifacts become accepted and sustained project progress.

## Storage

SQLite event store plus content-addressed artifact directory.

## Guarantees

- append-only database table;
- update and delete triggers deny mutation;
- each event contains the prior event hash for the artifact stream;
- canonical JSON serialization;
- complete verification command;
- export to newline-delimited JSON.

## Event ordering

Events are ordered by database sequence and event timestamp.

Late events are allowed and preserve their original occurrence time.

## Correction policy

Incorrect events are never edited. A compensating `CORRECTION_RECORDED` event references the original event.

## Retention / compaction (prototype)

The live SQLite file is **never** rewritten, truncated, or compacted in place. Retention is **export then optional new ledger**:

1. `lpe ledger verify <live.sqlite3>` — confirm the working chain.
2. `lpe ledger archive <live.sqlite3> --output <dir/events.jsonl>` — verify → export → verify JSONL; live DB unchanged.
3. Optionally `lpe ledger init <fresh.sqlite3>` for a smaller working set; keep the verified JSONL as the offline audit artifact.

Compensating `CORRECTION_RECORDED` events remain the only in-chain way to retract meaning. Soft-delete by DELETE is rejected by triggers and is not a supported policy.

Threat-model residual risk (compromised host FS vs export verify): [25_LEDGER_THREAT_MODEL.md](25_LEDGER_THREAT_MODEL.md).
