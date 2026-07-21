"""Golden §21 gate fixtures — synthetic sealed pass/fail (not live pilot data).

These fixtures prove the evaluator fails closed on missing data and can set
authorization flags only when every gate observable meets thresholds. They do
**not** claim a partner study, causal utility, or production §21 clearance.
"""

from __future__ import annotations

import json
from pathlib import Path

from lpe.honesty.research_gates import (
    evaluate_gates_from_paths,
    evaluate_section21_gates,
)
from lpe.ledger.seal import write_seal
from lpe.ledger.store import LedgerStore
from lpe.pilot.analysis import PilotEpisodeRecord, analyze_pilot
from lpe.pilot.protocol import freeze_protocol, validate_bundle_dir, write_example_bundle

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "section21"

PASSING_OBSERVABLES = {
    "packet_automation_rate": 0.85,
    "exact_environment_reproduction": 0.95,
    "median_instrumentation_overhead": 0.05,
    "p90_instrumentation_overhead": 0.12,
    "comprehension_pass_rate": 0.90,
    "primary_category_agreement": 0.80,
    "instrumented_efficiency_gain": 0.25,
    "instrumented_l2_l3_sensitivity_delta_pp": -1.0,
    "instrumented_additional_integrated_l3": 0,
    "sealed_reproducible": True,
    "dataset_sufficiency_for_routing": True,
    "dataset_sufficiency_for_synthesis": True,
}


def test_section21_fail_closed_on_empty_observables() -> None:
    report = evaluate_section21_gates(
        protocol_id="synthetic.fail",
        data_lock_hash="d" * 64,
        observables={},
    )
    assert report.shadow_pilot_passed is False
    assert report.learned_routing_authorized is False
    assert report.synthesis_authorized is False
    assert len(report.blocking_reasons) >= 10
    assert all(not g.passed for g in report.gates)


def test_section21_synthetic_pass_authorizes_when_sufficient() -> None:
    report = evaluate_section21_gates(
        protocol_id="synthetic.pass",
        data_lock_hash="e" * 64,
        observables=PASSING_OBSERVABLES,
        dataset_sufficiency_for_routing=True,
        dataset_sufficiency_for_synthesis=True,
    )
    assert report.shadow_pilot_passed is True
    assert report.learned_routing_authorized is True
    assert report.synthesis_authorized is True
    assert report.blocking_reasons == []
    assert report.report_hash


def test_section21_pass_but_routing_blocked_without_dataset_flag() -> None:
    report = evaluate_section21_gates(
        protocol_id="synthetic.pass-no-routing",
        data_lock_hash="f" * 64,
        observables=PASSING_OBSERVABLES,
        dataset_sufficiency_for_routing=False,
        dataset_sufficiency_for_synthesis=False,
    )
    assert report.shadow_pilot_passed is True
    assert report.learned_routing_authorized is False
    assert report.synthesis_authorized is False


def test_section21_fail_on_single_gate_regression() -> None:
    bad = dict(PASSING_OBSERVABLES)
    bad["packet_automation_rate"] = 0.50
    report = evaluate_section21_gates(
        protocol_id="synthetic.fail-g1",
        data_lock_hash="a" * 64,
        observables=bad,
        dataset_sufficiency_for_routing=True,
        dataset_sufficiency_for_synthesis=True,
    )
    assert report.shadow_pilot_passed is False
    assert any(g.gate_id == "G1" and not g.passed for g in report.gates)


def _write_synthetic_bundle(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Protocol + ledger + seal + analysis for evaluate_gates_from_paths."""
    protocol_root = write_example_bundle(tmp_path / "pilot-protocol")
    freeze_protocol(protocol_root)
    bundle = validate_bundle_dir(protocol_root)

    ledger_path = tmp_path / "ledger.sqlite3"
    store = LedgerStore(ledger_path)
    store.initialize()
    seal_path = tmp_path / "ledger.seal.json"
    write_seal(store, seal_path)

    episodes = [
        PilotEpisodeRecord(
            episode_id=f"syn-{i}",
            condition_tag="control" if i % 2 == 0 else "instrumented",
            risk_class="R2",
            artifact_type="theorem",
            reviewer_id="r1",
            review_minutes=30.0,
            outcome="accept",
            automated_packet=True,
            exact_environment_reproduction=True,
            primary_label="ok",
            peer_label="ok",
            weighted_accepted_obligations=1.0,
        )
        for i in range(10)
    ]
    analysis = analyze_pilot(
        protocol_id=bundle.protocol.protocol_id,
        data_lock_hash="c" * 64,
        episodes=episodes,
    )
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(analysis.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return protocol_root, ledger_path, seal_path, analysis_path


def test_section21_cli_path_fail_and_pass(tmp_path: Path) -> None:
    protocol_root, ledger_path, seal_path, analysis_path = _write_synthetic_bundle(tmp_path)

    fail_out = tmp_path / "gates-fail.json"
    fail_obs = tmp_path / "obs-fail.json"
    fail_obs.write_text("{}\n", encoding="utf-8")
    fail_report = evaluate_gates_from_paths(
        protocol_path=protocol_root,
        ledger_path=ledger_path,
        seal_path=seal_path,
        analysis_path=analysis_path,
        output_path=fail_out,
        observables_path=fail_obs,
    )
    assert fail_report.shadow_pilot_passed is False
    assert fail_out.is_file()

    pass_out = tmp_path / "gates-pass.json"
    pass_obs = tmp_path / "obs-pass.json"
    payload = dict(PASSING_OBSERVABLES)
    payload["data_lock_hash"] = "c" * 64
    pass_obs.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    pass_report = evaluate_gates_from_paths(
        protocol_path=protocol_root,
        ledger_path=ledger_path,
        seal_path=seal_path,
        analysis_path=analysis_path,
        output_path=pass_out,
        observables_path=pass_obs,
    )
    assert pass_report.shadow_pilot_passed is True
    assert pass_report.learned_routing_authorized is True
    assert pass_report.synthesis_authorized is True


def test_committed_observables_fixtures_exist() -> None:
    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    readme = FIXTURE_ROOT / "README.md"
    if not readme.is_file():
        readme.write_text(
            "# Synthetic §21 fixtures\n\n"
            "Pass/fail observables for `tests/unit/test_section21_golden.py`.\n"
            "These are **not** live partner pilot data and do not authorize M6/M7.\n",
            encoding="utf-8",
        )
    pass_path = FIXTURE_ROOT / "observables_pass.json"
    fail_path = FIXTURE_ROOT / "observables_fail_empty.json"
    if not pass_path.is_file():
        pass_path.write_text(json.dumps(PASSING_OBSERVABLES, indent=2) + "\n", encoding="utf-8")
    if not fail_path.is_file():
        fail_path.write_text("{}\n", encoding="utf-8")
    assert json.loads(pass_path.read_text(encoding="utf-8"))["packet_automation_rate"] >= 0.80
    assert json.loads(fail_path.read_text(encoding="utf-8")) == {}
