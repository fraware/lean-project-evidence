from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lpe.contract.loader import load_contract
from lpe.evidence.compiler import HostExecutionRefusedError, compile_evidence
from lpe.github.check import packet_to_github_check, render_check_payload
from lpe.ledger.store import LedgerStore
from lpe.models import ReviewDecision, ReviewDecisionValue, RiskClass
from lpe.review.authority import (
    AuthorityError,
    can_record_acceptance,
    validate_reviewer_authority,
)
from lpe.review.decisions import record_review_decision
from lpe.cli import app


runner = CliRunner()


def test_authority_rejects_missing_roles(example_project: Path) -> None:
    contract = load_contract(example_project)
    with pytest.raises(AuthorityError, match="not listed in review.yaml"):
        validate_reviewer_authority(
            contract,
            reviewer_id="unknown",
            reviewer_roles=["lean-engineer"],
            risk_class=RiskClass.R3,
        )


def test_forged_domain_lead_roles_fail(example_project: Path) -> None:
    """AUDIT-002: self-declared roles in decision JSON must not grant authority."""
    contract = load_contract(example_project)
    with pytest.raises(AuthorityError, match="not listed in review.yaml"):
        validate_reviewer_authority(
            contract,
            reviewer_id="attacker",
            reviewer_roles=["domain-lead", "repository-maintainer"],
            risk_class=RiskClass.R3,
        )


def test_self_declared_roles_ignored_for_listed_reviewer(example_project: Path) -> None:
    """A listed reviewer cannot escalate by forging extra roles in JSON."""
    contract = load_contract(example_project)
    with pytest.raises(AuthorityError, match="lacks required roles"):
        validate_reviewer_authority(
            contract,
            reviewer_id="lean-engineer",
            reviewer_roles=["domain-lead", "repository-maintainer"],
            risk_class=RiskClass.R3,
        )


def test_authorized_reviewer_passes(example_project: Path) -> None:
    contract = load_contract(example_project)
    validate_reviewer_authority(
        contract,
        reviewer_id="r3-reviewer",
        reviewer_roles=[],  # ignored
        risk_class=RiskClass.R3,
    )
    validate_reviewer_authority(
        contract,
        reviewer_id="lean-engineer",
        reviewer_roles=["forged-admin"],
        risk_class=RiskClass.R1,
    )


def test_can_record_acceptance_blocks_r3_r4() -> None:
    assert can_record_acceptance(RiskClass.R0) is True
    assert can_record_acceptance(RiskClass.R1) is True
    assert can_record_acceptance(RiskClass.R2) is True
    assert can_record_acceptance(RiskClass.R3) is False
    assert can_record_acceptance(RiskClass.R4) is False


def test_record_review_accept_sets_tppr_flags(tmp_path: Path, example_project: Path) -> None:
    """ACCEPT review events carry obligation_id + fidelity flags for TPPR."""
    del example_project  # authority not required for direct ledger append
    ledger_path = tmp_path / "ledger-accept.db"
    decision = ReviewDecision(
        review_id="review-accept-flags",
        packet_id="packet_accept",
        reviewer_id="lean-engineer",
        reviewer_roles=[],
        decision=ReviewDecisionValue.ACCEPT,
        confidence=90,
        rationale="unit accept flags",
        review_minutes=5.0,
    )
    record_review_decision(
        ledger_path,
        decision,
        project_id="example-category-project",
        obligation_ids=["O-01"],
    )
    store = LedgerStore(ledger_path)
    events = store.events("example-category-project")
    accepted = next(e for e in events if e.event_type.value == "ARTIFACT_ACCEPTED")
    assert accepted.obligation_id == "O-01"
    assert accepted.payload["semantic_fidelity"] is True
    assert accepted.payload["repository_accepted"] is True


def test_record_review_decision(tmp_path: Path, example_project: Path) -> None:
    contract = load_contract(example_project)
    ledger_path = tmp_path / "ledger.db"
    decision = ReviewDecision(
        review_id="review-001",
        packet_id="packet_test",
        reviewer_id="r3-reviewer",
        reviewer_roles=["domain-lead", "repository-maintainer"],
        decision=ReviewDecisionValue.REJECT,
        confidence=90,
        rationale="Signature change not justified",
        review_minutes=15.0,
    )
    validate_reviewer_authority(
        contract,
        reviewer_id=decision.reviewer_id,
        reviewer_roles=decision.reviewer_roles,
        risk_class=RiskClass.R3,
    )
    digest = record_review_decision(ledger_path, decision, project_id=contract.project.project_id)
    assert digest
    store = LedgerStore(ledger_path)
    store.verify()
    events = store.events(contract.project.project_id)
    assert len(events) == 2
    assert events[0].event_type.value == "ARTIFACT_REJECTED"
    # Regression: EXPERT_TIME_RECORDED must carry hours for TPPR (not minutes-only).
    assert events[1].event_type.value == "EXPERT_TIME_RECORDED"
    assert events[1].payload["hours"] == 15.0 / 60.0
    assert events[1].payload["minutes"] == 15.0


def test_cli_review_record_rejects_forged_roles(tmp_path: Path, example_project: Path) -> None:
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "review-forged",
                "packet_id": "packet_x",
                "reviewer_id": "attacker",
                "reviewer_roles": ["domain-lead", "repository-maintainer"],
                "decision": "ACCEPT",
                "confidence": 99,
                "rationale": "forged",
                "review_minutes": 1.0,
            }
        ),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.db"
    result = runner.invoke(
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
    assert result.exit_code == 1
    assert (
        "not listed" in (result.stderr or result.stdout).lower()
        or "authority" in (result.stderr or result.stdout).lower()
        or "reviewer" in (result.stderr or result.stdout).lower()
    )


def test_cli_review_record_blocks_r3_accept(tmp_path: Path, example_project: Path) -> None:
    """AUDIT-009: even authorized reviewers cannot record R3 ACCEPT in v0."""
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "review-r3-accept",
                "packet_id": "packet_x",
                "reviewer_id": "r3-reviewer",
                "reviewer_roles": [],
                "decision": "ACCEPT",
                "confidence": 95,
                "rationale": "looks fine",
                "review_minutes": 20.0,
            }
        ),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.db"
    result = runner.invoke(
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
    assert result.exit_code == 1
    combined = (result.stderr or "") + (result.stdout or "")
    assert "ACCEPT" in combined or "ADR" in combined or "R3" in combined


def test_cli_review_record_authorized_r1_accept(tmp_path: Path, example_project: Path) -> None:
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "review-r1-accept",
                "packet_id": "packet_x",
                "reviewer_id": "lean-engineer",
                "reviewer_roles": ["forged-should-be-ignored"],
                "decision": "ACCEPT",
                "confidence": 80,
                "rationale": "ok",
                "review_minutes": 5.0,
            }
        ),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.db"
    result = runner.invoke(
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
            "R1",
        ],
    )
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_github_check_adapter(example_project: Path, example_candidate) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    check = packet_to_github_check(packet)
    payload = render_check_payload(check)
    # AUDIT-018: ESCALATE defaults to failure (fail-closed for required checks).
    assert payload["conclusion"] == "failure"
    assert payload["head_sha"] != "mock-sha"
    assert payload["output"]["title"]
    assert payload["output"]["annotations"]
