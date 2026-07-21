"""Review decision recording — legacy single-decision path + dimension attestations."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpe.ledger.store import LedgerStore
from lpe.models import EventType, ReviewDecision, ReviewDecisionValue, RiskClass, UtilityEvent
from lpe.review.acceptance import (
    AcceptanceError,
    aggregate_and_record_acceptance,
    record_attestation_event,
)
from lpe.review.models import ReviewAttestationV2, ReviewDimension
from lpe.review.quorum import quorum_policy_for_risk


def review_decision_to_event(
    decision: ReviewDecision,
    *,
    project_id: str,
    obligation_id: str | None = None,
    evidence_fingerprint: str | None = None,
    ledger_seal_tip: str | None = None,
) -> UtilityEvent:
    """Legacy helper: build a single review event without dual fidelity flags.

    Individual review events must not set both ``semantic_fidelity`` and
    ``repository_accepted`` (§12.7). Those flags are reserved for
    ``AcceptanceAggregatedPayload`` via the quorum state machine.
    """
    event_type = (
        EventType.ARTIFACT_ACCEPTED
        if decision.decision.value == "ACCEPT"
        else EventType.ARTIFACT_REJECTED
        if decision.decision.value == "REJECT"
        else EventType.REVIEW_SUBMITTED
    )
    payload: dict[str, Any] = {
        "decision": decision.decision.value,
        "confidence": decision.confidence,
        "rationale": decision.rationale,
        "review_minutes": decision.review_minutes,
        "reviewer_roles": decision.reviewer_roles,
        "answer": decision.answer,
        "required_repair": decision.required_repair,
        # Explicit: single review must not auto-fill multi-dimension acceptance.
        "multi_dimension_auto_attest": False,
    }
    if evidence_fingerprint:
        payload["evidence_fingerprint"] = evidence_fingerprint
    if ledger_seal_tip:
        payload["ledger_seal_tip"] = ledger_seal_tip
    return UtilityEvent(
        event_id=f"event_{decision.review_id}",
        event_type=event_type,
        project_id=project_id,
        artifact_id=decision.packet_id,
        obligation_id=obligation_id,
        actor_id=decision.reviewer_id,
        payload=payload,
    )


def expert_time_event(
    *,
    event_id: str,
    project_id: str,
    artifact_id: str,
    actor_id: str,
    minutes: float,
    category: str,
    condition_tag: str | None = None,
) -> UtilityEvent:
    """Build an ``EXPERT_TIME_RECORDED`` event.

    TPPR denominators use ``hours`` (see ``docs/07_TPPR_SPEC.md``). Review decisions
    are authored in minutes; we convert and store both so ledger consumers stay honest.
    """
    payload: dict[str, Any] = {
        "hours": minutes / 60.0,
        "minutes": minutes,
        "category": category,
    }
    if condition_tag:
        payload["condition_tag"] = condition_tag
    return UtilityEvent(
        event_id=event_id,
        event_type=EventType.EXPERT_TIME_RECORDED,
        project_id=project_id,
        artifact_id=artifact_id,
        actor_id=actor_id,
        payload=payload,
    )


def _dimension_for_single_review(risk_class: RiskClass) -> ReviewDimension:
    policy = quorum_policy_for_risk(risk_class)
    if policy.requirements:
        return policy.requirements[0].dimension
    return ReviewDimension.IMPLEMENTATION_QUALITY


def _role_for_single_review(risk_class: RiskClass, decision: ReviewDecision) -> str:
    policy = quorum_policy_for_risk(risk_class)
    if policy.requirements:
        return policy.requirements[0].reviewer_role
    if decision.reviewer_roles:
        return decision.reviewer_roles[0]
    return "lean-engineer"


def decision_to_attestation(
    decision: ReviewDecision,
    *,
    risk_class: RiskClass,
    evidence_fingerprint: str,
    conflict_declaration_hash: str,
) -> ReviewAttestationV2:
    """Map a legacy ReviewDecision to exactly one dimension attestation."""
    now = datetime.now(UTC)
    return ReviewAttestationV2(
        attestation_id=f"attest_{decision.review_id}",
        packet_id=decision.packet_id,
        evidence_fingerprint=evidence_fingerprint,
        reviewer_id=decision.reviewer_id,
        reviewer_role=_role_for_single_review(risk_class, decision),
        dimension=_dimension_for_single_review(risk_class),
        decision=decision.decision,
        confidence=decision.confidence,
        rationale=decision.rationale,
        finding_refs=[],
        conflict_declaration_hash=conflict_declaration_hash,
        review_started_at=now,
        review_submitted_at=decision.submitted_at,
        review_minutes=decision.review_minutes,
    )


def record_review_decision(
    ledger_path: Path,
    decision: ReviewDecision,
    *,
    project_id: str,
    obligation_ids: list[str] | None = None,
    evidence_fingerprint: str | None = None,
    risk_class: RiskClass | None = None,
    conflict_declaration_hash: str | None = None,
) -> str:
    """Record a legacy review decision.

    ACCEPT for R0-R2 goes through quorum aggregation (single dimension -> aggregate
    with fidelity flags). R3/R4 ACCEPT must use ``aggregate_and_record_acceptance``
    with multiple attestations; this helper still records non-ACCEPT outcomes.
    """
    store = LedgerStore(ledger_path)
    if not ledger_path.exists():
        store.initialize()
    primary_obligation = obligation_ids[0] if obligation_ids else None
    fingerprint = evidence_fingerprint
    if fingerprint is None and decision.packet_id.startswith("packet_"):
        derived = decision.packet_id.removeprefix("packet_")
        if len(derived) == 64 and all(c in "0123456789abcdef" for c in derived):
            fingerprint = derived
    if fingerprint is None:
        fingerprint = f"legacy_{decision.packet_id}"

    # Non-ACCEPT (and R3/R4 paths that only record reject/repair): legacy event.
    if decision.decision is not ReviewDecisionValue.ACCEPT:
        event = review_decision_to_event(
            decision,
            project_id=project_id,
            obligation_id=primary_obligation,
            evidence_fingerprint=fingerprint,
        )
        digest = store.append(event)
        if obligation_ids and len(obligation_ids) > 1:
            for index, obligation_id in enumerate(obligation_ids[1:], start=1):
                linked = event.model_copy(
                    update={
                        "event_id": f"{event.event_id}_obl_{index}",
                        "obligation_id": obligation_id,
                    }
                )
                store.append(linked)
        time_event = expert_time_event(
            event_id=f"{event.event_id}_time",
            project_id=project_id,
            artifact_id=decision.packet_id,
            actor_id=decision.reviewer_id,
            minutes=decision.review_minutes,
            category="review",
        )
        if fingerprint:
            time_event = time_event.model_copy(
                update={
                    "payload": {
                        **time_event.payload,
                        "evidence_fingerprint": fingerprint,
                        "ledger_seal_tip": digest,
                    }
                }
            )
        store.append(time_event)
        return digest

    # ACCEPT: R0-R2 via single-dimension attestation + aggregate (sets TPPR flags).
    risk = risk_class or RiskClass.R1
    if risk in {RiskClass.R3, RiskClass.R4}:
        raise AcceptanceError(
            f"{risk.value} ACCEPT cannot be recorded via single-reviewer path; "
            "use dimension attestations + lpe review accept-quorum"
        )
    conflict_hash = conflict_declaration_hash or f"legacy_conflict_{decision.review_id}"
    attestation = decision_to_attestation(
        decision,
        risk_class=risk,
        evidence_fingerprint=fingerprint,
        conflict_declaration_hash=conflict_hash,
    )
    # Prefer legacy UtilityEvent path for R0-R2 so existing ledgers / TPPR keep
    # working without requiring a full V2 lifecycle prefix.
    event = review_decision_to_event(
        decision,
        project_id=project_id,
        obligation_id=primary_obligation,
        evidence_fingerprint=fingerprint,
    )
    # Promote to ARTIFACT_ACCEPTED with aggregate flags only (not on the attestation).
    from lpe.review.quorum import evaluate_quorum

    evaluation = evaluate_quorum(
        risk,
        [attestation],
        evidence_fingerprint=fingerprint,
    )
    if not evaluation.satisfied:
        raise AcceptanceError("quorum not satisfied: " + "; ".join(evaluation.blocking_reasons))
    event = event.model_copy(
        update={
            "payload": {
                **event.payload,
                "attestation_ids": list(evaluation.matched_attestation_ids),
                "quorum_policy_id": evaluation.policy.policy_id,
                "semantic_fidelity": evaluation.semantic_fidelity,
                "repository_accepted": evaluation.repository_accepted,
                "implementation_accepted": evaluation.implementation_accepted,
                "accepted_obligation_ids": list(obligation_ids or []),
                "aggregate_only": True,
            }
        }
    )
    digest = store.append(event)
    if obligation_ids and len(obligation_ids) > 1:
        for index, obligation_id in enumerate(obligation_ids[1:], start=1):
            linked = event.model_copy(
                update={
                    "event_id": f"{event.event_id}_obl_{index}",
                    "obligation_id": obligation_id,
                }
            )
            store.append(linked)
    time_event = expert_time_event(
        event_id=f"{event.event_id}_time",
        project_id=project_id,
        artifact_id=decision.packet_id,
        actor_id=decision.reviewer_id,
        minutes=decision.review_minutes,
        category="review",
    )
    time_event = time_event.model_copy(
        update={
            "payload": {
                **time_event.payload,
                "evidence_fingerprint": fingerprint,
                "ledger_seal_tip": digest,
            }
        }
    )
    store.append(time_event)
    return digest


# Re-export for callers that record V2 attestations directly.
__all__ = [
    "AcceptanceError",
    "aggregate_and_record_acceptance",
    "decision_to_attestation",
    "expert_time_event",
    "record_attestation_event",
    "record_review_decision",
    "review_decision_to_event",
]
