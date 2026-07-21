"""Pilot dry-run instrumentation (NOT a §21 study; no causal claims).

Frozen synthetic corpus → durable ``PilotWarehouse`` ledger events →
compile/review → summary reports distinguishing software metrics vs causal claims.

This is **dry-run instrumentation only**. It does **not** authorize shadow
pilots, production ACCEPT for R3/R4, or ENGINEERING_SPEC §21 science gates.
See ``docs/PILOT.md`` and ``docs/NON_CLAIMS.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.ledger.store import LedgerStore
from lpe.models import EventType
from lpe.pilot.dry_run import SECTION_21_CLEARED, run_frozen_corpus_dry_run
from lpe.pilot.summary import summarize_pilot
from lpe.pilot.warehouse import PILOT_SOURCE

runner = CliRunner()


@pytest.mark.longevity
def test_pilot_frozen_corpus_dry_run_durable_warehouse(
    example_project: Path,
    repository_root: Path,
    tmp_path: Path,
) -> None:
    """Dry-run path only: durable ledger; no causal claims; §21 not passed."""
    assert SECTION_21_CLEARED is False

    result = run_frozen_corpus_dry_run(
        example_project=example_project,
        repository_root=repository_root,
        work_dir=tmp_path,
        actor_id="pilot-dry-run-operator",
        cli_runner=runner,
    )

    assert 10 <= result.corpus_size <= 20
    assert result.automation_rate == 1.0
    assert result.overhead_within_budget is True
    assert result.report_json.is_file()
    assert result.summary_md.is_file()

    artifact = json.loads(result.report_json.read_text(encoding="utf-8"))
    assert artifact["section_21_cleared"] is False
    assert artifact["causal_claims"] is False
    assert artifact["durable"] is True
    assert artifact["metric_class"] == "software_instrumentation"
    assert artifact["non_claims"]["section_21"] == "not passed"
    assert artifact["non_claims"]["causal_utility"] == "not claimed"
    assert "NON_CLAIMS" in artifact
    assert artifact["NON_CLAIMS"]["section_21_cleared"] is False
    assert artifact["NON_CLAIMS"]["software_metrics_are_not_causal"] is True

    report_md = result.report_md.read_text(encoding="utf-8")
    assert "NON_CLAIMS" in report_md
    assert "software_instrumentation" in report_md
    assert "Software metrics" in report_md
    assert "Causal" in report_md or "§21" in report_md
    assert "section_21_cleared" in report_md.lower() or "section_21_cleared" in report_md
    summary_md = result.summary_md.read_text(encoding="utf-8")
    assert "NON_CLAIMS" in summary_md
    assert "software_instrumentation" in summary_md or "Software metrics" in summary_md
    assert "causal" in summary_md.lower() or "§21" in summary_md
    # Fresh store instance (process-restart durability).
    store = LedgerStore(result.ledger_path)
    store.verify()
    events = store.events(result.project_id)
    pilot_events = [e for e in events if e.payload.get("source") == PILOT_SOURCE]
    assert len(pilot_events) >= result.corpus_size
    types = {e.event_type for e in pilot_events}
    assert EventType.CANDIDATE_REGISTERED in types
    assert EventType.EXPERT_TIME_RECORDED in types
    assert EventType.EVIDENCE_COMPILED in types

    summary = summarize_pilot(store, project_id=result.project_id)
    assert summary.candidate_count == result.corpus_size
    assert summary.automation_rate == 1.0
    assert summary.expert_minutes_total > 0
    assert summary.section_21_cleared is False
    assert summary.causal_claims is False

    # Review path still wrote REQUEST_REPAIR into the same ledger.
    assert any(
        e.event_type is EventType.REVIEW_SUBMITTED and e.payload.get("decision") == "REQUEST_REPAIR"
        for e in events
    )

    tppr_result = runner.invoke(
        app,
        ["tppr", "compute", str(result.ledger_path), "--project-id", result.project_id],
    )
    assert tppr_result.exit_code == 0, tppr_result.stdout + (tppr_result.stderr or "")
    tppr = json.loads(tppr_result.stdout)
    assert tppr["project_id"] == result.project_id
    assert tppr["expert_hours_total"] > 0
    # Escalate / repair ⇒ no sustained accept credit in this dry-run.
    assert tppr["weighted_accepted_sustained_obligations"] == 0


@pytest.mark.longevity
def test_pilot_dry_run_cli(
    example_project: Path,
    repository_root: Path,
    tmp_path: Path,
) -> None:
    work = tmp_path / "cli-dry-run"
    result = runner.invoke(
        app,
        [
            "pilot",
            "dry-run",
            "--project",
            str(example_project),
            "--work-dir",
            str(work),
            "--repository-root",
            str(repository_root),
            "--actor",
            "pilot-cli-operator",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["durable"] is True
    assert payload["section_21_cleared"] is False
    assert payload["causal_claims"] is False
    assert "NON_CLAIMS" in payload
    assert payload["NON_CLAIMS"]["software_metrics_are_not_causal"] is True
    assert Path(payload["ledger"]).is_file()
    assert Path(payload["summary_json"]).is_file()


@pytest.mark.longevity
def test_pilot_dry_run_docs_disclaim_section_21(repository_root: Path) -> None:
    protocol = (repository_root / "docs" / "PILOT.md").read_text(encoding="utf-8")
    non_claims = repository_root / "docs" / "NON_CLAIMS.md"
    assert non_claims.is_file(), "docs/NON_CLAIMS.md must document honesty gates"
    text = non_claims.read_text(encoding="utf-8")
    assert "§21" in text or "section 21" in text.lower()
    assert "dry-run" in protocol.lower() or "dry-run" in text.lower()
    assert "causal" in protocol.lower() or "causal" in text.lower()
    assert "not passed" in text.lower() or "do not" in text.lower()
    assert "warehouse" in protocol.lower() or "instrument" in protocol.lower()
