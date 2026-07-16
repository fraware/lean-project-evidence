from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from lpe.hashing import canonical_json, sha256_text
from lpe.models import EventType, UtilityEvent

# Reject empty / placeholder identities on append (AUDIT-017).
_ANONYMOUS_ACTOR_RE = re.compile(
    r"^(anonymous|anon|unknown|none|null|n/?a|-)$",
    re.IGNORECASE,
)


class LedgerAuthError(ValueError):
    """Raised when ledger append lacks a usable actor or project binding."""


def validate_ledger_actor(actor_id: str) -> str:
    cleaned = actor_id.strip() if isinstance(actor_id, str) else ""
    if not cleaned or _ANONYMOUS_ACTOR_RE.match(cleaned):
        raise LedgerAuthError(
            "ledger append rejects anonymous/empty actor_id; "
            "provide a real reviewer or system identity"
        )
    return cleaned


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    project_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    obligation_id TEXT,
    occurred_at TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    supersedes_event_id TEXT,
    previous_hash TEXT,
    event_hash TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id, sequence);
CREATE INDEX IF NOT EXISTS idx_events_artifact ON events(artifact_id, sequence);
CREATE INDEX IF NOT EXISTS idx_events_obligation ON events(obligation_id, sequence);

CREATE TRIGGER IF NOT EXISTS deny_events_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS deny_events_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;
"""

# Applied on every connection (WAL persists in the DB file; busy/sync are per-connection).
_CONNECTION_PRAGMAS = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
"""


class LedgerIntegrityError(RuntimeError):
    pass


