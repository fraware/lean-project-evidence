"""Durable pilot warehouse backed by the append-only utility ledger.

Instrumentation only: records candidate outcomes, expert time, condition tags,
and overhead snapshots as hash-chained ledger events. Prefer existing
``EventType`` values with carefully versioned payloads.

Does **not** clear ENGINEERING_SPEC §21, authorize causal claims, or grant
production ACCEPT authority for R3/R4 (ADR 0003).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lpe.ids import new_id
from lpe.ledger.store import LedgerStore, validate_ledger_actor
from lpe.models import EventType, UtilityEvent
from lpe.pilot.overhead import OverheadReport
from lpe.review.decisions import expert_time_event

# Versioned payload marker for pilot warehouse events (not a new EventType).
PILOT_PAYLOAD_SCHEMA = "pilot.warehouse.v1"
PILOT_SOURCE = "pilot_warehouse"

# Expert-time categories that contribute to TPPR (must match metrics.tppr).
TPPR_TIME_CATEGORIES = frozenset(
    {"specification", "review", "repair", "integration"}
)

# Overhead snapshots use a non-TPPR category so compute_tppr lists them in
# exclusions rather than silently inflating the denominator.
OVERHEAD_CATEGORY = "overhead_snapshot"


@dataclass(frozen=True)
class PilotRecordResult:
    """Result of a durable pilot append."""

    event_id: str
    event_hash: str
    event_type: EventType


class PilotWarehouse:
    """Append-only pilot instrumentation stored in ``LedgerStore``.

    Every mutator writes a ledger event immediately. A fresh ``LedgerStore``
    instance on the same path sees prior events (process-restart durable).
    Anonymous ``actor_id`` values fail closed via ledger auth (AUDIT-017).
    """

    def __init__(
        self,
        store: LedgerStore,
        *,
        actor_id: str,
        project_id: str,
    ) -> None:
        self.store = store
        self.actor_id = validate_ledger_actor(actor_id)
        self.project_id = project_id
        self.store.initialize()

    def _base_payload(self, **fields: Any) -> dict[str, Any]:
        return {
            "pilot_schema": PILOT_PAYLOAD_SCHEMA,
            "source": PILOT_SOURCE,
            "durable": True,
            "section_21_cleared": False,
            "causal_claims": False,
            **fields,
        }

    def register_candidate(
        self,
        *,
        candidate_id: str,
        obligation_ids: list[str],
        condition_tag: str,
        packet_automated: bool = False,
        reproduction_exact: bool | None = None,
    ) -> PilotRecordResult:
        """Append ``CANDIDATE_REGISTERED`` with pilot condition metadata."""
        event = UtilityEvent(
            event_id=new_id("evt"),
            event_type=EventType.CANDIDATE_REGISTERED,
            project_id=self.project_id,
            artifact_id=candidate_id,
            obligation_id=obligation_ids[0] if obligation_ids else None,
            actor_id=self.actor_id,
            payload=self._base_payload(
                kind="candidate_registered",
                obligation_ids=list(obligation_ids),
                condition_tag=condition_tag,
                packet_automated=packet_automated,
                reproduction_exact=reproduction_exact,
            ),
        )
        digest = self.store.append(event)
        return PilotRecordResult(
            event_id=event.event_id,
            event_hash=digest,
            event_type=event.event_type,
        )

    def record_expert_time(
        self,
        *,
        candidate_id: str,
        category: str,
        minutes: float,
        condition_tag: str,
    ) -> PilotRecordResult:
        """Append ``EXPERT_TIME_RECORDED`` (hours + minutes; TPPR-compatible)."""
        if minutes <= 0:
            raise ValueError("expert-time minutes must be positive")
        # Build via expert_time_event for TPPR contract, then attach warehouse markers.
        base = expert_time_event(
            event_id=new_id("evt"),
            project_id=self.project_id,
            artifact_id=candidate_id,
            actor_id=self.actor_id,
            minutes=minutes,
            category=category,
            condition_tag=condition_tag,
        )
        payload = self._base_payload(kind="expert_time")
        payload.update(base.payload)
        event = base.model_copy(update={"payload": payload})
        digest = self.store.append(event)
        return PilotRecordResult(
            event_id=event.event_id,
            event_hash=digest,
            event_type=event.event_type,
        )

    def mark_packet_automated(
        self,
        *,
        candidate_id: str,
        condition_tag: str,
        recommendation: str | None = None,
        risk_class: str | None = None,
        hard_gate_passed: bool | None = None,
    ) -> PilotRecordResult:
        """Append ``EVIDENCE_COMPILED`` marking automated packet construction."""
        event = UtilityEvent(
            event_id=new_id("evt"),
            event_type=EventType.EVIDENCE_COMPILED,
            project_id=self.project_id,
            artifact_id=candidate_id,
            actor_id=self.actor_id,
            payload=self._base_payload(
                kind="packet_automated",
                packet_automated=True,
                condition_tag=condition_tag,
                recommendation=recommendation,
                risk_class=risk_class,
                hard_gate_passed=hard_gate_passed,
            ),
        )
        digest = self.store.append(event)
        return PilotRecordResult(
            event_id=event.event_id,
            event_hash=digest,
            event_type=event.event_type,
        )

    def record_overhead_snapshot(
        self,
        *,
        artifact_id: str,
        report: OverheadReport,
        condition_tag: str | None = None,
        note: str | None = None,
    ) -> PilotRecordResult:
        """Append overhead as ``EXPERT_TIME_RECORDED`` with non-TPPR category.

        Uses ``overhead_snapshot`` so ``compute_tppr`` excludes it from the
        expert-hours denominator (listed in ``exclusions``).
        """
        # Store instrumented wall delta as minutes for audit; TPPR ignores category.
        delta_minutes = max(
            0.0, report.instrumented_minutes - report.baseline_minutes
        )
        event = UtilityEvent(
            event_id=new_id("evt"),
            event_type=EventType.EXPERT_TIME_RECORDED,
            project_id=self.project_id,
            artifact_id=artifact_id,
            actor_id=self.actor_id,
            payload=self._base_payload(
                kind="overhead_snapshot",
                category=OVERHEAD_CATEGORY,
                hours=delta_minutes / 60.0,
                minutes=delta_minutes,
                condition_tag=condition_tag,
                baseline_minutes=report.baseline_minutes,
                instrumented_minutes=report.instrumented_minutes,
                overhead_fraction=report.overhead_fraction,
                within_budget=report.within_budget,
                note=note
                or (
                    "Software overhead proxy only; not field expert-time measurement "
                    "and not §21 clearance."
                ),
            ),
        )
        digest = self.store.append(event)
        return PilotRecordResult(
            event_id=event.event_id,
            event_hash=digest,
            event_type=event.event_type,
        )

    def record_outcome(
        self,
        *,
        candidate_id: str,
        condition_tag: str,
        decision: str,
        reproduction_exact: bool | None = None,
        notes: str | None = None,
    ) -> PilotRecordResult:
        """Append ``REVIEW_SUBMITTED`` as a pilot outcome marker (not ACCEPT authority).

        Prefer the normal ``lpe review record`` path for authoritative decisions.
        This records a durable pilot-tagged outcome for warehouse summaries.
        """
        event = UtilityEvent(
            event_id=new_id("evt"),
            event_type=EventType.REVIEW_SUBMITTED,
            project_id=self.project_id,
            artifact_id=candidate_id,
            actor_id=self.actor_id,
            payload=self._base_payload(
                kind="pilot_outcome",
                condition_tag=condition_tag,
                decision=decision,
                reproduction_exact=reproduction_exact,
                notes=notes,
                authority="pilot_warehouse_marker",
            ),
        )
        digest = self.store.append(event)
        return PilotRecordResult(
            event_id=event.event_id,
            event_hash=digest,
            event_type=event.event_type,
        )
