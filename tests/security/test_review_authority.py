"""AUDIT-002 / AUDIT-009: review authority and R3/R4 ACCEPT refusal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.contract.loader import load_contract
from lpe.models import RiskClass
from lpe.review.authority import (
    AuthorityError,
    can_record_acceptance,
    validate_reviewer_authority,
)

runner = CliRunner()


def test_role_forgery_unknown_reviewer_rejected(example_project: Path) -> None:
    """Invariant: self-declared roles do not grant authority for unknown reviewer_id."""
    contract = load_contract(example_project)
    with pytest.raises(AuthorityError, match="not listed in review.yaml"):
        validate_reviewer_authority(
            contract,
            reviewer_id="attacker",
            reviewer_roles=["domain-lead", "repository-maintainer"],
            risk_class=RiskClass.R3,
        )


def test_listed_reviewer_cannot_forge_extra_roles(example_project: Path) -> None:
    """Invariant: review.yaml roles win; forged JSON roles cannot escalate."""
    contract = load_contract(example_project)
    with pytest.raises(AuthorityError, match="lacks required roles"):
        validate_reviewer_authority(
            contract,
            reviewer_id="lean-engineer",
            reviewer_roles=["domain-lead", "repository-maintainer"],
            risk_class=RiskClass.R3,
        )


def test_authorized_r3_reviewer_accepted(example_project: Path) -> None:
    contract = load_contract(example_project)
    validate_reviewer_authority(
        contract,
        reviewer_id="r3-reviewer",
        reviewer_roles=[],
        risk_class=RiskClass.R3,
    )


@pytest.mark.parametrize(
    ("risk", "allowed"),
    [
        (RiskClass.R0, True),
        (RiskClass.R1, True),
        (RiskClass.R2, True),
        (RiskClass.R3, False),
        (RiskClass.R4, False),
    ],
)
def test_can_record_acceptance_matrix(risk: RiskClass, allowed: bool) -> None:
    """Invariant: R3/R4 ACCEPT cannot be recorded via CLI path (ADR 0003)."""
    assert can_record_acceptance(risk) is allowed


def test_cli_rejects_role_forgery(tmp_path: Path, example_project: Path) -> None:
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "review-forged-sec",
                "packet_id": "packet_x",
                "reviewer_id": "attacker",
                "reviewer_roles": ["domain-lead", "repository-maintainer"],
                "decision": "REJECT",
                "confidence": 99,
                "rationale": "forged",
                "review_minutes": 1.0,
            }
        ),
        encoding="utf-8",
    )
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
            str(tmp_path / "ledger.db"),
            "--risk-class",
            "R3",
        ],
    )
    assert result.exit_code == 1
    combined = (result.stderr or "") + (result.stdout or "")
    assert any(
        token in combined.lower()
        for token in ("not listed", "authority", "reviewer")
    )


def test_cli_rejects_r3_accept_even_for_authorized_reviewer(
    tmp_path: Path, example_project: Path
) -> None:
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "review-r3-accept-sec",
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
            str(tmp_path / "ledger.db"),
            "--risk-class",
            "R3",
        ],
    )
    assert result.exit_code == 1
    combined = (result.stderr or "") + (result.stdout or "")
    assert "ACCEPT" in combined or "ADR" in combined or "R3" in combined


def test_cli_rejects_r4_accept_regression(
    tmp_path: Path, example_project: Path
) -> None:
    """Regression: ADR 0003 R4 ACCEPT must remain unrecordable via CLI."""
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "review-r4-accept-sec",
                "packet_id": "packet_r4",
                "reviewer_id": "r4-reviewer",
                "reviewer_roles": [],
                "decision": "ACCEPT",
                "confidence": 99,
                "rationale": "R4 ACCEPT refused (ADR 0003)",
                "review_minutes": 1.0,
            }
        ),
        encoding="utf-8",
    )
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
            str(tmp_path / "ledger-r4.db"),
            "--risk-class",
            "R4",
        ],
    )
    assert result.exit_code == 1
    combined = (result.stderr or "") + (result.stdout or "")
    assert "ACCEPT" in combined or "ADR" in combined or "R4" in combined


def test_doctor_adr_0003_active_check() -> None:
    """Doctor surfaces ADR 0003 as active (R3/R4 ACCEPT refused)."""
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["adr_0003"]["active"] is True
    assert payload["adr_0003"]["can_record_acceptance"]["R3"] is False
    assert payload["adr_0003"]["can_record_acceptance"]["R4"] is False
