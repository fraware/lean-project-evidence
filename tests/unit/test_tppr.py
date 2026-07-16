from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lpe.metrics.tppr import compute_tppr
from lpe.models import EventType, UtilityEvent


def make(
    event_id: str,
    event_type: EventType,
    payload: dict,
    obligation_id: str | None = "O-01",
    project_id: str = "project",
) -> UtilityEvent:
    return UtilityEvent(
        event_id=event_id,
        event_type=event_type,
        project_id=project_id,
        artifact_id="artifact",
        obligation_id=obligation_id,
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        actor_id="tester",
        payload=payload,
    )


def test_tppr_requires_acceptance_and_persistence() -> None:
    events = [
        make("e1", EventType.OBLIGATION_REGISTERED, {"weight": 3}),
        make(
            "e2",
            EventType.ARTIFACT_ACCEPTED,
            {"semantic_fidelity": True, "repository_accepted": True},
        ),
        make(
            "e3",
            EventType.PERSISTENCE_CONFIRMED,
            {"downstream_enabled": True, "remained_integrated": True},
        ),
        make(
            "e4",
            EventType.EXPERT_TIME_RECORDED,
            {"category": "review", "hours": 2.0},
            obligation_id=None,
        ),
        make(
            "e5",
            EventType.EXPERT_TIME_RECORDED,
            {"category": "repair", "hours": 1.0},
            obligation_id=None,
        ),
    ]
    report = compute_tppr(events, "project")
    assert report.weighted_accepted_sustained_obligations == 3
    assert report.expert_hours_total == 3
    assert report.tppr == 1
    assert report.credited_obligations == ["O-01"]
    assert report.pending_persistence_obligations == []


@pytest.mark.parametrize(
    ("accepted", "persistence", "expected_numerator", "expected_pending"),
    [
        (False, False, 0, []),
        (True, False, 0, ["O-01"]),
        (True, True, 3, []),
    ],
)
def test_tppr_numerator_and_pending_matrix(
    accepted: bool,
    persistence: bool,
    expected_numerator: float,
    expected_pending: list[str],
) -> None:
    events = [
        make("e1", EventType.OBLIGATION_REGISTERED, {"weight": 3}),
        make(
            "e2",
            EventType.ARTIFACT_ACCEPTED,
            {
                "semantic_fidelity": accepted,
                "repository_accepted": accepted,
            },
        ),
        make(
            "e3",
            EventType.EXPERT_TIME_RECORDED,
            {"category": "specification", "hours": 2.0},
            obligation_id=None,
        ),
    ]
    if persistence:
        events.append(
            make(
                "e4",
                EventType.PERSISTENCE_CONFIRMED,
                {
                    "downstream_enabled": True,
                    "remained_integrated": True,
                },
            )
        )
    report = compute_tppr(events, "project")
    assert report.weighted_accepted_sustained_obligations == expected_numerator
    assert report.pending_persistence_obligations == expected_pending


def test_tppr_denominator_uses_all_hour_categories() -> None:
    events = [
        make("e1", EventType.OBLIGATION_REGISTERED, {"weight": 1}),
        make(
            "e2",
            EventType.ARTIFACT_ACCEPTED,
            {"semantic_fidelity": True, "repository_accepted": True},
        ),
        make(
            "e3",
            EventType.PERSISTENCE_CONFIRMED,
            {"downstream_enabled": True, "remained_integrated": True},
        ),
        make("e4", EventType.EXPERT_TIME_RECORDED, {"category": "specification", "hours": 1}, None),
        make("e5", EventType.EXPERT_TIME_RECORDED, {"category": "review", "hours": 2}, None),
        make("e6", EventType.EXPERT_TIME_RECORDED, {"category": "repair", "hours": 3}, None),
        make("e7", EventType.EXPERT_TIME_RECORDED, {"category": "integration", "hours": 4}, None),
    ]
    report = compute_tppr(events, "project")
    assert report.specification_hours == 1
    assert report.review_hours == 2
    assert report.repair_hours == 3
    assert report.integration_hours == 4
    assert report.expert_hours_total == 10
    assert report.tppr == 0.1


