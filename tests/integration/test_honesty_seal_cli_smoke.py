"""CI smoke: honesty gates + seal alternate-path CLIs (no Docker / Lean)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from lpe.cli import app
from lpe.ledger.store import LedgerStore
from lpe.models import EventType, UtilityEvent

runner = CliRunner()


def test_research_status_smoke() -> None:
    result = runner.invoke(app, ["research", "status"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["section_21_cleared"] is False
    assert payload["training_entrypoints_exist"] is False
    assert any(g["id"] == "SECTION-21" for g in payload["gates"])


def test_routing_cli_blocked_smoke() -> None:
    result = runner.invoke(app, ["routing"])
    assert result.exit_code == 1
    assert "§21" in result.output or "blocked" in result.output.lower()


def test_seal_alternate_path_cli_smoke(tmp_path: Path) -> None:
    ledger = tmp_path / "data" / "ledger.sqlite3"
    ledger.parent.mkdir()
    seal = tmp_path / "readonly-custody" / "seal.json"
    store = LedgerStore(ledger)
    store.append(
        UtilityEvent(
            event_id="evt-smoke-1",
            event_type=EventType.CANDIDATE_REGISTERED,
            project_id="project",
            artifact_id="artifact",
            obligation_id="O-01",
            occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
            actor_id="tester",
            payload={"smoke": True},
        )
    )
    sealed = runner.invoke(
        app, ["ledger", "seal", str(ledger), "--seal", str(seal)]
    )
    assert sealed.exit_code == 0, sealed.output
    payload = json.loads(sealed.stdout)
    assert payload["ok"] is True
    assert payload["colocated"] is False
    assert payload["not_worm"] is True

    verified = runner.invoke(
        app, ["ledger", "verify-seal", str(ledger), "--seal", str(seal)]
    )
    assert verified.exit_code == 0, verified.output
    assert json.loads(verified.stdout)["ok"] is True

    doctor = runner.invoke(app, ["doctor", "--ledger", str(ledger)])
    assert doctor.exit_code == 0, doctor.output
    report = json.loads(doctor.stdout)
    assert "seal_storage_recommendation" in report["ledger"]
