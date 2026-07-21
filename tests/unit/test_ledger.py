from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lpe.ledger.store import LedgerAuthError, LedgerIntegrityError, LedgerStore
from lpe.models import EventType, UtilityEvent


def event(
    event_id: str,
    event_type: EventType,
    payload: dict,
    *,
    artifact_id: str = "artifact",
    supersedes_event_id: str | None = None,
) -> UtilityEvent:
    return UtilityEvent(
        event_id=event_id,
        event_type=event_type,
        project_id="project",
        artifact_id=artifact_id,
        obligation_id="O-01",
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        actor_id="tester",
        payload=payload,
        supersedes_event_id=supersedes_event_id,
    )


def test_ledger_hash_chain_and_append_only(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    store = LedgerStore(path)
    store.append(event("event-1", EventType.CANDIDATE_REGISTERED, {"x": 1}))
    store.append(event("event-2", EventType.EVIDENCE_COMPILED, {"x": 2}))
    store.verify()
    assert len(store.events()) == 2

    with store.connect() as connection:
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("DELETE FROM events WHERE event_id = 'event-1'")


def test_ledger_rejects_duplicate_event_ids(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "ledger.sqlite3")
    store.append(event("event-1", EventType.CANDIDATE_REGISTERED, {"x": 1}))
    with pytest.raises(LedgerIntegrityError, match="duplicate"):
        store.append(event("event-1", EventType.EVIDENCE_COMPILED, {"x": 2}))


def test_ledger_correction_records_compensating_event(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "ledger.sqlite3")
    store.append(event("event-1", EventType.ARTIFACT_ACCEPTED, {"accepted": True}))
    store.append_correction(
        event_id="event-2",
        project_id="project",
        artifact_id="artifact",
        actor_id="auditor",
        supersedes_event_id="event-1",
        reason="accepted in error",
    )
    records = store.events()
    assert records[-1].event_type is EventType.CORRECTION_RECORDED
    assert records[-1].supersedes_event_id == "event-1"
    store.verify()


def test_ledger_verify_rejects_unknown_supersedes_target(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "ledger.sqlite3")
    store.append(
        event(
            "event-1",
            EventType.CORRECTION_RECORDED,
            {"reason": "bad"},
            supersedes_event_id="missing-event",
        )
    )
    with pytest.raises(LedgerIntegrityError, match="supersedes unknown event"):
        store.verify()


def test_ledger_verify_detects_tampered_hash(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "ledger.sqlite3")
    store.append(event("event-1", EventType.CANDIDATE_REGISTERED, {"x": 1}))
    with store.connect() as connection:
        connection.execute("DROP TRIGGER deny_events_update")
        connection.execute(
            "UPDATE events SET event_hash = ? WHERE event_id = ?",
            ("0" * 64, "event-1"),
        )
    with pytest.raises(LedgerIntegrityError, match="invalid event_hash"):
        store.verify()


def test_ledger_export_jsonl_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    export_path = tmp_path / "events.jsonl"
    store = LedgerStore(path)
    store.append(event("event-1", EventType.CANDIDATE_REGISTERED, {"x": 1}))
    store.append(event("event-2", EventType.EVIDENCE_COMPILED, {"x": 2}))
    count = store.export_jsonl(export_path)
    assert count == 2
    lines = export_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    exported = [json.loads(line) for line in lines]
    assert [record["event"]["event_id"] for record in exported] == ["event-1", "event-2"]
    assert all("previous_hash" in record and "event_hash" in record for record in exported)
    assert exported[0]["previous_hash"] is None
    assert exported[1]["previous_hash"] == exported[0]["event_hash"]
    assert LedgerStore.verify_exported_jsonl(export_path) == 2
    store.verify()


def test_ledger_rejects_anonymous_actor(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "ledger.sqlite3")
    anonymous = event("event-1", EventType.CANDIDATE_REGISTERED, {"x": 1})
    anonymous = anonymous.model_copy(update={"actor_id": "anonymous"})
    with pytest.raises(LedgerAuthError, match="anonymous"):
        store.append(anonymous)


def test_ledger_export_hash_tamper_detected(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    export_path = tmp_path / "events.jsonl"
    store = LedgerStore(path)
    store.append(event("event-1", EventType.CANDIDATE_REGISTERED, {"x": 1}))
    store.export_jsonl(export_path)
    record = json.loads(export_path.read_text(encoding="utf-8").strip())
    record["event_hash"] = "0" * 64
    export_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(LedgerIntegrityError, match="invalid event_hash"):
        LedgerStore.verify_exported_jsonl(export_path)


def test_ledger_concurrent_appends_preserve_integrity(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    store = LedgerStore(path)
    store.initialize()

    def append_one(index: int) -> str:
        local_store = LedgerStore(path)
        return local_store.append(
            event(
                f"event-{index}",
                EventType.EXPERT_TIME_RECORDED,
                {"category": "review", "hours": 0.1},
                artifact_id=f"artifact-{index % 3}",
            )
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(append_one, index) for index in range(24)]
        hashes = [future.result() for future in as_completed(futures)]

    assert len(set(hashes)) == 24
    assert len(LedgerStore(path).events()) == 24
    LedgerStore(path).verify()
