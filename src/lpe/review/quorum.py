"""R0-R4 quorum policies (CLOSURE-023)."""

from __future__ import annotations

from dataclasses import dataclass

from lpe.models import ReviewDecisionValue, RiskClass
from lpe.review.models import (
    QuorumPolicy,
    QuorumRequirement,
    ReviewAttestationV2,
    ReviewDimension,
)


class QuorumError(ValueError):
    """Raised when attestations do not satisfy the risk-class quorum."""


def quorum_policy_for_risk(risk_class: RiskClass) -> QuorumPolicy:
    """Return the frozen quorum policy for ``risk_class`` (§12.4)."""
    if risk_class is RiskClass.R0:
        return QuorumPolicy(
            policy_id="quorum.r0.auto",
            risk_class=risk_class.value,
            requirements=[],
            require_distinct_reviewers=False,
            allow_auto_accept=True,
        )
    if risk_class is RiskClass.R1:
        return QuorumPolicy(
            policy_id="quorum.r1.implementation",
            risk_class=risk_class.value,
            requirements=[
                QuorumRequirement(
                    dimension=ReviewDimension.IMPLEMENTATION_QUALITY,
                    reviewer_role="lean-engineer",
                )
            ],
        )
    if risk_class is RiskClass.R2:
        return QuorumPolicy(
            policy_id="quorum.r2.repository",
            risk_class=risk_class.value,
            requirements=[
                QuorumRequirement(
                    dimension=ReviewDimension.REPOSITORY_FIT,
                    reviewer_role="repository-maintainer",
                )
            ],
        )
    if risk_class is RiskClass.R3:
        return QuorumPolicy(
            policy_id="quorum.r3.semantic_repository",
            risk_class=risk_class.value,
            requirements=[
                QuorumRequirement(
                    dimension=ReviewDimension.SEMANTIC_FIDELITY,
                    reviewer_role="domain-lead",
                ),
                QuorumRequirement(
                    dimension=ReviewDimension.REPOSITORY_FIT,
                    reviewer_role="repository-maintainer",
                ),
            ],
        )
    if risk_class is RiskClass.R4:
        return QuorumPolicy(
            policy_id="quorum.r4.triple",
            risk_class=risk_class.value,
            requirements=[
                QuorumRequirement(
                    dimension=ReviewDimension.SEMANTIC_FIDELITY,
                    reviewer_role="domain-lead",
                ),
                QuorumRequirement(
                    dimension=ReviewDimension.REPOSITORY_FIT,
                    reviewer_role="architecture-maintainer",
                ),
                QuorumRequirement(
                    dimension=ReviewDimension.IMPLEMENTATION_QUALITY,
                    reviewer_role="lean-engineer",
                ),
            ],
        )
    raise QuorumError(f"unsupported risk class {risk_class!r}")


@dataclass(frozen=True)
class QuorumEvaluation:
    satisfied: bool
    policy: QuorumPolicy
    blocking_reasons: tuple[str, ...]
    matched_attestation_ids: tuple[str, ...]
    semantic_fidelity: bool
    repository_accepted: bool
    implementation_accepted: bool


