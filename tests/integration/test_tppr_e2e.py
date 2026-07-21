"""Integration-lite: contract → evidence → review → ledger → TPPR (no Lean build)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from lpe.cli import app
from lpe.ledger.store import LedgerStore
from lpe.metrics.tppr import compute_tppr
from lpe.models import EventType, UtilityEvent
from lpe.review.decisions import record_review_decision
from lpe.models import ReviewDecision, ReviewDecisionValue

runner = CliRunner()


def test_evidence_compile_skip_build_cli(
    example_project: Path, repository_root: Path, tmp_path: Path
) -> None:
    candidate = repository_root / "examples" / "candidates" / "R3-definition-change.json"
    output = tmp_path / "packet.json"
    markdown = tmp_path / "packet.md"
    result = runner.invoke(
        app,
        [
            "evidence",
            "compile",
            "--project",
            str(example_project),
            "--candidate",
            str(candidate),
            "--output",
            str(output),
            "--skip-build",
            "--markdown",
            str(markdown),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert output.is_file()
    packet = json.loads(output.read_text(encoding="utf-8"))
    assert packet["packet_id"]
    assert packet["hard_gate_passed"] is False
    assert markdown.is_file()
    assert output.stat().st_size < 1_000_000


def test_compile_review_ledger_tppr_path(
    example_project: Path,
    repository_root: Path,
    tmp_path: Path,
) -> None:
    """End-to-end fixture path without Docker/Lean: skip-build + REJECT review + TPPR."""
    candidate = repository_root / "examples" / "candidates" / "R3-definition-change.json"
    packet_path = tmp_path / "packet.json"
    compile_result = runner.invoke(
        app,
        [
            "evidence",
            "compile",
            "--project",
            str(example_project),
            "--candidate",
            str(candidate),
            "--output",
            str(packet_path),
            "--skip-build",
        ],
    )
    assert compile_result.exit_code == 0, compile_result.stdout
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet_id = packet["packet_id"]
    project_id = packet["project_id"]

    ledger = tmp_path / "ledger.sqlite3"
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "review-e2e-reject",
                "packet_id": packet_id,
                "reviewer_id": "r3-reviewer",
                "reviewer_roles": [],
                "decision": "REJECT",
                "confidence": 90,
                "rationale": "integration: signature change rejected",
                "review_minutes": 15.0,
            }
        ),
        encoding="utf-8",
    )
    review_result = runner.invoke(
        app,
        [
            "review",
            "record",
            "--project",
            str(example_project),
            "--decision",
            str(decision_path),
            "--ledger",
            str(ledger),
            "--risk-class",
            "R3",
        ],
    )
    assert review_result.exit_code == 0, review_result.stdout + (review_result.stderr or "")

    verify = runner.invoke(app, ["ledger", "verify", str(ledger)])
    assert verify.exit_code == 0
    assert "valid" in verify.stdout

    store = LedgerStore(ledger)
    events = store.events(project_id)
    assert len(events) >= 2
    assert any(e.event_type is EventType.ARTIFACT_REJECTED for e in events)
    expert = next(e for e in events if e.event_type is EventType.EXPERT_TIME_RECORDED)
    assert "hours" in expert.payload
    assert expert.payload["hours"] == 15.0 / 60.0

    # Seed obligation + expert hours already present; TPPR should compute without KeyError.
    store.append(
        UtilityEvent(
            event_id="evt_obl_e2e",
            event_type=EventType.OBLIGATION_REGISTERED,
            project_id=project_id,
            artifact_id=packet_id,
            obligation_id="O-01",
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            actor_id="integrator",
            payload={"weight": 3},
        )
    )
    tppr_result = runner.invoke(
        app,
        ["tppr", "compute", str(ledger), "--project-id", project_id],
    )
    assert tppr_result.exit_code == 0, tppr_result.stdout + (tppr_result.stderr or "")
    report = json.loads(tppr_result.stdout)
    assert report["project_id"] == project_id
    assert report["expert_hours_total"] > 0
    # Rejected → no sustained credit.
    assert report["weighted_accepted_sustained_obligations"] == 0


def test_review_expert_time_emits_hours_for_tppr(example_project: Path, tmp_path: Path) -> None:
    """Regression: review record must store hours so TPPR does not KeyError."""
    ledger = tmp_path / "ledger.db"
    decision = ReviewDecision(
        review_id="review-hours-fix",
        packet_id="packet_hours",
        reviewer_id="lean-engineer",
        reviewer_roles=[],
        decision=ReviewDecisionValue.ACCEPT,
        confidence=80,
        rationale="hours payload regression",
        review_minutes=30.0,
    )
    record_review_decision(ledger, decision, project_id="example-category-project")
    store = LedgerStore(ledger)
    events = store.events("example-category-project")
    expert = next(e for e in events if e.event_type is EventType.EXPERT_TIME_RECORDED)
    assert expert.payload["hours"] == 0.5
    assert expert.payload["minutes"] == 30.0
    report = compute_tppr(events, "example-category-project")
    assert report.review_hours == 0.5
    assert report.expert_hours_total == 0.5
