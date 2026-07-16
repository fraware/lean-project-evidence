from __future__ import annotations

from lpe.pilot.instrumentation import PilotInstrumentation
from lpe.pilot.overhead import OverheadReport


def test_pilot_instrumentation_tracks_candidates() -> None:
    pilot = PilotInstrumentation()
    pilot.register_candidate(
        candidate_id="c1",
        project_id="p1",
        obligation_ids=["O-01"],
        condition_tag="control",
    )
    pilot.mark_packet_automated("c1")
    pilot.record_expert_time(
        candidate_id="c1",
        category="review",
        minutes=10.0,
        condition_tag="control",
    )
    assert pilot.automation_rate() == 1.0
    assert pilot.total_expert_minutes() == 10.0


def test_overhead_within_budget() -> None:
    report = OverheadReport.compute(baseline_minutes=100, instrumented_minutes=105)
    assert report.within_budget is True
    assert report.overhead_fraction == 0.05
