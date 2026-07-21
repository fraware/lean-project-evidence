"""CLOSURE-025–030 Phase E unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lpe.honesty.research_gates import (
    ResearchGateBlocked,
    evaluate_section21_gates,
    refuse_research_entrypoint,
)
from lpe.ledger.events import (
    AcceptanceAggregatedPayload,
    CandidateRegisteredPayload,
    DownstreamEnabledPayload,
    EventTypeV2,
    ExpertTimePayload,
    IntegrationConfirmedPayload,
    ObligationFreezePayload,
    PersistenceConfirmedPayload,
    PersistenceRule,
    UtilityEventV2,
)
from lpe.metrics.tppr_v2 import TPPRAntiGamingError, compute_tppr_v2
from lpe.pilot.analysis import (
    PilotEpisodeRecord,
    analyze_pilot,
    cohen_kappa,
    gwet_ac1,
)
from lpe.pilot.assignment import EpisodeSpec, assign_conditions, verify_assignment_with_seed
from lpe.pilot.comprehension import (
    CalibrationCase,
    CaseResponse,
    ComprehensionAttempt,
    EvidenceBasisAnswer,
    MaterialLabel,
    score_comprehension,
)
from lpe.pilot.protocol import (
    ProtocolError,
    freeze_protocol,
    validate_bundle_dir,
    write_example_bundle,
)

NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)


def _evt(
    event_id: str,
    event_type: EventTypeV2,
    payload,
    *,
    obligations: list[str] | None = None,
    artifact: str = "art-1",
    occurred: datetime | None = None,
) -> UtilityEventV2:
    return UtilityEventV2(
        event_id=event_id,
        event_type=event_type,
        project_id="proj",
        artifact_id=artifact,
        obligation_ids=obligations or ["O-01"],
        occurred_at=occurred or NOW,
        recorded_at=occurred or NOW,
        actor_id="operator",
        payload=payload,
    )


def _full_credit_events() -> list[UtilityEventV2]:
    rule = PersistenceRule(
        rule_id="persist-default",
        mode="calendar_days",
        threshold=30,
        regression_policy="revoke",
    )
    t0 = NOW
    return [
        _evt(
            "e-freeze",
            EventTypeV2.OBLIGATION_FROZEN,
            ObligationFreezePayload(
                freeze_id="fr1",
                obligation_ids=["O-01"],
                freeze_hash="a" * 64,
                persistence_rule=rule,
                contract_hash="b" * 64,
                obligation_weights={"O-01": 2.0},
            ),
            occurred=t0,
        ),
        _evt(
            "e-cand",
            EventTypeV2.CANDIDATE_REGISTERED,
            CandidateRegisteredPayload(
                candidate_id="c1",
                root_candidate_id="c1",
                freeze_id="fr1",
                base_ref="base",
                head_ref="head",
                tree_hash="c" * 64,
                risk_class="R2",
            ),
            occurred=t0 + timedelta(hours=1),
        ),
        _evt(
            "e-acc",
            EventTypeV2.ARTIFACT_ACCEPTED,
            AcceptanceAggregatedPayload(
                attestation_ids=["a1"],
                quorum_policy_id="quorum.r2.repository",
                evidence_fingerprint="d" * 64,
                semantic_fidelity=False,
                repository_accepted=True,
                implementation_accepted=False,
                accepted_obligation_ids=["O-01"],
                accepted_at=t0 + timedelta(days=1),
                risk_class="R2",
            ),
            occurred=t0 + timedelta(days=1),
        ),
        _evt(
            "e-int",
            EventTypeV2.INTEGRATION_CONFIRMED,
            IntegrationConfirmedPayload(candidate_id="c1", integration_ref="main@1"),
            occurred=t0 + timedelta(days=2),
        ),
        _evt(
            "e-down",
            EventTypeV2.DOWNSTREAM_ENABLED,
            DownstreamEnabledPayload(
                candidate_id="c1",
                suite_ids=["downstream.main"],
                evidence_fingerprint="d" * 64,
            ),
            occurred=t0 + timedelta(days=3),
        ),
        _evt(
            "e-pers",
            EventTypeV2.PERSISTENCE_CONFIRMED,
            PersistenceConfirmedPayload(
                candidate_id="c1",
                persistence_rule_id="persist-default",
                confirmed_at=t0 + timedelta(days=35),
                window_elapsed=True,
            ),
            occurred=t0 + timedelta(days=35),
        ),
        _evt(
            "e-time",
            EventTypeV2.EXPERT_TIME_RECORDED,
            ExpertTimePayload(
                hours=2.0,
                minutes=120.0,
                category="review",
                measurement_confidence="exact_timer",
            ),
            obligations=[],
            occurred=t0 + timedelta(days=1),
        ),
    ]


def test_tppr_v2_credits_once() -> None:
    report = compute_tppr_v2(_full_credit_events(), "proj")
    assert report.credited_obligations == ["O-01"]
    assert report.weighted_credited == 2.0
    assert report.tppr_complete_case == pytest.approx(1.0)
    assert any(row.credited for row in report.numerator_audit)


def test_tppr_v2_rejects_persistence_before_integration() -> None:
    events = _full_credit_events()
    # Drop integration
    events = [e for e in events if e.event_type is not EventTypeV2.INTEGRATION_CONFIRMED]
    with pytest.raises(TPPRAntiGamingError, match="persistence before integration"):
        compute_tppr_v2(events, "proj")


def test_tppr_v2_rejects_anonymous_actor() -> None:
    events = _full_credit_events()
    events[0] = events[0].model_copy(update={"actor_id": "anonymous"})
    with pytest.raises(TPPRAntiGamingError, match="anonymous"):
        compute_tppr_v2(events, "proj")


def test_tppr_v2_condition_assigned_maps_candidate() -> None:
    from lpe.ledger.events import ConditionAssignedPayload

    events = _full_credit_events()
    # CONDITION_ASSIGNED must precede candidate registration mapping consumption.
    cand = next(e for e in events if e.event_type is EventTypeV2.CANDIDATE_REGISTERED)
    assert isinstance(cand.payload, CandidateRegisteredPayload)
    cond = _evt(
        "cond-1",
        EventTypeV2.CONDITION_ASSIGNED,
        ConditionAssignedPayload(
            condition_assignment_id="assign-1",
            condition_tag="instrumented",
            candidate_id=cand.payload.candidate_id,
            assignment_hash="h" * 64,
        ),
        obligations=[],
        occurred=NOW - timedelta(seconds=1),
    )
    report = compute_tppr_v2([cond, *events], "proj")
    assert report.credited_obligations == ["O-01"]
    instrumented = [c for c in report.cohorts if c.condition_tag == "instrumented"]
    assert instrumented
    assert "O-01" in instrumented[0].credited_obligations


def test_tppr_v2_rejects_candidate_before_freeze() -> None:
    events = _full_credit_events()
    # Swap times so candidate is before freeze
    freeze = events[0]
    cand = events[1]
    events[0] = freeze.model_copy(update={"occurred_at": NOW + timedelta(hours=2)})
    events[1] = cand.model_copy(update={"occurred_at": NOW})
    with pytest.raises(TPPRAntiGamingError, match="before obligation freeze"):
        compute_tppr_v2(events, "proj")


def test_protocol_bundle_freeze_and_refuse_blank(tmp_path: Path) -> None:
    root = write_example_bundle(tmp_path / "pilot-protocol")
    bundle = validate_bundle_dir(root)
    assert bundle.protocol.sample_size_min >= 30
    frozen = freeze_protocol(root)
    assert frozen.frozen
    # Mutate protocol after freeze
    proto = (root / "protocol.yaml").read_text(encoding="utf-8")
    (root / "protocol.yaml").write_text(
        proto.replace("example-partner", "mutated-partner"), encoding="utf-8"
    )
    with pytest.raises(ProtocolError):
        freeze_protocol(root)


def test_assignment_deterministic_quotas(tmp_path: Path) -> None:
    root = write_example_bundle(tmp_path / "proto")
    freeze_protocol(root)
    bundle = validate_bundle_dir(root)
    episodes = [
        EpisodeSpec(
            candidate_id=f"c{i:02d}",
            risk_class="R2",
            artifact_type="theorem",
            author_id="author-x",
        )
        for i in range(10)
    ]
    m1 = assign_conditions(
        protocol_id=bundle.protocol.protocol_id,
        config=bundle.assignment,
        episodes=episodes,
        roster=bundle.roster,
        seed_plaintext="seed-abc",
    )
    m2 = assign_conditions(
        protocol_id=bundle.protocol.protocol_id,
        config=bundle.assignment,
        episodes=episodes,
        roster=bundle.roster,
        seed_plaintext="seed-abc",
    )
    assert m1.manifest_hash == m2.manifest_hash
    assert m1.quotas["control"] == 4
    assert m1.quotas["instrumented"] == 4
    assert m1.quotas["shadow"] == 2
    assert verify_assignment_with_seed(
        m1,
        config=bundle.assignment,
        episodes=episodes,
        roster=bundle.roster,
        seed_plaintext="seed-abc",
    )


def test_assignment_repair_blinding(tmp_path: Path) -> None:
    root = write_example_bundle(tmp_path / "proto")
    freeze_protocol(root)
    bundle = validate_bundle_dir(root)
    base = [
        EpisodeSpec(
            candidate_id="c00",
            risk_class="R2",
            artifact_type="theorem",
            author_id="author-x",
        ),
        EpisodeSpec(
            candidate_id="c01",
            risk_class="R2",
            artifact_type="theorem",
            author_id="author-y",
        ),
        EpisodeSpec(
            candidate_id="c02",
            risk_class="R2",
            artifact_type="theorem",
            author_id="author-z",
        ),
        EpisodeSpec(
            candidate_id="c03",
            risk_class="R2",
            artifact_type="theorem",
            author_id="author-w",
        ),
        EpisodeSpec(
            candidate_id="c04",
            risk_class="R2",
            artifact_type="theorem",
            author_id="author-v",
        ),
    ]
    repair = EpisodeSpec(
        candidate_id="c00.r1",
        risk_class="R2",
        artifact_type="theorem",
        author_id="author-x",
        root_candidate_id="c00",
        is_repair=True,
    )
    manifest = assign_conditions(
        protocol_id=bundle.protocol.protocol_id,
        config=bundle.assignment,
        episodes=[*base, repair],
        roster=bundle.roster,
        seed_plaintext="seed-repair",
    )
    root_asg = next(a for a in manifest.assignments if a.candidate_id == "c00")
    repair_asg = next(a for a in manifest.assignments if a.candidate_id == "c00.r1")
    root_reviewers = {r.reviewer_id for r in root_asg.reviewers}
    repair_reviewers = {r.reviewer_id for r in repair_asg.reviewers}
    assert repair_asg.condition_tag == root_asg.condition_tag
    assert not (root_reviewers & repair_reviewers)


def test_comprehension_pass_and_second_fail_excludes(tmp_path: Path) -> None:
    root = write_example_bundle(tmp_path / "proto")
    bundle = validate_bundle_dir(root)
    cases = [
        CalibrationCase(
            case_id=cid,
            adjudicated_material=MaterialLabel.MATERIAL_DEFECT,
            adjudicated_basis=EvidenceBasisAnswer.KERNEL_CHECKED,
        )
        for cid in bundle.comprehension.calibration_case_ids
    ]
    good = ComprehensionAttempt(
        attempt_number=1,
        responses=[
            CaseResponse(
                case_id=c.case_id,
                material_judgment=MaterialLabel.MATERIAL_DEFECT,
                basis_answer=EvidenceBasisAnswer.KERNEL_CHECKED,
            )
            for c in cases
        ],
        conflict_blinding_acknowledged=True,
    )
    result = score_comprehension(
        reviewer_id="domain-alice",
        config=bundle.comprehension,
        cases=cases,
        attempt=good,
    )
    assert result.passed
    assert not result.excluded_from_primary

    bad_responses = [
        CaseResponse(
            case_id=c.case_id,
            material_judgment=MaterialLabel.NO_MATERIAL_DEFECT,
            basis_answer=EvidenceBasisAnswer.HEURISTIC_RETRIEVAL,
        )
        for c in cases
    ]
    fail1 = score_comprehension(
        reviewer_id="domain-alice",
        config=bundle.comprehension,
        cases=cases,
        attempt=ComprehensionAttempt(
            attempt_number=1,
            responses=bad_responses,
            conflict_blinding_acknowledged=True,
        ),
    )
    assert not fail1.passed
    fail2 = score_comprehension(
        reviewer_id="domain-alice",
        config=bundle.comprehension,
        cases=cases,
        attempt=ComprehensionAttempt(
            attempt_number=2,
            responses=bad_responses,
            conflict_blinding_acknowledged=True,
        ),
        prior_failures=1,
    )
    assert fail2.excluded_from_primary


def test_analysis_agreement_and_gates_fail_closed() -> None:
    episodes = [
        PilotEpisodeRecord(
            episode_id=f"e{i}",
            condition_tag="control" if i % 2 == 0 else "instrumented",
            risk_class="R2",
            artifact_type="theorem",
            reviewer_id="r1",
            review_minutes=30.0,
            outcome="accept",
            automated_packet=True,
            exact_environment_reproduction=True,
            primary_label="ok",
            peer_label="ok",
            weighted_accepted_obligations=1.0,
        )
        for i in range(10)
    ]
    report = analyze_pilot(
        protocol_id="proto.x",
        data_lock_hash="lockhash",
        episodes=episodes,
    )
    assert report.agreement
    assert cohen_kappa(["a", "a"], ["a", "b"]) is not None
    assert gwet_ac1(["a", "a"], ["a", "a"]) == pytest.approx(1.0)

    gate = evaluate_section21_gates(
        protocol_id="proto.x",
        data_lock_hash="lockhash",
        observables={},  # all missing → fail closed
    )
    assert not gate.shadow_pilot_passed
    assert not gate.learned_routing_authorized
    assert not gate.synthesis_authorized
    assert len(gate.blocking_reasons) >= 10


def test_research_training_still_blocked() -> None:
    with pytest.raises(ResearchGateBlocked):
        refuse_research_entrypoint("routing.train")
    with pytest.raises(ResearchGateBlocked):
        refuse_research_entrypoint("closure-037")
