"""Doctor ledger permission warnings and Docker Lean image honesty."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from lpe.cli import app
from lpe.execution.sandbox import DEFAULT_DOCKER_IMAGE
from lpe.ledger.store import LedgerStore
from lpe.models import EventType, UtilityEvent
from datetime import datetime, timezone

runner = CliRunner()


def test_doctor_warns_default_docker_not_lean() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["docker_image"] == DEFAULT_DOCKER_IMAGE or "LPE_DOCKER_IMAGE" in str(
        payload
    )
    assert payload.get("docker_image_lean_capable_hint")


def test_doctor_ledger_report(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite3"
    store = LedgerStore(ledger)
    store.initialize()
    store.append(
        UtilityEvent(
            event_id="evt-doc-1",
            event_type=EventType.CANDIDATE_REGISTERED,
            project_id="project",
            artifact_id="artifact",
            obligation_id="O-01",
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            actor_id="tester",
            payload={"x": 1},
        )
    )
    result = runner.invoke(app, ["doctor", "--ledger", str(ledger)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "ledger" in payload
    assert payload["ledger"]["exists"] is True
    assert "supported_retention" in payload["ledger"]