class LedgerStore:
    def __init__(self, path: Path):
        self.path = path
        # Skip re-running SCHEMA on every append/verify once this process has
        # initialized this path (clear win for append throughput; no security change).
        self._initialized = False

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.executescript(_CONNECTION_PRAGMAS)
        return connection

    def initialize(self) -> None:
        if self._initialized and self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            mode = connection.execute("PRAGMA journal_mode").fetchone()
            if mode is None or str(mode[0]).lower() != "wal":
                raise LedgerIntegrityError(
                    f"ledger refused to enable WAL journal_mode (got {mode!r})"
                )
        self._initialized = True

    def journal_mode(self) -> str:
        """Return the active SQLite journal mode (expected: ``wal``)."""
        self.initialize()
        with self.connect() as connection:
            row = connection.execute("PRAGMA journal_mode").fetchone()
        return str(row[0]).lower() if row else ""

    def checkpoint(self, *, truncate: bool = False) -> None:
        """Flush WAL into the main DB file (clean shutdown / backup prep)."""
        self.initialize()
        mode = "TRUNCATE" if truncate else "PASSIVE"
        with self.connect() as connection:
            connection.execute(f"PRAGMA wal_checkpoint({mode})")

    def _previous_hash(self, connection: sqlite3.Connection, artifact_id: str) -> str | None:
        row = connection.execute(
            """
            SELECT event_hash
            FROM events
            WHERE artifact_id = ?
            ORDER BY sequence DESC
            LIMIT 1
            """,
            (artifact_id,),
        ).fetchone()
        return str(row["event_hash"]) if row else None

    @staticmethod
    def _hash_material(event: UtilityEvent, previous_hash: str | None) -> str:
        material = {
            "event": event.model_dump(mode="json"),
            "previous_hash": previous_hash,
        }
        return sha256_text(canonical_json(material))

    def append(self, event: UtilityEvent) -> str:
        validate_ledger_actor(event.actor_id)
        self.initialize()
        with self.connect() as connection:
            # BEGIN IMMEDIATE serializes writers so previous_hash reads are not racy.
            connection.execute("BEGIN IMMEDIATE")
            previous_hash = self._previous_hash(connection, event.artifact_id)
            event_hash = self._hash_material(event, previous_hash)
            try:
                connection.execute(
                    """
                    INSERT INTO events (
                        event_id, event_type, project_id, artifact_id, obligation_id,
                        occurred_at, actor_id, payload_json, supersedes_event_id,
                        previous_hash, event_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.event_type.value,
                        event.project_id,
                        event.artifact_id,
                        event.obligation_id,
                        event.occurred_at.isoformat(),
                        event.actor_id,
                        canonical_json(event.payload),
                        event.supersedes_event_id,
                        previous_hash,
                        event_hash,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                connection.execute("ROLLBACK")
                raise LedgerIntegrityError(
                    f"failed to append event {event.event_id}: duplicate or invalid insert"
                ) from exc
            connection.execute("COMMIT")
            return event_hash

    def append_correction(
        self,
        *,
        event_id: str,
        project_id: str,
        artifact_id: str,
        actor_id: str,
        supersedes_event_id: str,
        reason: str,
        obligation_id: str | None = None,
        payload: dict | None = None,
    ) -> str:
        correction_payload = {"reason": reason, **(payload or {})}
        event = UtilityEvent(
            event_id=event_id,
            event_type=EventType.CORRECTION_RECORDED,
            project_id=project_id,
            artifact_id=artifact_id,
            obligation_id=obligation_id,
            actor_id=actor_id,
            payload=correction_payload,
            supersedes_event_id=supersedes_event_id,
        )
        return self.append(event)

    def events(self, project_id: str | None = None) -> list[UtilityEvent]:
        self.initialize()
        query = "SELECT * FROM events"
        parameters: tuple[str, ...] = ()
        if project_id is not None:
            query += " WHERE project_id = ?"
            parameters = (project_id,)
        query += " ORDER BY sequence"
        with self.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> UtilityEvent:
        return UtilityEvent(
            event_id=row["event_id"],
            event_type=row["event_type"],
            project_id=row["project_id"],
            artifact_id=row["artifact_id"],
            obligation_id=row["obligation_id"],
            occurred_at=row["occurred_at"],
            actor_id=row["actor_id"],
            payload=json.loads(row["payload_json"]),
            supersedes_event_id=row["supersedes_event_id"],
        )

    def verify(self) -> None:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events ORDER BY artifact_id, sequence"
            ).fetchall()
        previous_by_artifact: dict[str, str | None] = {}
        known_event_ids = {str(row["event_id"]) for row in rows}
        for row in rows:
            artifact_id = str(row["artifact_id"])
            expected_previous = previous_by_artifact.get(artifact_id)
            event = self._row_to_event(row)
            expected_hash = self._hash_material(event, expected_previous)
            if row["event_hash"] != expected_hash:
                raise LedgerIntegrityError(f"invalid event_hash for {row['event_id']}")
            if row["previous_hash"] != expected_previous:
                raise LedgerIntegrityError(
                    f"broken previous_hash for event {row['event_id']}"
                )
            if event.supersedes_event_id is not None:
                if event.supersedes_event_id not in known_event_ids:
                    raise LedgerIntegrityError(
                        f"event {event.event_id} supersedes unknown event "
                        f"{event.supersedes_event_id}"
                    )
            previous_by_artifact[artifact_id] = expected_hash

    def _row_to_export_record(self, row: sqlite3.Row) -> dict[str, Any]:
        event = self._row_to_event(row)
        return {
            "event": json.loads(event.model_dump_json()),
            "previous_hash": row["previous_hash"],
            "event_hash": row["event_hash"],
        }

    def export_records(self) -> list[dict[str, Any]]:
        """Export events with ``previous_hash`` / ``event_hash`` for offline verify."""
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events ORDER BY sequence"
            ).fetchall()
        return [self._row_to_export_record(row) for row in rows]

    def export_jsonl(self, output: Path) -> int:
        """Write verifiable JSONL: each line has event + previous_hash + event_hash.

        Streams rows from SQLite so large ledgers (10k+) do not materialize the
        full export list in memory before writing.
        """
        self.initialize()
        output.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with self.connect() as connection, output.open("w", encoding="utf-8") as handle:
            cursor = connection.execute("SELECT * FROM events ORDER BY sequence")
            for row in cursor:
                record = self._row_to_export_record(row)
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                count += 1
        return count

    def archive_verified_jsonl(self, archive_path: Path) -> dict[str, Any]:
        """Retention/compaction prototype: verify → export → verify JSONL.

        Leaves the live SQLite ledger untouched (append-only invariants hold).
        Operators who want a smaller working set open a *new* ledger via
        ``lpe ledger init`` and keep the verified JSONL as the offline archive.
        Never DELETE/UPDATE events or rewrite the live chain.
        """
        if archive_path.resolve() == self.path.resolve():
            raise LedgerIntegrityError(
                "archive path must not overwrite the live ledger SQLite file"
            )
        self.verify()
        count = self.export_jsonl(archive_path)
        verified = self.verify_exported_jsonl(archive_path)
        if verified != count:
            raise LedgerIntegrityError(
                f"archive verify count mismatch: exported {count}, verified {verified}"
            )
        return {
            "events": count,
            "archive": str(archive_path),
            "live_ledger": str(self.path),
            "live_unchanged": True,
            "fresh_ledger_hint": (
                "lpe ledger init <new-path.sqlite3>  # start empty working set; "
                "keep verified JSONL as audit artifact"
            ),
        }

    @classmethod
    def verify_exported_jsonl(cls, path: Path) -> int:
        """Recompute hash chain from an export produced by ``export_jsonl``.

        Returns the number of verified records. Raises ``LedgerIntegrityError``
        on mismatch. Does not require the original SQLite file. Streams the
        file line-by-line so large exports stay memory-bounded.
        """
        previous_by_artifact: dict[str, str | None] = {}
        known_event_ids: set[str] = set()
        count = 0
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                if "event" not in record or "event_hash" not in record:
                    raise LedgerIntegrityError(
                        "export line missing event/event_hash; re-export with a "
                        "ledger that includes chain digests"
                    )
                event = UtilityEvent.model_validate(record["event"])
                expected_previous = previous_by_artifact.get(event.artifact_id)
                expected_hash = cls._hash_material(event, expected_previous)
                if record.get("previous_hash") != expected_previous:
                    raise LedgerIntegrityError(
                        f"broken previous_hash in export for event {event.event_id}"
                    )
                if record["event_hash"] != expected_hash:
                    raise LedgerIntegrityError(
                        f"invalid event_hash in export for event {event.event_id}"
                    )
                if event.supersedes_event_id is not None:
                    if event.supersedes_event_id not in known_event_ids:
                        raise LedgerIntegrityError(
                            f"export event {event.event_id} supersedes unknown "
                            f"{event.supersedes_event_id}"
                        )
                previous_by_artifact[event.artifact_id] = expected_hash
                known_event_ids.add(event.event_id)
                count += 1
        return count
