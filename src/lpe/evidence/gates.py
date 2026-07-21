from __future__ import annotations

from dataclasses import dataclass, field

from lpe.models import (
    EvidenceFinding,
    FindingStatus,
    Recommendation,
    RiskClass,
)


@dataclass(frozen=True)
class GateDecision:
    """Hard-gate decision with explicit failure vs unresolved split (AUDIT-020).

    ``hard_gate_passed`` is True only when every hard-relevant check is PASS
    (or NOT_APPLICABLE). UNKNOWN on a hard-relevant check does **not** count as
    axiom-safe / hard-gate success — it yields ``hard_gate_passed=False`` with
    an ESCALATE recommendation.
    """

    hard_gate_passed: bool
    recommendation: Recommendation
    reasons: list[str]
    uncertainty: list[str]
    hard_failures: list[str] = field(default_factory=list)
    unresolved_hard_checks: list[str] = field(default_factory=list)


HARD_FAIL_CHECKS = {
    "contract.valid",
    "candidate.obligations",
    "lean.build",
    "lean.placeholders",
    "lean.prohibited_axioms",
    "repository.changed_paths",
}


def decide(
    findings: list[EvidenceFinding],
    risk_class: RiskClass,
    auto_accept_eligible: bool,
) -> GateDecision:
    hard_failures = [
        finding
        for finding in findings
        if finding.check_id in HARD_FAIL_CHECKS and finding.status is FindingStatus.FAIL
    ]
    if hard_failures:
        return GateDecision(
            hard_gate_passed=False,
            recommendation=Recommendation.REJECT,
            reasons=[
                "hard gate failures: " + "; ".join(finding.summary for finding in hard_failures)
            ],
            uncertainty=[],
            hard_failures=[finding.check_id for finding in hard_failures],
            unresolved_hard_checks=[],
        )

    unresolved_hard = [
        finding
        for finding in findings
        if finding.check_id in HARD_FAIL_CHECKS and finding.status is FindingStatus.UNKNOWN
    ]
    unknown = [finding.summary for finding in findings if finding.status is FindingStatus.UNKNOWN]

    # AUDIT-020: unresolved hard-relevant checks must not imply hard_gate_passed.
    if unresolved_hard:
        unresolved_ids = [finding.check_id for finding in unresolved_hard]
        return GateDecision(
            hard_gate_passed=False,
            recommendation=Recommendation.ESCALATE,
            reasons=[
                "hard-relevant checks unresolved (not axiom-safe): " + ", ".join(unresolved_ids)
            ],
            uncertainty=unknown,
            hard_failures=[],
            unresolved_hard_checks=unresolved_ids,
        )

    if risk_class in {RiskClass.R3, RiskClass.R4}:
        return GateDecision(
            hard_gate_passed=True,
            recommendation=Recommendation.ESCALATE,
            reasons=[f"{risk_class.value} artifacts require authorized human acceptance"],
            uncertainty=unknown,
            hard_failures=[],
            unresolved_hard_checks=[],
        )

    if unknown:
        return GateDecision(
            hard_gate_passed=True,
            recommendation=Recommendation.ESCALATE,
            reasons=["required evidence remains unresolved"],
            uncertainty=unknown,
            hard_failures=[],
            unresolved_hard_checks=[],
        )

    if auto_accept_eligible:
        return GateDecision(
            hard_gate_passed=True,
            recommendation=Recommendation.ACCEPT,
            reasons=["all deterministic gates passed and policy permits automatic acceptance"],
            uncertainty=[],
            hard_failures=[],
            unresolved_hard_checks=[],
        )

    return GateDecision(
        hard_gate_passed=True,
        recommendation=Recommendation.ESCALATE,
        reasons=["project policy requires human review"],
        uncertainty=[],
        hard_failures=[],
        unresolved_hard_checks=[],
    )
