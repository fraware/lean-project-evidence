from __future__ import annotations

from pathlib import Path

from lpe.ledger.store import LedgerStore
from lpe.models import EventType, ReviewDecision, UtilityEvent


def review_decision_to_event(
    decision: ReviewDecision,
    *,
    project_id: str,
    obligation_id: str | None = None,
) -> UtilityEvent:
    event_type = (
        EventType.ARTIFACT_ACCEPTED
        if decision.decision.value == "ACCEPT"
        else EventType.ARTIFACT_REJECTED
        if decision.decision.value == "REJECT"
        else EventType.REVIEW_SUBMITTED
    )
    payload: dict = {
        "decision": decision.decision.value,
        "confidence": decision.confidence,
        "rationale": decision.rationale,
        "review_minutes": decision.review_minutes,
        "reviewer_roles": decision.reviewer_roles,
        "answer": decision.answer,
        "required_repair": decision.required_repair,
    }
    # Human ACCEPT is the attestation for TPPR acceptance flags (docs/07_TPPR_SPEC.md).
    if decision.decision.value == "ACCEPT":
        payload["semantic_fidelity"] = True
        payload["repository_accepted"] = True
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
    payload: dict = {
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


def record_review_decision(
    ledger_path: Path,
    decision: ReviewDecision,
    *,
    project_id: str,
    obligation_ids: list[str] | None = None,
) -> str:
    store = LedgerStore(ledger_path)
    if not ledger_path.exists():
        store.initialize()
    primary_obligation = obligation_ids[0] if obligation_ids else None
    event = review_decision_to_event(
        decision, project_id=project_id, obligation_id=primary_obligation
    )
    digest = store.append(event)
    # When multiple obligations are accepted, append linked ACCEPT events so TPPR
    # can credit each (same review_id suffix; hash-chained separately).
    if (
        decision.decision.value == "ACCEPT"
        and obligation_ids
        and len(obligation_ids) > 1
    ):
        for index, obligation_id in enumerate(obligation_ids[1:], start=1):
            linked = event.model_copy(
                update={
                    "event_id": f"{event.event_id}_obl_{index}",
                    "obligation_id": obligation_id,
                }
            )
            store.append(linked)
    store.append(
        expert_time_event(
            event_id=f"{event.event_id}_time",
            project_id=project_id,
            artifact_id=decision.packet_id,
            actor_id=decision.reviewer_id,
            minutes=decision.review_minutes,
            category="review",
        )
    )
    return digest
