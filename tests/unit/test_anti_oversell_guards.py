"""Anti-oversell guards, ADR 0003 doctor check, M6/M7 blocking, Lean honesty."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.honesty.adr import adr_0003_status
from lpe.honesty.lean_status import lean_extractor_status
from lpe.honesty.non_claims import (
    NON_CLAIMS_ITEMS,
    OversellClaimError,
    format_non_claims_block,
    non_claims_payload,
    refuse_oversell_flags,
)
from lpe.honesty.research_gates import (
    ResearchGateBlocked,
    refuse_research_entrypoint,
    research_status_payload,
)
from lpe.lean.extractor import REGEX_STUB_EXTRACTOR
from lpe.models import RiskClass
from lpe.reporting.markdown import REGEX_STUB_PACKET_BANNER, render_packet
from lpe.review.authority import can_record_acceptance
from lpe.routing.baseline import DeterministicRoutingBaseline
from lpe.synthesis.eval_harness import SynthesisEvalHarness

runner = CliRunner()


def test_non_claims_canonical_ids_stable() -> None:
    ids = {item["id"] for item in NON_CLAIMS_ITEMS}
    assert {
        "section_21",
        "causal_tppr",
        "r3_r4_accept",
        "mathlib_elaborator",
        "m6_m7_training",
        "dry_run_is_not_study",
    } <= ids
    block = format_non_claims_block(as_markdown=True)
    assert "NON_CLAIMS" in block
    assert "software metrics" in block.lower() or "Software metrics" in block
    payload = non_claims_payload()
    assert payload["section_21_cleared"] is False
    assert payload["causal_claims"] is False
    assert payload["software_metrics_are_not_causal"] is True


def test_refuse_oversell_flags() -> None:
    refuse_oversell_flags(section_21_cleared=False, causal_claims=False)
    with pytest.raises(OversellClaimError, match="section_21"):
        refuse_oversell_flags(section_21_cleared=True)
    with pytest.raises(OversellClaimError, match="causal"):
        refuse_oversell_flags(claim_causal=True)
    with pytest.raises(OversellClaimError):
        refuse_oversell_flags({"mathlib_complete": "true"})


def test_docs_28_non_claims_exists(repository_root: Path) -> None:
    path = repository_root / "docs" / "NON_CLAIMS.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "§21" in text or "section 21" in text.lower() or "ENGINEERING_SPEC" in text
    assert "ADR 0003" in text or "R3/R4" in text
    assert "Mathlib" in text
    assert "EPIC-039" in text or "M6" in text


def test_adr_0003_status_active(repository_root: Path) -> None:
    status = adr_0003_status(repository_root=repository_root)
    assert status["active"] is True
    assert status["can_record_acceptance"]["R3"] is False
    assert status["can_record_acceptance"]["R4"] is False
    assert status["can_record_acceptance"]["R0"] is True
    assert can_record_acceptance(RiskClass.R3) is False
    assert can_record_acceptance(RiskClass.R4) is False


def test_doctor_reports_adr_and_extractor() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["adr_0003"]["active"] is True
    assert payload["adr_0003"]["can_record_acceptance"]["R3"] is False
    assert "lean_extractor" in payload
    assert payload["lean_extractor"]["mathlib_scale"] is False
    assert any("not Mathlib-scale" in w for w in payload["lean_extractor"]["warnings"])
    assert payload["NON_CLAIMS"]["section_21_cleared"] is False
    assert payload["research_gates"]["training_entrypoints_exist"] is False


def test_lean_status_warns_not_mathlib_scale() -> None:
    result = runner.invoke(app, ["lean", "status"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mathlib_scale"] is False
    assert payload["extractor_mode"] in {REGEX_STUB_EXTRACTOR, "lean.toolchain"}
    combined = (result.stderr or "") + result.stdout
    assert "not Mathlib-scale" in combined or "Mathlib" in combined


def test_research_status_gate_matrix() -> None:
    result = runner.invoke(app, ["research", "status"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["section_21_cleared"] is False
    assert payload["training_entrypoints_exist"] is False
    ids = {g["id"] for g in payload["gates"]}
    assert "EPIC-039" in ids
    assert "EPIC-040" in ids
    assert "SECTION-21" in ids
    md = runner.invoke(app, ["research", "status", "--format", "markdown"])
    assert md.exit_code == 0
    assert "BLOCKED" in md.stdout
    assert research_status_payload()["m6_m7_blocked_until"]


def test_routing_cli_blocked() -> None:
    result = runner.invoke(app, ["routing"])
    assert result.exit_code == 1
    combined = (result.stderr or "") + result.stdout
    assert "§21" in combined or "EPIC-039" in combined or "blocked" in combined.lower()

    train = runner.invoke(app, ["routing", "train"])
    assert train.exit_code == 1
    assert "train" in ((train.stderr or "") + train.stdout).lower() or "EPIC" in (
        (train.stderr or "") + train.stdout
    )

    research_train = runner.invoke(app, ["research", "train"])
    assert research_train.exit_code == 1


def test_m6_m7_train_methods_raise() -> None:
    baseline = DeterministicRoutingBaseline()
    with pytest.raises(ResearchGateBlocked):
        baseline.train()
    with pytest.raises(ResearchGateBlocked):
        baseline.load_learned_policy()
    harness = SynthesisEvalHarness()
    with pytest.raises(ResearchGateBlocked):
        harness.train()
    with pytest.raises(ResearchGateBlocked, match="EPIC"):
        refuse_research_entrypoint("synthesis.train")


def test_pilot_summary_refuses_claim_flags(tmp_path: Path, example_project: Path) -> None:
    from lpe.ledger.store import LedgerStore

    ledger = tmp_path / "ledger.sqlite3"
    LedgerStore(ledger).initialize()
    result = runner.invoke(
        app,
        [
            "pilot",
            "summary",
            str(ledger),
            "--project-id",
            "example-category-project",
            "--claim-section-21",
        ],
    )
    assert result.exit_code == 1
    combined = (result.stderr or "") + result.stdout
    assert "Refusing" in combined or "oversell" in combined.lower() or "§21" in combined


def test_pilot_summary_emits_non_claims(tmp_path: Path) -> None:
    from lpe.ledger.store import LedgerStore

    ledger = tmp_path / "ledger.sqlite3"
    LedgerStore(ledger).initialize()
    result = runner.invoke(
        app,
        [
            "pilot",
            "summary",
            str(ledger),
            "--project-id",
            "example-category-project",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert "NON_CLAIMS" in payload
    assert payload["NON_CLAIMS"]["section_21_cleared"] is False
    assert payload["section_21_cleared"] is False
    assert payload["causal_claims"] is False

    md = runner.invoke(
        app,
        [
            "pilot",
            "summary",
            str(ledger),
            "--project-id",
            "example-category-project",
            "--format",
            "markdown",
        ],
    )
    assert md.exit_code == 0
    assert "NON_CLAIMS" in md.stdout
    assert "software" in md.stdout.lower()


def test_markdown_regex_stub_banner(example_project, example_candidate) -> None:
    from lpe.evidence.compiler import compile_evidence

    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    md = render_packet(packet)
    # skip_build path uses regex-stub → mandatory honesty banner
    assert "regex-stub" in md.lower() or REGEX_STUB_PACKET_BANNER.split("\n")[0] in md
    assert "incomplete" in md.lower()
    assert "Mathlib" in md or "NON_CLAIMS" in md


def test_lean_extractor_status_shape() -> None:
    status = lean_extractor_status(None)
    assert "extractor_mode" in status
    assert status["mathlib_scale"] is False
    assert status["warnings"]
