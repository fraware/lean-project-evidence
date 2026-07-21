from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lpe.ledger.store import LedgerStore


@dataclass
class PilotCandidate:
    candidate_id: str
    project_id: str
    obligation_ids: list[str]
    condition_tag: str
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    packet_automated: bool = False
    reproduction_exact: bool | None = None


@dataclass
class ExpertTimeEvent:
    candidate_id: str
    category: str
    minutes: float
    condition_tag: str
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class PilotInstrumentation:
    """In-memory scratch pad for pilot metrics (non-durable).

    Prefer ``PilotWarehouse`` for partner / dry-run instrumentation: every
    mutation appends to the utility ledger and survives process restart.
    This class remains for unit tests and ephemeral local scratch.

    Optional ``append_snapshot_to_ledger`` still exists for one-shot dumps of
    in-memory expert-time rows (legacy AUDIT-023 path).
    """

    def __init__(self) -> None:
        self.candidates: dict[str, PilotCandidate] = {}
        self.expert_time: list[ExpertTimeEvent] = []

    def register_candidate(
        self,
        *,
        candidate_id: str,
        project_id: str,
        obligation_ids: list[str],
        condition_tag: str,
    ) -> PilotCandidate:
        record = PilotCandidate(
            candidate_id=candidate_id,
            project_id=project_id,
            obligation_ids=obligation_ids,
            condition_tag=condition_tag,
        )
        self.candidates[candidate_id] = record
        return record

    def record_expert_time(
        self,
        *,
        candidate_id: str,
        category: str,
        minutes: float,
        condition_tag: str,
    ) -> ExpertTimeEvent:
        event = ExpertTimeEvent(
            candidate_id=candidate_id,
            category=category,
            minutes=minutes,
            condition_tag=condition_tag,
        )
        self.expert_time.append(event)
        return event

    def mark_packet_automated(self, candidate_id: str) -> None:
        self.candidates[candidate_id].packet_automated = True

    def total_expert_minutes(self, *, condition_tag: str | None = None) -> float:
        events = self.expert_time
        if condition_tag:
            events = [e for e in events if e.condition_tag == condition_tag]
        return sum(e.minutes for e in events)

    def automation_rate(self) -> float:
        if not self.candidates:
            return 0.0
        automated = sum(1 for c in self.candidates.values() if c.packet_automated)
        return automated / len(self.candidates)

    def append_snapshot_to_ledger(
        self,
        store: LedgerStore,
        *,
        actor_id: str,
        project_id: str,
    ) -> list[str]:
        """Legacy one-shot dump of in-memory expert-time rows.

        Prefer ``PilotWarehouse.record_expert_time`` for durable appends.
        Returns event hashes. Payload marks ``durable: false`` / snapshot source.
        """
        from lpe.ids import new_id
        from lpe.models import EventType, UtilityEvent

        digests: list[str] = []
        for event in self.expert_time:
            if event.candidate_id not in self.candidates:
                continue
            candidate = self.candidates[event.candidate_id]
            if candidate.project_id != project_id:
                continue
            digest = store.append(
                UtilityEvent(
                    event_id=new_id("evt"),
                    event_type=EventType.EXPERT_TIME_RECORDED,
                    project_id=project_id,
                    artifact_id=event.candidate_id,
                    actor_id=actor_id,
                    payload={
                        "category": event.category,
                        "hours": event.minutes / 60.0,
                        "minutes": event.minutes,
                        "condition_tag": event.condition_tag,
                        "source": "pilot_instrumentation_snapshot",
                        "durable": False,
                        "note": (
                            "Optional in-memory snapshot; prefer PilotWarehouse. "
                            "Not §21 science-gate clearance."
                        ),
                    },
                )
            )
            digests.append(digest)
        return digests
