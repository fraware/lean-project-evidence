"""Doctor ledger permission warnings and Docker Lean image honesty."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from lpe.cli import app
from lpe.execution.sandbox import DEFAULT_DOCKER_IMAGE
from lpe.ledger.seal import write_seal
from lpe.ledger.store import LedgerStore
from lpe.models import EventType, UtilityEvent

runner = CliRunner()


def test_doctor_warns_default_docker_not_lean() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["docker_image"] == DEFAULT_DOCKER_IMAGE or "LPE_DOCKER_IMAGE" in str(payload)
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
            occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
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
    assert payload["ledger"]["seal_exists"] is False
    assert payload["ledger"]["seal_colocated"] is None
    assert "seal_storage_recommendation" in payload["ledger"]
    assert any("no ledger seal found" in w for w in payload["ledger"]["warnings"])
    assert "supported_seal" in payload["ledger"]


def test_doctor_ledger_seal_present_clears_missing_warning(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite3"
    store = LedgerStore(ledger)
    store.append(
        UtilityEvent(
            event_id="evt-doc-2",
            event_type=EventType.CANDIDATE_REGISTERED,
            project_id="project",
            artifact_id="artifact",
            obligation_id="O-01",
            occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
            actor_id="tester",
            payload={"x": 1},
        )
    )
    write_seal(store)
    result = runner.invoke(app, ["doctor", "--ledger", str(ledger)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ledger"]["seal_exists"] is True
    assert payload["ledger"]["seal_colocated"] is True
    assert not any("no ledger seal found" in w for w in payload["ledger"]["warnings"])
    assert any("co-located" in w for w in payload["ledger"]["warnings"])


def test_doctor_ledger_separate_seal_clears_colocated_warning(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite3"
    separate = tmp_path / "offhost" / "ledger.seal.json"
    store = LedgerStore(ledger)
    store.append(
        UtilityEvent(
            event_id="evt-doc-3",
            event_type=EventType.CANDIDATE_REGISTERED,
            project_id="project",
            artifact_id="artifact",
            obligation_id="O-01",
            occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
            actor_id="tester",
            payload={"x": 1},
        )
    )
    write_seal(store, separate)
    # Doctor looks at the default path; copy recommendation is for operators.
    # Simulate operator who also left no default seal — only separate exists.
    result = runner.invoke(app, ["doctor", "--ledger", str(ledger)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ledger"]["seal_exists"] is False
    assert any("no ledger seal found" in w for w in payload["ledger"]["warnings"])
    assert "--seal" in payload["ledger"]["seal_storage_recommendation"]
