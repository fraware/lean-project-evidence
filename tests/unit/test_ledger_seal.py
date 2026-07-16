"""External ledger seal / snapshot attestation tests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.hashing import sha256_file
from lpe.ledger.seal import (
    CUSTODY_CONTENT_HASH,
    CUSTODY_HMAC,
    SEAL_ENV_KEY,
    LedgerSealError,
    default_seal_path,
    verify_seal,
    write_seal,
)
from lpe.ledger.store import LedgerStore
from lpe.models import EventType, UtilityEvent

runner = CliRunner()


def _event(
    event_id: str,
    payload: dict,
    *,
    artifact_id: str = "artifact",
) -> UtilityEvent:
    return UtilityEvent(
        event_id=event_id,
        event_type=EventType.CANDIDATE_REGISTERED,
        project_id="project",
        artifact_id=artifact_id,
        obligation_id="O-01",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        actor_id="tester",
        payload=payload,
    )


def test_seal_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SEAL_ENV_KEY, raising=False)
    ledger = tmp_path / "ledger.sqlite3"
    store = LedgerStore(ledger)
    store.append(_event("e1", {"x": 1}))
    store.append(_event("e2", {"x": 2}, artifact_id="other"))

    result = write_seal(store)
    seal_path = Path(result["seal_path"])
    assert seal_path == default_seal_path(ledger)
    assert seal_path.is_file()
    manifest = result["manifest"]
    assert manifest["custody"] == CUSTODY_CONTENT_HASH
    assert manifest["not_worm"] is True
    assert "not cryptographic custody" in manifest["custody_note"]
    assert manifest["event_count"] == 2
    assert set(manifest["artifact_tips"]) == {"artifact", "other"}
    assert "hmac" not in manifest

    checked = verify_seal(store)
    assert checked["ok"] is True
    assert checked["event_count"] == 2


def test_seal_hmac_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SEAL_ENV_KEY, "test-seal-key")
    ledger = tmp_path / "ledger.sqlite3"
    store = LedgerStore(ledger)
    store.append(_event("e1", {"x": 1}))

    result = write_seal(store)
    assert result["manifest"]["custody"] == CUSTODY_HMAC
    assert result["manifest"]["hmac"]
    assert verify_seal(store)["ok"] is True

    monkeypatch.setenv(SEAL_ENV_KEY, "wrong-key")
    with pytest.raises(LedgerSealError, match="HMAC mismatch"):
        verify_seal(store)

    monkeypatch.delenv(SEAL_ENV_KEY, raising=False)
    with pytest.raises(LedgerSealError, match=SEAL_ENV_KEY):
        verify_seal(store)


def test_seal_verify_fails_after_event_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(SEAL_ENV_KEY, raising=False)
    ledger = tmp_path / "ledger.sqlite3"
    store = LedgerStore(ledger)
    store.append(_event("e1", {"x": 1}))
    write_seal(store)

    with store.connect() as connection:
        connection.execute("DROP TRIGGER deny_events_update")
        connection.execute(
            "UPDATE events SET event_hash = ? WHERE event_id = ?",
            ("0" * 64, "e1"),
        )

    with pytest.raises(LedgerSealError, match="ledger verify failed"):
        verify_seal(store)


def test_seal_verify_fails_after_silent_append(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(SEAL_ENV_KEY, raising=False)
    ledger = tmp_path / "ledger.sqlite3"
    store = LedgerStore(ledger)
    store.append(_event("e1", {"x": 1}))
    write_seal(store)
    store.append(_event("e2", {"x": 2}))

    with pytest.raises(LedgerSealError, match="event_count"):
        verify_seal(store)


def test_export_seal_content_hash_consistency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(SEAL_ENV_KEY, raising=False)
    ledger = tmp_path / "ledger.sqlite3"
    export_path = tmp_path / "events.jsonl"
    store = LedgerStore(ledger)
    store.append(_event("e1", {"x": 1}))
    store.append(_event("e2", {"x": 2}, artifact_id="other"))

    store.export_jsonl(export_path)
    result = write_seal(store)
    assert result["manifest"]["export_content_hash"] == sha256_file(export_path)
    # Explicit byte identity with hashlib for the same file.
    assert (
        result["manifest"]["export_content_hash"]
        == hashlib.sha256(export_path.read_bytes()).hexdigest()
    )


def test_cli_seal_and_verify_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(SEAL_ENV_KEY, raising=False)
    ledger = tmp_path / "ledger.sqlite3"
    store = LedgerStore(ledger)
    store.append(_event("e1", {"x": 1}))

    sealed = runner.invoke(app, ["ledger", "seal", str(ledger)])
    assert sealed.exit_code == 0, sealed.output
    payload = json.loads(sealed.stdout)
    assert payload["ok"] is True
    assert payload["not_worm"] is True
    assert Path(payload["seal_path"]).is_file()

    checked = runner.invoke(app, ["ledger", "verify-seal", str(ledger)])
    assert checked.exit_code == 0, checked.output
    assert json.loads(checked.stdout)["ok"] is True

    store.append(_event("e2", {"x": 2}))
    failed = runner.invoke(app, ["ledger", "verify-seal", str(ledger)])
    assert failed.exit_code == 1
    assert "seal does not match" in failed.output or "event_count" in failed.output


def test_empty_seal_key_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SEAL_ENV_KEY, "   ")
    store = LedgerStore(tmp_path / "ledger.sqlite3")
    store.initialize()
    with pytest.raises(LedgerSealError, match="empty"):
        write_seal(store)