def evaluate_quorum(
    risk_class: RiskClass,
    attestations: list[ReviewAttestationV2],
    *,
    evidence_fingerprint: str,
    require_semantic_for_r2: bool = False,
) -> QuorumEvaluation:
    """Evaluate whether attestations satisfy quorum for ``risk_class``.

    Any REJECT blocks. REQUEST_REPAIR / INDETERMINATE block acceptance.
    R3/R4 never auto-accept (``allow_auto_accept`` is false).
    """
    policy = quorum_policy_for_risk(risk_class)
    reasons: list[str] = []

    if risk_class in {RiskClass.R3, RiskClass.R4} and policy.allow_auto_accept:
        reasons.append("R3/R4 auto-accept is impossible")

    # Global disagreement rules.
    for att in attestations:
        if att.decision is ReviewDecisionValue.REJECT:
            reasons.append(f"REJECT from {att.attestation_id} blocks acceptance")
        elif att.decision is ReviewDecisionValue.REQUEST_REPAIR:
            reasons.append(f"REQUEST_REPAIR from {att.attestation_id} requires repair")
        elif att.decision is ReviewDecisionValue.INDETERMINATE:
            reasons.append(
                f"INDETERMINATE from {att.attestation_id} blocks until evidence/adjudication"
            )

    # Fingerprint consistency for accepting attestations.
    accept_atts = [a for a in attestations if a.decision is ReviewDecisionValue.ACCEPT]
    for att in accept_atts:
        if att.evidence_fingerprint != evidence_fingerprint:
            reasons.append(
                f"attestation {att.attestation_id} fingerprint mismatch "
                f"(expected {evidence_fingerprint})"
            )

    matched: list[str] = []
    used_reviewers: set[str] = set()

    if policy.allow_auto_accept and risk_class is RiskClass.R0:
        # R0: no human attestations required when hard gates already passed upstream.
        return QuorumEvaluation(
            satisfied=not reasons,
            policy=policy,
            blocking_reasons=tuple(reasons),
            matched_attestation_ids=tuple(matched),
            semantic_fidelity=True,
            repository_accepted=True,
            implementation_accepted=True,
        )

    requirements = list(policy.requirements)
    if risk_class is RiskClass.R2 and require_semantic_for_r2:
        requirements.append(
            QuorumRequirement(
                dimension=ReviewDimension.SEMANTIC_FIDELITY,
                reviewer_role="domain-lead",
            )
        )

    remaining = list(accept_atts)
    for req in requirements:
        found: ReviewAttestationV2 | None = None
        for att in remaining:
            if att.dimension is not req.dimension:
                continue
            if att.reviewer_role != req.reviewer_role:
                continue
            if policy.require_distinct_reviewers and att.reviewer_id in used_reviewers:
                continue
            found = att
            break
        if found is None:
            reasons.append(f"missing {req.dimension.value}=ACCEPT from role {req.reviewer_role!r}")
        else:
            matched.append(found.attestation_id)
            used_reviewers.add(found.reviewer_id)
            remaining.remove(found)

    if policy.require_distinct_reviewers and len(used_reviewers) < len([r for r in requirements]):
        # Distinctness already enforced during matching; double-check count.
        if len(matched) == len(requirements) and len(used_reviewers) < len(requirements):
            reasons.append("quorum requires distinct reviewers")

    semantic = any(
        a.dimension is ReviewDimension.SEMANTIC_FIDELITY
        and a.decision is ReviewDecisionValue.ACCEPT
        and a.attestation_id in matched
        for a in attestations
    )
    repository = any(
        a.dimension is ReviewDimension.REPOSITORY_FIT
        and a.decision is ReviewDecisionValue.ACCEPT
        and a.attestation_id in matched
        for a in attestations
    )
    implementation = any(
        a.dimension is ReviewDimension.IMPLEMENTATION_QUALITY
        and a.decision is ReviewDecisionValue.ACCEPT
        and a.attestation_id in matched
        for a in attestations
    )

    # R1 sets implementation; TPPR aggregate still needs fidelity flags from policy.
    if risk_class is RiskClass.R1 and implementation and not reasons:
        semantic = True
        repository = True
    if risk_class is RiskClass.R2 and repository and not reasons:
        if not require_semantic_for_r2:
            semantic = True
        implementation = True

    satisfied = not reasons and len(matched) >= len(requirements)
    return QuorumEvaluation(
        satisfied=satisfied,
        policy=policy,
        blocking_reasons=tuple(reasons),
        matched_attestation_ids=tuple(matched),
        semantic_fidelity=semantic if satisfied else False,
        repository_accepted=repository if satisfied else False,
        implementation_accepted=implementation if satisfied else False,
    )
