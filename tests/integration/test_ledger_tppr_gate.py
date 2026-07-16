"""Ledger export / verify_exported_jsonl round-trip and tamper detection."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.ledger.store import LedgerIntegrityError, LedgerStore
from lpe.models import EventType, UtilityEvent

runner = CliRunner()


def _event(event_id: str, event_type: EventType, payload: dict) -> UtilityEvent:
    return UtilityEvent(
        event_id=event_id,
        event_type=event_type,
        project_id="example-category-project",
        artifact_id="artifact",
        obligation_id="O-01",
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        actor_id="integrator",
        payload=payload,
    )


def test_ledger_export_verify_round_trip_cli(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite3"
    export_path = tmp_path / "events.jsonl"
    store = LedgerStore(ledger)
    store.append(_event("evt-1", EventType.CANDIDATE_REGISTERED, {"x": 1}))
    store.append(_event("evt-2", EventType.EVIDENCE_COMPILED, {"x": 2}))

    result = runner.invoke(
        app,
        ["ledger", "export", str(ledger), "--output", str(export_path), "--verify"],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert "chain verified" in result.stdout
    assert LedgerStore.verify_exported_jsonl(export_path) == 2


def test_ledger_export_tamper_detected_on_event_hash(tmp_path: Path) -> None:
    """Invariant: mutating event_hash in exported JSONL fails verify_exported_jsonl."""
    ledger = tmp_path / "ledger.sqlite3"
    export_path = tmp_path / "events.jsonl"
    store = LedgerStore(ledger)
    store.append(_event("evt-1", EventType.CANDIDATE_REGISTERED, {"x": 1}))
    store.export_jsonl(export_path)

    record = json.loads(export_path.read_text(encoding="utf-8").strip())
    record["event_hash"] = "0" * 64
    export_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(LedgerIntegrityError, match="invalid event_hash"):
        LedgerStore.verify_exported_jsonl(export_path)


def test_ledger_export_tamper_detected_on_previous_hash(tmp_path: Path) -> None:
    """Invariant: broken previous_hash links fail offline verify."""
    ledger = tmp_path / "ledger.sqlite3"
    export_path = tmp_path / "events.jsonl"
    store = LedgerStore(ledger)
    store.append(_event("evt-1", EventType.CANDIDATE_REGISTERED, {"x": 1}))
    store.append(_event("evt-2", EventType.EVIDENCE_COMPILED, {"x": 2}))
    store.export_jsonl(export_path)

    lines = export_path.read_text(encoding="utf-8").strip().splitlines()
    records = [json.loads(line) for line in lines]
    records[1]["previous_hash"] = "deadbeef" * 8
    export_path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    with pytest.raises(LedgerIntegrityError, match="previous_hash"):
        LedgerStore.verify_exported_jsonl(export_path)


def test_tppr_blocked_when_ledger_verify_fails(tmp_path: Path) -> None:
    """Invariant: tppr compute refuses to report metrics on a broken chain."""
    ledger = tmp_path / "ledger.sqlite3"
    store = LedgerStore(ledger)
    store.append(_event("evt-1", EventType.CANDIDATE_REGISTERED, {"x": 1}))
    with store.connect() as connection:
        connection.execute("DROP TRIGGER deny_events_update")
        connection.execute(
            "UPDATE events SET event_hash = ? WHERE event_id = ?",
            ("0" * 64, "evt-1"),
        )
    result = runner.invoke(
        app,
        [
            "tppr",
            "compute",
            str(ledger),
            "--project-id",
            "example-category-project",
        ],
    )
    assert result.exit_code != 0
