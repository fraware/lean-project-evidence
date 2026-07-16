"""Ledger archive / retention prototype (verify → export → verify; live untouched)."""

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
        actor_id="archivist",
        payload=payload,
    )


def test_archive_verified_jsonl_leaves_live_intact(tmp_path: Path) -> None:
    ledger = tmp_path / "live.sqlite3"
    archive = tmp_path / "archive" / "events.jsonl"
    store = LedgerStore(ledger)
    store.append(_event("evt-1", EventType.CANDIDATE_REGISTERED, {"n": 1}))
    store.append(_event("evt-2", EventType.EVIDENCE_COMPILED, {"n": 2}))

    result = store.archive_verified_jsonl(archive)
    assert result["events"] == 2
    assert result["live_unchanged"] is True
    assert LedgerStore.verify_exported_jsonl(archive) == 2

    # Live chain still verifies and still has both events.
    store.verify()
    with store.connect() as connection:
        count = connection.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
    assert count == 2


def test_archive_refuses_overwrite_live_sqlite(tmp_path: Path) -> None:
    ledger = tmp_path / "live.sqlite3"
    store = LedgerStore(ledger)
    store.append(_event("evt-1", EventType.CANDIDATE_REGISTERED, {"n": 1}))
    with pytest.raises(LedgerIntegrityError, match="must not overwrite"):
        store.archive_verified_jsonl(ledger)


def test_ledger_archive_cli(tmp_path: Path) -> None:
    ledger = tmp_path / "live.sqlite3"
    archive = tmp_path / "out.jsonl"
    store = LedgerStore(ledger)
    store.append(_event("evt-1", EventType.CANDIDATE_REGISTERED, {"n": 1}))

    result = runner.invoke(
        app,
        ["ledger", "archive", str(ledger), "--output", str(archive)],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["events"] == 1
    assert payload["live_unchanged"] is True
    assert "fresh working set" in " ".join(payload["next_steps"]).lower() or any(
        "ledger init" in step for step in payload["next_steps"]
    )
    assert archive.is_file()
    assert LedgerStore.verify_exported_jsonl(archive) == 1
