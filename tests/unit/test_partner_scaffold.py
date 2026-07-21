"""Partner scaffold + field overhead tests (not §21 / no causal claims)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.ledger.store import LedgerStore
from lpe.metrics.tppr import compute_tppr
from lpe.pilot.field_overhead import compute_field_overhead, record_field_overhead
from lpe.pilot.partner_scaffold import (
    ANALYSIS_PLAN_STATUS_UNFROZEN,
    PARTNER_CONDITION_TAGS,
    init_partner_pilot,
    validate_partner_scaffold,
)
from lpe.pilot.warehouse import OVERHEAD_CATEGORY, PilotWarehouse

runner = CliRunner()


def test_init_partner_scaffold_validates(tmp_path: Path) -> None:
    root = tmp_path / "partner-pilot"
    created = init_partner_pilot(root, project_id="acme-lean")
    assert created.section_21_cleared is False
    assert created.causal_claims is False
    assert created.ledger_path.name == "partner-pilot.sqlite3"
    assert not created.ledger_path.exists()  # created on first ledger use

    check = validate_partner_scaffold(root)
    assert check.ok, (check.missing, check.errors)
    assert check.ready_to_instrument is True
    assert check.ready_to_claim is False
    assert check.section_21_cleared is False
    assert check.analysis_plan_status == ANALYSIS_PLAN_STATUS_UNFROZEN
    assert set(check.condition_tags) == set(PARTNER_CONDITION_TAGS)

    plan = (root / "analysis_plan.md").read_text(encoding="utf-8")
    assert ANALYSIS_PLAN_STATUS_UNFROZEN in plan
    tags = json.loads((root / "condition_tags.json").read_text(encoding="utf-8"))
    assert tags["section_21_cleared"] is False


def test_init_partner_refuses_nonempty_without_force(tmp_path: Path) -> None:
    root = tmp_path / "partner-pilot"
    root.mkdir()
    (root / "noise.txt").write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        init_partner_pilot(root)
    init_partner_pilot(root, force=True)
    assert validate_partner_scaffold(root).ok


def test_cli_init_partner_and_validate(tmp_path: Path) -> None:
    root = tmp_path / "kit"
    create = runner.invoke(
        app,
        [
            "pilot",
            "init-partner",
            "--dir",
            str(root),
            "--project-id",
            "partner-x",
        ],
    )
    assert create.exit_code == 0, create.stdout
    body = json.loads(create.stdout)
    assert body["ready_to_instrument"] is True
    assert body["ready_to_claim"] is False
    assert body["section_21_cleared"] is False
    assert body["validated"] is True

    validate = runner.invoke(
        app,
        ["pilot", "init-partner", "--validate", "--dir", str(root)],
    )
    assert validate.exit_code == 0, validate.stdout
    vbody = json.loads(validate.stdout)
    assert vbody["ok"] is True
    assert vbody["ready_to_claim"] is False


def test_cli_overhead_separated_from_review_minutes(tmp_path: Path) -> None:
    ledger = tmp_path / "pilot.sqlite3"
    log = tmp_path / "overhead" / "field.jsonl"

    # Seed one review-minute event.
    review = runner.invoke(
        app,
        [
            "pilot",
            "record",
            "--ledger",
            str(ledger),
            "--project-id",
            "proj",
            "--actor",
            "field-ops",
            "--kind",
            "expert-time",
            "--candidate-id",
            "c1",
            "--condition-tag",
            "instrumented",
            "--category",
            "review",
            "--minutes",
            "30",
        ],
    )
    assert review.exit_code == 0, review.stdout

    overhead = runner.invoke(
        app,
        [
            "pilot",
            "overhead",
            "--ledger",
            str(ledger),
            "--project-id",
            "proj",
            "--actor",
            "field-ops",
            "--baseline-minutes",
            "100",
            "--wall-minutes",
            "108",
            "--candidate-id",
            "c1",
            "--condition-tag",
            "shadow",
            "--local-log",
            str(log),
        ],
    )
    assert overhead.exit_code == 0, overhead.stdout
    payload = json.loads(overhead.stdout)
    assert payload["category"] == OVERHEAD_CATEGORY
    assert payload["is_review_minutes"] is False
    assert payload["within_budget"] is True
    assert payload["section_21_cleared"] is False
    assert payload["overhead_fraction"] == pytest.approx(0.08)

    assert log.is_file()
    log_row = json.loads(log.read_text(encoding="utf-8").strip())
    assert log_row["is_review_minutes"] is False
    assert log_row["wall_minutes"] == 108.0

    events = LedgerStore(ledger).events("proj")
    tppr = compute_tppr(events, "proj")
    # Only the 30 review minutes (0.5 h) count; overhead is excluded.
    assert tppr.expert_hours_total == pytest.approx(0.5)


def test_record_field_overhead_api(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "p.sqlite3")
    wh = PilotWarehouse(store, actor_id="ops", project_id="proj")
    report, entry = compute_field_overhead(baseline_minutes=50.0, wall_minutes=54.0)
    assert report.within_budget is True
    assert entry.is_review_minutes is False

    result, logged = record_field_overhead(
        wh,
        baseline_minutes=50.0,
        wall_minutes=54.0,
        candidate_id="c9",
        condition_tag="shadow",
        local_log=tmp_path / "oh.jsonl",
    )
    assert result.event_id
    assert logged.category == OVERHEAD_CATEGORY
    assert (tmp_path / "oh.jsonl").is_file()


def test_validate_fails_when_condition_missing(tmp_path: Path) -> None:
    root = tmp_path / "broken"
    init_partner_pilot(root)
    tags_path = root / "condition_tags.json"
    data = json.loads(tags_path.read_text(encoding="utf-8"))
    data["conditions"] = [c for c in data["conditions"] if c["tag"] != "shadow"]
    tags_path.write_text(json.dumps(data), encoding="utf-8")
    check = validate_partner_scaffold(root)
    assert check.ok is False
    assert any("shadow" in e for e in check.errors)
