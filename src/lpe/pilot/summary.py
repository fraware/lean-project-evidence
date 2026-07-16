"""Ledger-backed pilot summary aggregations (software metrics only).

Reads durable warehouse events from ``LedgerStore``. Distinguishes software
instrumentation metrics from causal / §21 claims (always false here).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from lpe.ledger.store import LedgerStore
from lpe.models import EventType, UtilityEvent
from lpe.pilot.warehouse import OVERHEAD_CATEGORY, PILOT_SOURCE


@dataclass
class ConditionBucket:
    condition_tag: str
    candidates: int = 0
    automated: int = 0
    expert_minutes: float = 0.0
    outcomes: dict[str, int] = field(default_factory=dict)


@dataclass
class PilotSummary:
    """Aggregated software metrics from the utility ledger.

    ``section_21_cleared`` and ``causal_claims`` are always False for honesty.
    """

    project_id: str
    candidate_count: int
    automated_count: int
    automation_rate: float
    expert_minutes_total: float
    expert_minutes_by_category: dict[str, float]
    expert_minutes_by_condition: dict[str, float]
    conditions: dict[str, ConditionBucket]
    overhead_snapshots: list[dict[str, Any]]
    reproduction_exact_count: int
    reproduction_known_count: int
    event_count: int
    section_21_cleared: bool = False
    causal_claims: bool = False
    metric_class: str = "software_instrumentation"
    note: str = (
        "Software metrics from durable ledger events only. "
        "Not a causal study and not ENGINEERING_SPEC §21 clearance."
    )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["conditions"] = {
            tag: asdict(bucket) for tag, bucket in self.conditions.items()
        }
        return payload


def _is_pilot_event(event: UtilityEvent) -> bool:
    return event.payload.get("source") == PILOT_SOURCE


def _minutes_from_payload(payload: dict[str, Any]) -> float | None:
    if "minutes" in payload:
        return float(payload["minutes"])
    if "hours" in payload:
        return float(payload["hours"]) * 60.0
    return None


def summarize_pilot(
    store: LedgerStore,
    *,
    project_id: str,
    pilot_events_only: bool = True,
) -> PilotSummary:
    """Aggregate pilot metrics from ledger events for ``project_id``.

    When ``pilot_events_only`` is True (default), only events tagged with
    ``source=pilot_warehouse`` contribute. Set False to include all project
    expert-time events (e.g. review-recorded minutes) in expert totals.
    """
    store.verify()
    events = store.events(project_id)
    if pilot_events_only:
        events = [e for e in events if _is_pilot_event(e)]

    # candidate_id -> latest known metadata
    candidates: dict[str, dict[str, Any]] = {}
    minutes_by_category: dict[str, float] = defaultdict(float)
    minutes_by_condition: dict[str, float] = defaultdict(float)
    outcomes_by_condition: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    overhead_snapshots: list[dict[str, Any]] = []
    reproduction_exact = 0
    reproduction_known = 0

    for event in events:
        payload = event.payload
        kind = payload.get("kind")
        tag = str(payload.get("condition_tag") or "untagged")
        cid = event.artifact_id

        if event.event_type is EventType.CANDIDATE_REGISTERED and (
            kind == "candidate_registered" or _is_pilot_event(event)
        ):
            prev = candidates.get(cid, {})
            candidates[cid] = {
                **prev,
                "condition_tag": tag,
                "packet_automated": bool(
                    payload.get("packet_automated") or prev.get("packet_automated")
                ),
                "reproduction_exact": payload.get(
                    "reproduction_exact", prev.get("reproduction_exact")
                ),
            }
            if payload.get("reproduction_exact") is not None:
                reproduction_known += 1
                if payload.get("reproduction_exact"):
                    reproduction_exact += 1

        elif event.event_type is EventType.EVIDENCE_COMPILED and (
            kind == "packet_automated" or payload.get("packet_automated")
        ):
            prev = candidates.get(cid, {})
            candidates[cid] = {
                **prev,
                "condition_tag": tag or prev.get("condition_tag", "untagged"),
                "packet_automated": True,
            }

        elif event.event_type is EventType.EXPERT_TIME_RECORDED:
            category = str(payload.get("category", ""))
            if category == OVERHEAD_CATEGORY or kind == "overhead_snapshot":
                overhead_snapshots.append(
                    {
                        "event_id": event.event_id,
                        "artifact_id": event.artifact_id,
                        "baseline_minutes": payload.get("baseline_minutes"),
                        "instrumented_minutes": payload.get("instrumented_minutes"),
                        "overhead_fraction": payload.get("overhead_fraction"),
                        "within_budget": payload.get("within_budget"),
                        "condition_tag": payload.get("condition_tag"),
                        "note": payload.get("note"),
                    }
                )
                continue
            minutes = _minutes_from_payload(payload)
            if minutes is None:
                continue
            minutes_by_category[category] += minutes
            minutes_by_condition[tag] += minutes

        elif event.event_type is EventType.REVIEW_SUBMITTED and kind == "pilot_outcome":
            decision = str(payload.get("decision", "UNKNOWN"))
            outcomes_by_condition[tag][decision] += 1
            if payload.get("reproduction_exact") is not None:
                reproduction_known += 1
                if payload.get("reproduction_exact"):
                    reproduction_exact += 1

    conditions: dict[str, ConditionBucket] = {}
    for cid, meta in candidates.items():
        tag = str(meta.get("condition_tag") or "untagged")
        if tag not in conditions:
            conditions[tag] = ConditionBucket(condition_tag=tag)
        conditions[tag].candidates += 1
        if meta.get("packet_automated"):
            conditions[tag].automated += 1

    for tag, minutes in minutes_by_condition.items():
        if tag not in conditions:
            conditions[tag] = ConditionBucket(condition_tag=tag)
        conditions[tag].expert_minutes = minutes

    for tag, outcomes in outcomes_by_condition.items():
        if tag not in conditions:
            conditions[tag] = ConditionBucket(condition_tag=tag)
        conditions[tag].outcomes = dict(outcomes)

    candidate_count = len(candidates)
    automated_count = sum(
        1 for meta in candidates.values() if meta.get("packet_automated")
    )
    automation_rate = (
        automated_count / candidate_count if candidate_count else 0.0
    )

    return PilotSummary(
        project_id=project_id,
        candidate_count=candidate_count,
        automated_count=automated_count,
        automation_rate=automation_rate,
        expert_minutes_total=sum(minutes_by_category.values()),
        expert_minutes_by_category=dict(minutes_by_category),
        expert_minutes_by_condition=dict(minutes_by_condition),
        conditions=conditions,
        overhead_snapshots=overhead_snapshots,
        reproduction_exact_count=reproduction_exact,
        reproduction_known_count=reproduction_known,
        event_count=len(events),
    )