def test_tppr_zero_expert_hours_returns_none() -> None:
    events = [make("e1", EventType.OBLIGATION_REGISTERED, {"weight": 2})]
    report = compute_tppr(events, "project")
    assert report.tppr is None
    assert report.expert_hours_total == 0


def test_tppr_multiple_obligations_credit_independently() -> None:
    events = [
        make("o1", EventType.OBLIGATION_REGISTERED, {"weight": 2}, "O-01"),
        make("o2", EventType.OBLIGATION_REGISTERED, {"weight": 3}, "O-02"),
        make(
            "a1",
            EventType.ARTIFACT_ACCEPTED,
            {"semantic_fidelity": True, "repository_accepted": True},
            "O-01",
        ),
        make(
            "a2",
            EventType.ARTIFACT_ACCEPTED,
            {"semantic_fidelity": True, "repository_accepted": True},
            "O-02",
        ),
        make(
            "p1",
            EventType.PERSISTENCE_CONFIRMED,
            {"downstream_enabled": True, "remained_integrated": True},
            "O-01",
        ),
        make("t1", EventType.EXPERT_TIME_RECORDED, {"category": "review", "hours": 5}, None),
    ]
    report = compute_tppr(events, "project")
    assert report.credited_obligations == ["O-01"]
    assert report.pending_persistence_obligations == ["O-02"]
    assert report.weighted_accepted_sustained_obligations == 2


def test_tppr_rejected_candidate_removes_credit() -> None:
    events = [
        make("e1", EventType.OBLIGATION_REGISTERED, {"weight": 3}),
        make(
            "e2",
            EventType.ARTIFACT_ACCEPTED,
            {"semantic_fidelity": True, "repository_accepted": True},
        ),
        make("e3", EventType.ARTIFACT_REJECTED, {"reason": "failed review"}),
        make("e4", EventType.EXPERT_TIME_RECORDED, {"category": "review", "hours": 1}, None),
    ]
    report = compute_tppr(events, "project")
    assert report.credited_obligations == []
    assert report.pending_persistence_obligations == []


def test_tppr_records_corrections_in_exclusions() -> None:
    events = [
        make("e1", EventType.OBLIGATION_REGISTERED, {"weight": 1}),
        make(
            "e2",
            EventType.CORRECTION_RECORDED,
            {"reason": "wrong weight"},
            obligation_id=None,
        ),
    ]
    events[1] = events[1].model_copy(update={"supersedes_event_id": "e1"})
    report = compute_tppr(events, "project")
    assert any("correction e2" in item for item in report.exclusions)


def test_tppr_unknown_expert_category_is_excluded() -> None:
    events = [
        make("e1", EventType.EXPERT_TIME_RECORDED, {"category": "mentoring", "hours": 2}, None),
    ]
    report = compute_tppr(events, "project")
    assert report.expert_hours_total == 0
    assert report.exclusions == ["unknown expert time category in e1"]


def test_tppr_accepts_legacy_minutes_only_payload() -> None:
    """Regression: minutes-only expert time converts to hours instead of KeyError."""
    events = [
        make(
            "e1",
            EventType.EXPERT_TIME_RECORDED,
            {"category": "review", "minutes": 30.0},
            None,
        ),
    ]
    report = compute_tppr(events, "project")
    assert report.review_hours == 0.5
    assert report.expert_hours_total == 0.5


def test_tppr_ignores_other_projects() -> None:
    events = [
        make("e1", EventType.OBLIGATION_REGISTERED, {"weight": 5}, project_id="other"),
        make("e2", EventType.EXPERT_TIME_RECORDED, {"category": "review", "hours": 1}, None),
    ]
    report = compute_tppr(events, "project")
    assert report.weighted_accepted_sustained_obligations == 0
    assert report.expert_hours_total == 1
