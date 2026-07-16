from __future__ import annotations

from lpe.evidence.gates import decide
from lpe.models import (
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    Recommendation,
    RiskClass,
    Severity,
)
from lpe.models import Provenance
from datetime import datetime, timezone


def _pass_finding(check_id: str) -> EvidenceFinding:
    now = datetime.now(timezone.utc)
    return EvidenceFinding(
        finding_id=f"f_{check_id}",
        check_id=check_id,
        check_version="0.1.0",
        dimension=EvidenceDimension.KERNEL,
        status=FindingStatus.PASS,
        severity=Severity.INFO,
        summary="ok",
        provenance=Provenance(
            tool="t",
            tool_version="0",
            input_hash="x",
            started_at=now,
            finished_at=now,
            elapsed_ms=0,
        ),
    )


def test_hard_fail_rejects_with_reasons() -> None:
    now = datetime.now(timezone.utc)
    fail = EvidenceFinding(
        finding_id="f_fail",
        check_id="lean.placeholders",
        check_version="0.1.0",
        dimension=EvidenceDimension.KERNEL,
        status=FindingStatus.FAIL,
        severity=Severity.L3,
        summary="Prohibited tokens found: ['sorry']",
        provenance=Provenance(
            tool="t",
            tool_version="0",
            input_hash="x",
            started_at=now,
            finished_at=now,
            elapsed_ms=0,
        ),
    )
    decision = decide(
        findings=[fail],
        risk_class=RiskClass.R0,
        auto_accept_eligible=True,
    )
    assert decision.recommendation is Recommendation.REJECT
    assert decision.hard_gate_passed is False


def test_r3_never_auto_accepts_even_without_unknown() -> None:
    findings = [
        _pass_finding("contract.valid"),
        _pass_finding("candidate.obligations"),
        _pass_finding("lean.build"),
        _pass_finding("lean.placeholders"),
        _pass_finding("lean.prohibited_axioms"),
        _pass_finding("repository.changed_paths"),
    ]
    decision = decide(findings=findings, risk_class=RiskClass.R3, auto_accept_eligible=False)
    assert decision.recommendation is Recommendation.ESCALATE


def test_gates_unknown_hard_check_escalates_without_passing() -> None:
    now = datetime.now(timezone.utc)
    unknown_axiom = EvidenceFinding(
        finding_id="f_unknown",
        check_id="lean.prohibited_axioms",
        check_version="0.1.0",
        dimension=EvidenceDimension.KERNEL,
        status=FindingStatus.UNKNOWN,
        severity=Severity.L3,
        summary="Axiom closure incomplete",
        provenance=Provenance(
            tool="t",
            tool_version="0",
            input_hash="x",
            started_at=now,
            finished_at=now,
            elapsed_ms=0,
        ),
    )
    decision = decide(
        findings=[
            _pass_finding("contract.valid"),
            _pass_finding("candidate.obligations"),
            _pass_finding("lean.build"),
            _pass_finding("lean.placeholders"),
            unknown_axiom,
            _pass_finding("repository.changed_paths"),
        ],
        risk_class=RiskClass.R0,
        auto_accept_eligible=True,
    )
    assert decision.hard_gate_passed is False
    assert decision.recommendation is Recommendation.ESCALATE
    assert "lean.prohibited_axioms" in decision.unresolved_hard_checks


def test_r0_auto_accept_when_no_unknown() -> None:
    findings = [
        _pass_finding("contract.valid"),
        _pass_finding("candidate.obligations"),
        _pass_finding("lean.build"),
        _pass_finding("lean.placeholders"),
        _pass_finding("lean.prohibited_axioms"),
        _pass_finding("repository.changed_paths"),
    ]
    decision = decide(findings=findings, risk_class=RiskClass.R0, auto_accept_eligible=True)
    assert decision.recommendation is Recommendation.ACCEPT
    assert decision.hard_gate_passed is True

