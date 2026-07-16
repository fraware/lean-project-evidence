from __future__ import annotations

from lpe.models import ProjectContract, ReviewDecision, ReviewDecisionValue, RiskClass


class AuthorityError(ValueError):
    pass


def required_roles_for_risk(contract: ProjectContract, risk_class: RiskClass) -> list[str]:
    return list(contract.policies.risk_rules[risk_class].required_roles)


def _authority_roles(
    contract: ProjectContract, reviewer_id: str
) -> set[str] | None:
    """Return roles granted to reviewer_id by review.yaml, or None if unknown."""
    for authority in contract.review.authorities:
        if authority.reviewer_id == reviewer_id:
            return set(authority.roles)
    return None


def validate_reviewer_authority(
    contract: ProjectContract,
    *,
    reviewer_id: str,
    reviewer_roles: list[str] | None = None,
    risk_class: RiskClass,
) -> None:
    """Ensure reviewer is authorized by review.yaml for the candidate risk class.

    Self-declared ``reviewer_roles`` from decision JSON are ignored as a source of
    truth. Only roles listed for ``reviewer_id`` in ``review.yaml`` count.
    """
    del reviewer_roles  # never trusted; kept for call-site compatibility

    required = set(required_roles_for_risk(contract, risk_class))
    if not required:
        return

    held = _authority_roles(contract, reviewer_id)
    if held is None:
        raise AuthorityError(
            f"reviewer {reviewer_id!r} is not listed in review.yaml authorities"
        )

    missing = required - held
    if missing:
        raise AuthorityError(
            f"reviewer {reviewer_id!r} lacks required roles for {risk_class.value}: "
            f"{sorted(missing)} (roles are taken only from review.yaml, not decision JSON)"
        )


def validate_decision_for_risk(
    decision: ReviewDecision,
    risk_class: RiskClass,
) -> None:
    """R3/R4 cannot be auto-accepted via indeterminate bypass."""
    if risk_class not in {RiskClass.R3, RiskClass.R4}:
        return
    if decision.decision is ReviewDecisionValue.ACCEPT and decision.confidence < 80:
        raise AuthorityError(
            f"{risk_class.value} acceptance requires confidence >= 80; got {decision.confidence}"
        )


def can_record_acceptance(risk_class: RiskClass) -> bool:
    """ADR 0003: R3/R4 never auto-accept; v0 refuses recording ACCEPT for them.

    Human ACCEPT for R3/R4 requires a future multi-authority protocol. Until then,
    fail closed: only R0–R2 ACCEPT decisions may be recorded via ``lpe review record``.
    """
    return risk_class not in {RiskClass.R3, RiskClass.R4}
