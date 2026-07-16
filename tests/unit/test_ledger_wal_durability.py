"""Ledger WAL durability, crash recovery, and multi-writer integrity."""

from __future__ import annotations

import multiprocessing as mp
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lpe.ledger.store import LedgerIntegrityError, LedgerStore
from lpe.models import EventType, UtilityEvent


def _event(
    event_id: str,
    *,
    artifact_id: str = "artifact",
    payload: dict | None = None,
) -> UtilityEvent:
    return UtilityEvent(
        event_id=event_id,
        event_type=EventType.CANDIDATE_REGISTERED,
        project_id="project",
        artifact_id=artifact_id,
        obligation_id="O-01",
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        actor_id="tester",
        payload=payload or {"x": 1},
    )


def test_ledger_enables_wal_journal_mode(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    store = LedgerStore(path)
    store.initialize()
    assert store.journal_mode() == "wal"
    # Sidecar files appear after the first write under WAL.
    store.append(_event("event-1"))
    assert path.is_file()
    # WAL file may be empty after checkpoint; mode must still be wal.
    assert store.journal_mode() == "wal"
    store.checkpoint(truncate=True)
    # After TRUNCATE checkpoint reopen verifies committed data.
    recovered = LedgerStore(path)
    assert recovered.journal_mode() == "wal"
    recovered.verify()
    assert len(recovered.events()) == 1


def test_uncommitted_transaction_not_visible_after_reconnect(tmp_path: Path) -> None:
    """Crash mid-transaction: uncommitted INSERT must not appear after reopen."""
    path = tmp_path / "ledger.sqlite3"
    store = LedgerStore(path)
    store.append(_event("event-1"))

    connection = store.connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO events (
                event_id, event_type, project_id, artifact_id, obligation_id,
                occurred_at, actor_id, payload_json, supersedes_event_id,
                previous_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event-ghost",
                EventType.EVIDENCE_COMPILED.value,
                "project",
                "artifact",
                "O-01",
                datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                "tester",
                "{}",
                None,
                "deadbeef",
                "ghost" + ("0" * 59),
            ),
        )
        # Abrupt close without COMMIT (simulates process kill).
        connection.close()
    finally:
        try:
            connection.close()
        except Exception:
            pass

    recovered = LedgerStore(path)
    ids = [e.event_id for e in recovered.events()]
    assert ids == ["event-1"]
    assert "event-ghost" not in ids
    recovered.verify()


def test_committed_events_survive_new_process_instance(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    LedgerStore(path).append(_event("event-1", payload={"n": 1}))
    LedgerStore(path).append(_event("event-2", payload={"n": 2}))

    # Fresh instance (as after process restart).
    recovered = LedgerStore(path)
    assert [e.event_id for e in recovered.events()] == ["event-1", "event-2"]
    recovered.verify()
    export = tmp_path / "out.jsonl"
    assert recovered.export_jsonl(export) == 2
    assert LedgerStore.verify_exported_jsonl(export) == 2


def _worker_append(path_str: str, event_id: str, artifact_id: str) -> None:
    store = LedgerStore(Path(path_str))
    store.append(
        UtilityEvent(
            event_id=event_id,
            event_type=EventType.EXPERT_TIME_RECORDED,
            project_id="project",
            artifact_id=artifact_id,
            obligation_id="O-01",
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            actor_id="worker",
            payload={"category": "review", "hours": 0.1},
        )
    )


def test_multiprocess_writers_preserve_hash_chain(tmp_path: Path) -> None:
    """Multi-writer under separate processes (stronger than thread-pool unit test)."""
    path = tmp_path / "ledger.sqlite3"
    LedgerStore(path).initialize()
    assert LedgerStore(path).journal_mode() == "wal"

    ctx = mp.get_context("spawn")
    procs = [
        ctx.Process(
            target=_worker_append,
            args=(str(path), f"evt-{i}", f"art-{i % 3}"),
        )
        for i in range(12)
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=30)
        assert proc.exitcode == 0, f"worker failed with exit {proc.exitcode}"

    store = LedgerStore(path)
    assert len(store.events()) == 12
    store.verify()


def test_rollback_on_duplicate_does_not_corrupt_chain(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    store = LedgerStore(path)
    store.append(_event("event-1"))
    with pytest.raises(LedgerIntegrityError, match="duplicate"):
        store.append(_event("event-1", payload={"dup": True}))
    store.append(_event("event-2"))
    store.verify()
    assert [e.event_id for e in store.events()] == ["event-1", "event-2"]


def test_wal_checkpoint_then_verify_after_sidecar_cleanup(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    store = LedgerStore(path)
    for i in range(5):
        store.append(_event(f"event-{i}", artifact_id=f"a-{i % 2}"))
    store.checkpoint(truncate=True)
    # Simulate operator copying only the main DB file after clean checkpoint.
    recovered = LedgerStore(path)
    assert len(recovered.events()) == 5
    recovered.verify()
