"""Durable pilot warehouse tests (not §21 / no causal claims)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.ledger.store import LedgerAuthError, LedgerStore
from lpe.models import EventType
from lpe.pilot.overhead import OverheadReport
from lpe.pilot.summary import summarize_pilot
from lpe.pilot.warehouse import OVERHEAD_CATEGORY, PilotWarehouse

runner = CliRunner()


def test_warehouse_durable_across_store_restart(tmp_path: Path) -> None:
    ledger = tmp_path / "pilot.sqlite3"
    store = LedgerStore(ledger)
    warehouse = PilotWarehouse(
        store, actor_id="pilot-operator", project_id="proj-a"
    )
    warehouse.register_candidate(
        candidate_id="c1",
        obligation_ids=["O-01"],
        condition_tag="instrumented",
    )
    warehouse.record_expert_time(
        candidate_id="c1",
        category="review",
        minutes=12.0,
        condition_tag="instrumented",
    )
    warehouse.mark_packet_automated(
        candidate_id="c1",
        condition_tag="instrumented",
        recommendation="ESCALATE",
    )

    # New process / new LedgerStore instance must see prior events.
    reloaded = LedgerStore(ledger)
    reloaded.verify()
    events = reloaded.events("proj-a")
    types = {e.event_type for e in events}
    assert EventType.CANDIDATE_REGISTERED in types
    assert EventType.EXPERT_TIME_RECORDED in types
    assert EventType.EVIDENCE_COMPILED in types
    assert all(e.payload.get("durable") is True for e in events)
    assert all(e.payload.get("section_21_cleared") is False for e in events)

    summary = summarize_pilot(reloaded, project_id="proj-a")
    assert summary.candidate_count == 1
    assert summary.automation_rate == 1.0
    assert summary.expert_minutes_total == 12.0
    assert summary.section_21_cleared is False
    assert summary.causal_claims is False


def test_warehouse_summary_aggregates_by_condition(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "pilot.sqlite3")
    wh = PilotWarehouse(store, actor_id="ops", project_id="proj")
    wh.register_candidate(
        candidate_id="a", obligation_ids=["O-01"], condition_tag="control"
    )
    wh.register_candidate(
        candidate_id="b", obligation_ids=["O-01"], condition_tag="instrumented"
    )
    wh.mark_packet_automated(candidate_id="b", condition_tag="instrumented")
    wh.record_expert_time(
        candidate_id="a", category="review", minutes=10.0, condition_tag="control"
    )
    wh.record_expert_time(
        candidate_id="b",
        category="repair",
        minutes=20.0,
        condition_tag="instrumented",
    )
    wh.record_outcome(
        candidate_id="a",
        condition_tag="control",
        decision="REQUEST_REPAIR",
    )
    overhead = OverheadReport.compute(
        baseline_minutes=100.0, instrumented_minutes=105.0
    )
    wh.record_overhead_snapshot(artifact_id="corpus", report=overhead)

    summary = summarize_pilot(LedgerStore(tmp_path / "pilot.sqlite3"), project_id="proj")
    assert summary.candidate_count == 2
    assert summary.automated_count == 1
    assert summary.automation_rate == 0.5
    assert summary.expert_minutes_by_condition["control"] == 10.0
    assert summary.expert_minutes_by_condition["instrumented"] == 20.0
    assert summary.conditions["instrumented"].automated == 1
    assert summary.conditions["control"].outcomes["REQUEST_REPAIR"] == 1
    assert len(summary.overhead_snapshots) == 1
    assert summary.overhead_snapshots[0]["within_budget"] is True
    # Overhead must not inflate expert_minutes_total.
    assert summary.expert_minutes_total == 30.0


def test_warehouse_rejects_anonymous_actor(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "pilot.sqlite3")
    with pytest.raises(LedgerAuthError, match="anonymous"):
        PilotWarehouse(store, actor_id="anonymous", project_id="proj")


def test_cli_pilot_record_and_summary(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite3"
    record = runner.invoke(
        app,
        [
            "pilot",
            "record",
            "--ledger",
            str(ledger),
            "--project-id",
            "proj",
            "--actor",
            "cli-ops",
            "--kind",
            "candidate",
            "--candidate-id",
            "c1",
            "--condition-tag",
            "control",
            "--obligation-ids",
            "O-01,O-02",
        ],
    )
    assert record.exit_code == 0, record.stdout
    payload = json.loads(record.stdout)
    assert payload["durable"] is True
    assert payload["section_21_cleared"] is False

    time_rec = runner.invoke(
        app,
        [
            "pilot",
            "record",
            "--ledger",
            str(ledger),
            "--project-id",
            "proj",
            "--actor",
            "cli-ops",
            "--kind",
            "expert-time",
            "--candidate-id",
            "c1",
            "--condition-tag",
            "control",
            "--category",
            "review",
            "--minutes",
            "8",
        ],
    )
    assert time_rec.exit_code == 0, time_rec.stdout

    auto = runner.invoke(
        app,
        [
            "pilot",
            "record",
            "--ledger",
            str(ledger),
            "--project-id",
            "proj",
            "--actor",
            "cli-ops",
            "--kind",
            "packet-automated",
            "--candidate-id",
            "c1",
            "--condition-tag",
            "control",
        ],
    )
    assert auto.exit_code == 0, auto.stdout

    summary = runner.invoke(
        app,
        ["pilot", "summary", str(ledger), "--project-id", "proj"],
    )
    assert summary.exit_code == 0, summary.stdout
    body = json.loads(summary.stdout)
    assert body["candidate_count"] == 1
    assert body["automation_rate"] == 1.0
    assert body["expert_minutes_total"] == 8.0
    assert body["causal_claims"] is False


def test_cli_pilot_record_rejects_anonymous(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite3"
    result = runner.invoke(
        app,
        [
            "pilot",
            "record",
            "--ledger",
            str(ledger),
            "--project-id",
            "proj",
            "--actor",
            "anonymous",
            "--kind",
            "candidate",
            "--candidate-id",
            "c1",
            "--condition-tag",
            "control",
        ],
    )
    assert result.exit_code == 1
    combined = (result.stdout + (result.stderr or "")).lower()
    assert "anonymous" in combined


def test_overhead_category_excluded_from_tppr_denominator(tmp_path: Path) -> None:
    from lpe.metrics.tppr import compute_tppr

    store = LedgerStore(tmp_path / "pilot.sqlite3")
    wh = PilotWarehouse(store, actor_id="ops", project_id="proj")
    wh.record_expert_time(
        candidate_id="c1",
        category="review",
        minutes=60.0,
        condition_tag="control",
    )
    wh.record_overhead_snapshot(
        artifact_id="corpus",
        report=OverheadReport.compute(
            baseline_minutes=100.0, instrumented_minutes=110.0
        ),
    )
    events = LedgerStore(tmp_path / "pilot.sqlite3").events("proj")
    assert any(
        e.payload.get("category") == OVERHEAD_CATEGORY for e in events
    )
    report = compute_tppr(events, "proj")
    # Only review hour counts; overhead is exclusion, not denominator.
    assert report.expert_hours_total == pytest.approx(1.0)
    assert any("unknown expert time category" in x for x in report.exclusions)
