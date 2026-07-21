"""Acceptance aggregation state machine (CLOSURE-023).

``ARTIFACT_ACCEPTED`` is emitted only through this module — never from a
single undifferentiated review decision for multi-dimension flags.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from lpe.ledger.events import (
    AcceptanceAggregatedPayload,
    EventTypeV2,
    ExpertTimePayload,
    ReviewAttestationPayload,
    UtilityEventV2,
)
from lpe.ledger.store import LedgerStore
from lpe.models import RiskClass
from lpe.review.models import ReviewAttestationV2
from lpe.review.quorum import evaluate_quorum


class AcceptanceError(ValueError):
    """Raised when acceptance aggregation is refused."""


def attestation_to_payload(attestation: ReviewAttestationV2) -> ReviewAttestationPayload:
    return ReviewAttestationPayload(
        attestation_id=attestation.attestation_id,
        packet_id=attestation.packet_id,
        evidence_fingerprint=attestation.evidence_fingerprint,
        reviewer_id=attestation.reviewer_id,
        reviewer_role=attestation.reviewer_role,
        dimension=attestation.dimension.value,
        decision=attestation.decision,
        confidence=attestation.confidence,
        conflict_declaration_hash=attestation.conflict_declaration_hash,
        finding_refs=list(attestation.finding_refs),
    )


def build_acceptance_event(
    *,
    event_id: str,
    project_id: str,
    artifact_id: str,
    actor_id: str,
    risk_class: RiskClass,
    attestations: list[ReviewAttestationV2],
    evidence_fingerprint: str,
    obligation_ids: list[str] | None = None,
    require_semantic_for_r2: bool = False,
    protocol_freeze_id: str | None = None,
) -> UtilityEventV2:
    """Build ``ARTIFACT_ACCEPTED`` only when quorum is satisfied."""
    evaluation = evaluate_quorum(
        risk_class,
        attestations,
        evidence_fingerprint=evidence_fingerprint,
        require_semantic_for_r2=require_semantic_for_r2,
    )
    if not evaluation.satisfied:
        raise AcceptanceError("quorum not satisfied: " + "; ".join(evaluation.blocking_reasons))
    if risk_class in {RiskClass.R3, RiskClass.R4} and evaluation.policy.allow_auto_accept:
        raise AcceptanceError("R3/R4 auto-accept is impossible")

    now = datetime.now(UTC)
    payload = AcceptanceAggregatedPayload(
        attestation_ids=list(evaluation.matched_attestation_ids),
        quorum_policy_id=evaluation.policy.policy_id,
        evidence_fingerprint=evidence_fingerprint,
        semantic_fidelity=evaluation.semantic_fidelity,
        repository_accepted=evaluation.repository_accepted,
        implementation_accepted=evaluation.implementation_accepted,
        accepted_obligation_ids=list(obligation_ids or []),
        accepted_at=now,
        risk_class=risk_class.value,
    )
    return UtilityEventV2(
        event_id=event_id,
        event_type=EventTypeV2.ARTIFACT_ACCEPTED,
        project_id=project_id,
        artifact_id=artifact_id,
        obligation_ids=list(obligation_ids or []),
        actor_id=actor_id,
        protocol_freeze_id=protocol_freeze_id,
        payload=payload,
    )


def record_attestation_event(
    store: LedgerStore,
    attestation: ReviewAttestationV2,
    *,
    project_id: str,
    artifact_id: str | None = None,
    obligation_ids: list[str] | None = None,
) -> str:
    """Append a single-dimension REVIEW_ATTESTED event (no multi-flag ACCEPT)."""
    from lpe.ledger.store import LedgerTransitionError
    from lpe.models import EventType, UtilityEvent

    event = UtilityEventV2(
        event_id=f"event_attest_{attestation.attestation_id}",
        event_type=EventTypeV2.REVIEW_ATTESTED,
        project_id=project_id,
        artifact_id=artifact_id or attestation.packet_id,
        obligation_ids=list(obligation_ids or []),
        actor_id=attestation.reviewer_id,
        payload=attestation_to_payload(attestation),
    )
    try:
        digest = store.append_v2(event)
        time_event = UtilityEventV2(
            event_id=f"event_attest_{attestation.attestation_id}_time",
            event_type=EventTypeV2.EXPERT_TIME_RECORDED,
            project_id=project_id,
            artifact_id=event.artifact_id,
            obligation_ids=list(obligation_ids or []),
            actor_id=attestation.reviewer_id,
            payload=ExpertTimePayload(
                hours=attestation.review_minutes / 60.0,
                minutes=attestation.review_minutes,
                category="review",
                evidence_fingerprint=attestation.evidence_fingerprint,
            ),
        )
        store.append_v2(time_event)
        return digest
    except LedgerTransitionError:
        # Dimension attestation without a primed V2 lifecycle: legacy submit event.
        legacy = UtilityEvent(
            event_id=event.event_id,
            event_type=EventType.REVIEW_SUBMITTED,
            project_id=project_id,
            artifact_id=event.artifact_id,
            obligation_id=(obligation_ids[0] if obligation_ids else None),
            actor_id=attestation.reviewer_id,
            payload={
                **attestation_to_payload(attestation).model_dump(mode="json"),
                "multi_dimension_auto_attest": False,
            },
        )
        digest = store.append(legacy)
        store.append(
            UtilityEvent(
                event_id=f"{event.event_id}_time",
                event_type=EventType.EXPERT_TIME_RECORDED,
                project_id=project_id,
                artifact_id=event.artifact_id,
                actor_id=attestation.reviewer_id,
                payload={
                    "hours": attestation.review_minutes / 60.0,
                    "minutes": attestation.review_minutes,
                    "category": "review",
                    "evidence_fingerprint": attestation.evidence_fingerprint,
                },
            )
        )
        return digest


def aggregate_and_record_acceptance(
    ledger_path: Path,
    *,
    project_id: str,
    artifact_id: str,
    actor_id: str,
    risk_class: RiskClass,
    attestations: list[ReviewAttestationV2],
    evidence_fingerprint: str,
    obligation_ids: list[str] | None = None,
    event_id: str | None = None,
    require_semantic_for_r2: bool = False,
) -> str:
    """Run quorum evaluation and append ARTIFACT_ACCEPTED when satisfied."""
    from lpe.ledger.store import LedgerTransitionError
    from lpe.models import EventType, UtilityEvent

    if risk_class in {RiskClass.R3, RiskClass.R4} and len(attestations) < 2:
        raise AcceptanceError(
            f"{risk_class.value} acceptance requires multi-attestation quorum "
            "(single-reviewer ACCEPT is refused; ADR 0003)"
        )
    store = LedgerStore(ledger_path)
    if not ledger_path.exists():
        store.initialize()
    event = build_acceptance_event(
        event_id=event_id or f"event_accept_{artifact_id}",
        project_id=project_id,
        artifact_id=artifact_id,
        actor_id=actor_id,
        risk_class=risk_class,
        attestations=attestations,
        evidence_fingerprint=evidence_fingerprint,
        obligation_ids=obligation_ids,
        require_semantic_for_r2=require_semantic_for_r2,
    )
    try:
        return store.append_v2(event)
    except LedgerTransitionError:
        # Quorum already validated; allow legacy-shaped append when the artifact
        # lacks a typed V2 lifecycle prefix (mixed/migrating ledgers).
        legacy = UtilityEvent(
            event_id=event.event_id,
            event_type=EventType.ARTIFACT_ACCEPTED,
            project_id=project_id,
            artifact_id=artifact_id,
            obligation_id=(obligation_ids[0] if obligation_ids else None),
            actor_id=actor_id,
            payload=event.payload_dict(),
        )
        return store.append(legacy)
