"""CLOSURE-021–024: attestations, conflicts, quorum, repair, adjudication."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from lpe.cli import app
from lpe.models import ReviewDecisionValue, RiskClass
from lpe.review.acceptance import AcceptanceError, aggregate_and_record_acceptance
from lpe.review.adjudication import (
    ADJUDICATOR_ROLE,
    AdjudicationError,
    AdjudicationRecord,
    ProvisionalJudgment,
    auditable_lineage,
    reveal_peer_attestations,
    validate_adjudicator,
)
from lpe.review.authority import can_record_acceptance, can_record_quorum_acceptance
from lpe.review.conflicts import (
    ConflictError,
    ReviewerConflictDeclaration,
    require_eligible_for_primary_attestation,
)
from lpe.review.models import ReviewAttestationV2, ReviewDimension
from lpe.review.quorum import evaluate_quorum
from lpe.review.repair import (
    attestations_do_not_transfer,
    build_repair_lineage,
    next_repair_candidate_id,
)
from lpe.ledger.store import LedgerStore

runner = CliRunner()
NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)
FP = "f" * 64


def _attestation(
    *,
    attestation_id: str,
    reviewer_id: str,
    role: str,
    dimension: ReviewDimension,
    decision: ReviewDecisionValue = ReviewDecisionValue.ACCEPT,
    conflict_hash: str = "conflict-hash",
) -> ReviewAttestationV2:
    return ReviewAttestationV2(
        attestation_id=attestation_id,
        packet_id="packet_x",
        evidence_fingerprint=FP,
        reviewer_id=reviewer_id,
        reviewer_role=role,
        dimension=dimension,
        decision=decision,
        confidence=90,
        rationale="ok",
        finding_refs=[],
        conflict_declaration_hash=conflict_hash,
        review_started_at=NOW,
        review_submitted_at=NOW,
        review_minutes=10.0,
    )


def test_attestation_requires_fingerprint_and_conflict_hash() -> None:
    with pytest.raises(ValidationError):
        ReviewAttestationV2(
            attestation_id="a1",
            packet_id="p",
            evidence_fingerprint="",
            reviewer_id="r",
            reviewer_role="domain-lead",
            dimension=ReviewDimension.SEMANTIC_FIDELITY,
            decision=ReviewDecisionValue.ACCEPT,
            confidence=90,
            rationale="x",
            conflict_declaration_hash="c",
            review_started_at=NOW,
            review_minutes=1.0,
        )


def test_conflict_fail_closed_authorship() -> None:
    decl = ReviewerConflictDeclaration(
        reviewer_id="r1",
        project_id="p",
        candidate_id="c1",
        candidate_author=True,
        eligible=False,
        signed_at=NOW,
    )
    assert decl.eligible is False
    with pytest.raises(ConflictError):
        require_eligible_for_primary_attestation(decl)


def test_conflict_cannot_claim_eligible_when_disqualified() -> None:
    with pytest.raises(ValidationError, match="fail closed"):
        ReviewerConflictDeclaration(
            reviewer_id="r1",
            project_id="p",
            candidate_id="c1",
            packet_constructor=True,
            eligible=True,
            signed_at=NOW,
        )


def test_r3_quorum_requires_distinct_reviewers() -> None:
    a1 = _attestation(
        attestation_id="a1",
        reviewer_id="same",
        role="domain-lead",
        dimension=ReviewDimension.SEMANTIC_FIDELITY,
    )
    a2 = _attestation(
        attestation_id="a2",
        reviewer_id="same",
        role="repository-maintainer",
        dimension=ReviewDimension.REPOSITORY_FIT,
    )
    result = evaluate_quorum(RiskClass.R3, [a1, a2], evidence_fingerprint=FP)
    assert result.satisfied is False


def test_r3_quorum_satisfied() -> None:
    a1 = _attestation(
        attestation_id="a1",
        reviewer_id="domain-lead",
        role="domain-lead",
        dimension=ReviewDimension.SEMANTIC_FIDELITY,
    )
    a2 = _attestation(
        attestation_id="a2",
        reviewer_id="repository-maintainer",
        role="repository-maintainer",
        dimension=ReviewDimension.REPOSITORY_FIT,
    )
    result = evaluate_quorum(RiskClass.R3, [a1, a2], evidence_fingerprint=FP)
    assert result.satisfied is True
    assert result.semantic_fidelity is True
    assert result.repository_accepted is True


def test_r4_quorum_requires_three_distinct_roles() -> None:
    a1 = _attestation(
        attestation_id="a1",
        reviewer_id="domain-lead",
        role="domain-lead",
        dimension=ReviewDimension.SEMANTIC_FIDELITY,
    )
    a2 = _attestation(
        attestation_id="a2",
        reviewer_id="architecture-maintainer",
        role="architecture-maintainer",
        dimension=ReviewDimension.REPOSITORY_FIT,
    )
    incomplete = evaluate_quorum(RiskClass.R4, [a1, a2], evidence_fingerprint=FP)
    assert incomplete.satisfied is False

    a3 = _attestation(
        attestation_id="a3",
        reviewer_id="lean-engineer",
        role="lean-engineer",
        dimension=ReviewDimension.IMPLEMENTATION_QUALITY,
    )
    full = evaluate_quorum(RiskClass.R4, [a1, a2, a3], evidence_fingerprint=FP)
    assert full.satisfied is True
    assert full.policy.allow_auto_accept is False
    assert full.semantic_fidelity is True
    assert full.repository_accepted is True
    assert full.implementation_accepted is True


def test_request_repair_and_indeterminate_block() -> None:
    repair = _attestation(
        attestation_id="a1",
        reviewer_id="domain-lead",
        role="domain-lead",
        dimension=ReviewDimension.SEMANTIC_FIDELITY,
        decision=ReviewDecisionValue.REQUEST_REPAIR,
    )
    accept = _attestation(
        attestation_id="a2",
        reviewer_id="repository-maintainer",
        role="repository-maintainer",
        dimension=ReviewDimension.REPOSITORY_FIT,
    )
    result = evaluate_quorum(RiskClass.R3, [repair, accept], evidence_fingerprint=FP)
    assert result.satisfied is False
    assert any("REQUEST_REPAIR" in r for r in result.blocking_reasons)

    indeterminate = repair.model_copy(
        update={"decision": ReviewDecisionValue.INDETERMINATE, "attestation_id": "a3"}
    )
    result2 = evaluate_quorum(RiskClass.R3, [indeterminate, accept], evidence_fingerprint=FP)
    assert result2.satisfied is False
    assert any("INDETERMINATE" in r for r in result2.blocking_reasons)


def test_fingerprint_mismatch_blocks_quorum() -> None:
    a1 = _attestation(
        attestation_id="a1",
        reviewer_id="domain-lead",
        role="domain-lead",
        dimension=ReviewDimension.SEMANTIC_FIDELITY,
    )
    a2 = _attestation(
        attestation_id="a2",
        reviewer_id="repository-maintainer",
        role="repository-maintainer",
        dimension=ReviewDimension.REPOSITORY_FIT,
    ).model_copy(update={"evidence_fingerprint": "0" * 64})
    result = evaluate_quorum(RiskClass.R3, [a1, a2], evidence_fingerprint=FP)
    assert result.satisfied is False
    assert any("fingerprint mismatch" in r for r in result.blocking_reasons)


def test_reject_blocks_quorum() -> None:
    a1 = _attestation(
        attestation_id="a1",
        reviewer_id="domain-lead",
        role="domain-lead",
        dimension=ReviewDimension.SEMANTIC_FIDELITY,
        decision=ReviewDecisionValue.REJECT,
    )
    a2 = _attestation(
        attestation_id="a2",
        reviewer_id="repository-maintainer",
        role="repository-maintainer",
        dimension=ReviewDimension.REPOSITORY_FIT,
    )
    result = evaluate_quorum(RiskClass.R3, [a1, a2], evidence_fingerprint=FP)
    assert result.satisfied is False
    assert any("REJECT" in r for r in result.blocking_reasons)


def test_can_record_acceptance_still_blocks_r3_r4_single_path() -> None:
    assert can_record_acceptance(RiskClass.R3) is False
    assert can_record_acceptance(RiskClass.R4) is False
    assert can_record_quorum_acceptance(RiskClass.R3) is True


def test_aggregate_r3_acceptance(tmp_path: Path) -> None:
    a1 = _attestation(
        attestation_id="a1",
        reviewer_id="domain-lead",
        role="domain-lead",
        dimension=ReviewDimension.SEMANTIC_FIDELITY,
    )
    a2 = _attestation(
        attestation_id="a2",
        reviewer_id="repository-maintainer",
        role="repository-maintainer",
        dimension=ReviewDimension.REPOSITORY_FIT,
    )
    digest = aggregate_and_record_acceptance(
        tmp_path / "ledger.db",
        project_id="example-category-project",
        artifact_id="packet_x",
        actor_id="aggregator",
        risk_class=RiskClass.R3,
        attestations=[a1, a2],
        evidence_fingerprint=FP,
        obligation_ids=["O-01"],
    )
    assert digest
    events = LedgerStore(tmp_path / "ledger.db").events()
    accepted = next(e for e in events if e.event_type.value == "ARTIFACT_ACCEPTED")
    assert accepted.payload["semantic_fidelity"] is True
    assert accepted.payload["repository_accepted"] is True
    assert accepted.payload["quorum_policy_id"] == "quorum.r3.semantic_repository"


def test_single_attestation_r3_refused(tmp_path: Path) -> None:
    a1 = _attestation(
        attestation_id="a1",
        reviewer_id="domain-lead",
        role="domain-lead",
        dimension=ReviewDimension.SEMANTIC_FIDELITY,
    )
    with pytest.raises(AcceptanceError, match="multi-attestation"):
        aggregate_and_record_acceptance(
            tmp_path / "ledger.db",
            project_id="p",
            artifact_id="packet_x",
            actor_id="aggregator",
            risk_class=RiskClass.R3,
            attestations=[a1],
            evidence_fingerprint=FP,
        )


def test_build_acceptance_event_r0_and_quorum_fail() -> None:
    from lpe.ledger.events import EventTypeV2
    from lpe.review.acceptance import build_acceptance_event

    event = build_acceptance_event(
        event_id="evt-r0",
        project_id="p",
        artifact_id="art",
        actor_id="system",
        risk_class=RiskClass.R0,
        attestations=[],
        evidence_fingerprint=FP,
    )
    assert event.event_type is EventTypeV2.ARTIFACT_ACCEPTED

    a1 = _attestation(
        attestation_id="a1",
        reviewer_id="domain-lead",
        role="domain-lead",
        dimension=ReviewDimension.SEMANTIC_FIDELITY,
    )
    with pytest.raises(AcceptanceError, match="quorum not satisfied"):
        build_acceptance_event(
            event_id="evt-r3",
            project_id="p",
            artifact_id="art",
            actor_id="system",
            risk_class=RiskClass.R3,
            attestations=[a1],
            evidence_fingerprint=FP,
        )


def test_record_attestation_event_legacy_path(tmp_path: Path) -> None:
    from lpe.review.acceptance import record_attestation_event

    ledger = tmp_path / "ledger.db"
    store = LedgerStore(ledger)
    store.initialize()
    att = _attestation(
        attestation_id="att-legacy-1",
        reviewer_id="domain-lead",
        role="domain-lead",
        dimension=ReviewDimension.SEMANTIC_FIDELITY,
    )
    digest = record_attestation_event(
        store,
        att,
        project_id="proj",
        artifact_id="art-1",
        obligation_ids=["O-01"],
    )
    assert digest
    events = store.events()
    assert any(e.event_type.value == "REVIEW_SUBMITTED" for e in events)
    assert any(e.event_type.value == "EXPERT_TIME_RECORDED" for e in events)


def test_repair_lineage_ids() -> None:
    assert next_repair_candidate_id("cand-root") == ("cand-root.r1", 1)
    assert next_repair_candidate_id("cand-root.r1") == ("cand-root.r2", 2)
    lineage = build_repair_lineage(
        prior_candidate_id="cand-root",
        repair_request_ids=["rep-1"],
        applied_change={"diff": "x"},
        new_evidence_fingerprint=FP,
    )
    assert lineage.new_candidate_id == "cand-root.r1"
    prior = [
        _attestation(
            attestation_id="old",
            reviewer_id="domain-lead",
            role="domain-lead",
            dimension=ReviewDimension.SEMANTIC_FIDELITY,
        )
    ]
    assert attestations_do_not_transfer(prior, lineage.new_candidate_id) == []


def test_adjudicator_rules() -> None:
    conflict = ReviewerConflictDeclaration(
        reviewer_id="adj-1",
        project_id="p",
        candidate_id="c1",
        eligible=True,
        signed_at=NOW,
    )
    h = validate_adjudicator(
        adjudicator_id="adj-1",
        adjudicator_roles=[ADJUDICATOR_ROLE],
        original_reviewer_ids=["domain-lead"],
        conflict=conflict,
    )
    assert h == conflict.declaration_hash()
    with pytest.raises(AdjudicationError, match="original reviewer"):
        validate_adjudicator(
            adjudicator_id="domain-lead",
            adjudicator_roles=[ADJUDICATOR_ROLE],
            original_reviewer_ids=["domain-lead"],
            conflict=conflict,
        )


def test_adjudication_lineage() -> None:
    provisional = ProvisionalJudgment(
        judgment_id="j1",
        adjudicator_id="adj-1",
        packet_id="packet_x",
        evidence_fingerprint=FP,
        provisional_decision=ReviewDecisionValue.ACCEPT,
        rationale="independent",
        recorded_at=NOW,
    )
    peers = [
        _attestation(
            attestation_id="a1",
            reviewer_id="domain-lead",
            role="domain-lead",
            dimension=ReviewDimension.SEMANTIC_FIDELITY,
        )
    ]
    revealed = reveal_peer_attestations(provisional, peers)
    record = AdjudicationRecord(
        adjudication_id="adj-rec-1",
        packet_id="packet_x",
        evidence_fingerprint=FP,
        adjudicator_id="adj-1",
        provisional_judgment_id="j1",
        original_attestation_ids=["a1"],
        decision=ReviewDecisionValue.ACCEPT,
        rationale="resolved",
        conflict_declaration_hash="ch",
        resolved_at=NOW,
    )
    lineage = auditable_lineage(provisional=revealed, record=record, peer_attestations=peers)
    assert lineage["adjudication_id"] == "adj-rec-1"


def test_cli_accept_quorum_r3(tmp_path: Path, example_project: Path) -> None:
    atts = [
        _attestation(
            attestation_id="a1",
            reviewer_id="domain-lead",
            role="domain-lead",
            dimension=ReviewDimension.SEMANTIC_FIDELITY,
        ).model_dump(mode="json"),
        _attestation(
            attestation_id="a2",
            reviewer_id="repository-maintainer",
            role="repository-maintainer",
            dimension=ReviewDimension.REPOSITORY_FIT,
        ).model_dump(mode="json"),
    ]
    path = tmp_path / "atts.json"
    path.write_text(json.dumps(atts), encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    result = runner.invoke(
        app,
        [
            "review",
            "accept-quorum",
            "--project",
            str(example_project),
            "--attestations",
            str(path),
            "--ledger",
            str(ledger),
            "--risk-class",
            "R3",
            "--evidence-fingerprint",
            FP,
            "--actor-id",
            "aggregator",
            "--artifact-id",
            "packet_x",
            "--obligation-ids",
            "O-01",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
