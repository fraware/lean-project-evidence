"""Trusted Project Progress Rate (TPPR) aggregation.

Event semantics follow ``docs/07_TPPR_SPEC.md``:

- ``OBLIGATION_REGISTERED`` registers obligation weight before candidate work.
- ``ARTIFACT_ACCEPTED`` requires both ``semantic_fidelity`` and ``repository_accepted``.
- ``PERSISTENCE_CONFIRMED`` requires both ``downstream_enabled`` and
  ``remained_integrated`` before sustained credit is granted.
- ``EXPERT_TIME_RECORDED`` contributes denominator hours by category:
  specification, review, repair, integration.
- ``CORRECTION_RECORDED`` and unknown expert-time categories are listed in
  ``exclusions`` rather than silently adjusting totals.
- Accepted but not yet sustained obligations appear in
  ``pending_persistence_obligations``.
"""

from __future__ import annotations

from collections import defaultdict

from lpe.models import EventType, TPPRReport, UtilityEvent


TIME_CATEGORIES = {
    "specification": "specification_hours",
    "review": "review_hours",
    "repair": "repair_hours",
    "integration": "integration_hours",
}


def compute_tppr(events: list[UtilityEvent], project_id: str) -> TPPRReport:
    relevant = [event for event in events if event.project_id == project_id]
    weights: dict[str, float] = {}
    accepted: dict[str, bool] = defaultdict(bool)
    sustained: dict[str, bool] = defaultdict(bool)
    rejected: set[str] = set()
    hours = dict.fromkeys(TIME_CATEGORIES.values(), 0.0)
    compute_cost_usd = 0.0
    wall_clock_hours = 0.0
    exclusions: list[str] = []

    for event in relevant:
        obligation_id = event.obligation_id
        if event.event_type is EventType.OBLIGATION_REGISTERED and obligation_id:
            weights[obligation_id] = float(event.payload["weight"])
        elif event.event_type is EventType.ARTIFACT_ACCEPTED and obligation_id:
            accepted[obligation_id] = bool(
                event.payload.get("semantic_fidelity", False)
                and event.payload.get("repository_accepted", False)
            )
        elif event.event_type is EventType.ARTIFACT_REJECTED and obligation_id:
            rejected.add(obligation_id)
            accepted[obligation_id] = False
            sustained[obligation_id] = False
        elif event.event_type is EventType.PERSISTENCE_CONFIRMED and obligation_id:
            sustained[obligation_id] = bool(
                event.payload.get("downstream_enabled", False)
                and event.payload.get("remained_integrated", False)
            )
        elif event.event_type is EventType.EXPERT_TIME_RECORDED:
            category = str(event.payload["category"])
            if category not in TIME_CATEGORIES:
                exclusions.append(f"unknown expert time category in {event.event_id}")
                continue
            if "hours" in event.payload:
                hours_val = float(event.payload["hours"])
            elif "minutes" in event.payload:
                # Legacy / mis-keyed payloads: convert rather than KeyError.
                hours_val = float(event.payload["minutes"]) / 60.0
            else:
                exclusions.append(
                    f"expert time event {event.event_id} missing hours/minutes"
                )
                continue
            hours[TIME_CATEGORIES[category]] += hours_val
        elif event.event_type is EventType.CORRECTION_RECORDED:
            target = event.supersedes_event_id or "unknown"
            exclusions.append(
                f"correction {event.event_id} recorded for superseded event {target}"
            )

        compute_cost_usd += float(event.payload.get("compute_cost_usd", 0.0))
        wall_clock_hours += float(event.payload.get("wall_clock_hours", 0.0))

    credited = sorted(
        obligation_id
        for obligation_id, weight in weights.items()
        if weight > 0
        and accepted[obligation_id]
        and sustained[obligation_id]
        and obligation_id not in rejected
    )
    pending = sorted(
        obligation_id
        for obligation_id in weights
        if accepted[obligation_id] and not sustained[obligation_id]
    )
    numerator = sum(weights[obligation_id] for obligation_id in credited)
    expert_total = sum(hours.values())
    tppr = numerator / expert_total if expert_total > 0 else None

    return TPPRReport(
        project_id=project_id,
        weighted_accepted_sustained_obligations=numerator,
        specification_hours=hours["specification_hours"],
        review_hours=hours["review_hours"],
        repair_hours=hours["repair_hours"],
        integration_hours=hours["integration_hours"],
        expert_hours_total=expert_total,
        tppr=tppr,
        compute_cost_usd=compute_cost_usd,
        wall_clock_hours=wall_clock_hours,
        credited_obligations=credited,
        pending_persistence_obligations=pending,
        exclusions=exclusions,
    )
