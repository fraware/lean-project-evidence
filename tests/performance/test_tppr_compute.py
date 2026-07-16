"""TPPR compute over moderate synthetic event sets."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lpe.metrics.tppr import compute_tppr
from lpe.models import EventType, UtilityEvent
from tests.performance.budgets import assert_within_soft_budget
from tests.performance.metrics import record, timed

_PROJECT = "project"
_MODERATE_N = 500


def _moderate_events(n: int = _MODERATE_N) -> list[UtilityEvent]:
    events: list[UtilityEvent] = []
    for i in range(n):
        oid = f"O-{i % 40:02d}"
        events.append(
            UtilityEvent(
                event_id=f"tppr-reg-{i}",
                event_type=EventType.OBLIGATION_REGISTERED,
                project_id=_PROJECT,
                artifact_id=f"art-{i}",
                obligation_id=oid,
                occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                actor_id="perf",
                payload={"weight": 1.0},
            )
        )
        if i % 3 == 0:
            events.append(
                UtilityEvent(
                    event_id=f"tppr-acc-{i}",
                    event_type=EventType.ARTIFACT_ACCEPTED,
                    project_id=_PROJECT,
                    artifact_id=f"art-{i}",
                    obligation_id=oid,
                    occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    actor_id="perf",
                    payload={
                        "semantic_fidelity": True,
                        "repository_accepted": True,
                    },
                )
            )
        if i % 5 == 0:
            events.append(
                UtilityEvent(
                    event_id=f"tppr-pers-{i}",
                    event_type=EventType.PERSISTENCE_CONFIRMED,
                    project_id=_PROJECT,
                    artifact_id=f"art-{i}",
                    obligation_id=oid,
                    occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    actor_id="perf",
                    payload={
                        "downstream_enabled": True,
                        "remained_integrated": True,
                    },
                )
            )
        if i % 7 == 0:
            events.append(
                UtilityEvent(
                    event_id=f"tppr-time-{i}",
                    event_type=EventType.EXPERT_TIME_RECORDED,
                    project_id=_PROJECT,
                    artifact_id=f"art-{i}",
                    obligation_id=None,
                    occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    actor_id="perf",
                    payload={"category": "review", "hours": 0.1},
                )
            )
    return events


@pytest.mark.performance
def test_tppr_compute_moderate_event_set() -> None:
    events = _moderate_events()
    assert len(events) >= _MODERATE_N

    with timed() as elapsed:
        report = compute_tppr(events, _PROJECT)
    tppr_s = elapsed[0]
    record(
        "tppr_moderate_s",
        tppr_s,
        unit="s",
        notes=f"compute_tppr over {len(events)} synthetic events",
    )
    assert_within_soft_budget("tppr_moderate_s", tppr_s)
    assert report.project_id == _PROJECT
    assert report.expert_hours_total >= 0
