"""CLOSURE-018–020: typed ledger events, reducers, migration."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from lpe.cli import app
from lpe.ledger.events import (
    LEGACY_UNRESOLVED,
    AcceptanceAggregatedPayload,
    CandidateRegisteredPayload,
    CorrectionPayload,
    EventTypeV2,
    EvidenceCompiledPayload,
    ExpertTimePayload,
    ObligationFreezePayload,
    PersistenceRule,
    ReviewAttestationPayload,
    UtilityEventV2,
    parse_event_payload,
)
from lpe.ledger.migration import migrate_ledger
from lpe.ledger.state import (
    LifecycleError,
    apply_corrections_deterministically,
    fold_events,
    reduce_event,
    validate_event_against_history,
)
from lpe.ledger.store import LedgerStore, LedgerTransitionError
from lpe.models import EventType, UtilityEvent

runner = CliRunner()
NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)


def _freeze(artifact: str = "art-1") -> UtilityEventV2:
    return UtilityEventV2(
        event_id=f"evt-freeze-{artifact}",
        event_type=EventTypeV2.OBLIGATION_FROZEN,
        project_id="proj",
        artifact_id=artifact,
        obligation_ids=["O-01"],
        occurred_at=NOW,
        recorded_at=NOW,
        actor_id="system",
        payload=ObligationFreezePayload(
            freeze_id=f"freeze-{artifact}",
            obligation_ids=["O-01"],
            freeze_hash="a" * 64,
            persistence_rule=PersistenceRule(
                rule_id="persist-default",
                mode="calendar_days",
                threshold=30,
            ),
            contract_hash="b" * 64,
        ),
    )


def _candidate(artifact: str = "art-1") -> UtilityEventV2:
    return UtilityEventV2(
        event_id=f"evt-cand-{artifact}",
        event_type=EventTypeV2.CANDIDATE_REGISTERED,
        project_id="proj",
        artifact_id=artifact,
        obligation_ids=["O-01"],
        occurred_at=NOW,
        recorded_at=NOW,
        actor_id="system",
        payload=CandidateRegisteredPayload(
            candidate_id=f"cand-{artifact}",
            root_candidate_id=f"cand-{artifact}",
            freeze_id=f"freeze-{artifact}",
            base_ref="main",
            head_ref="HEAD",
            tree_hash="c" * 64,
            risk_class="R3",
        ),
    )


def _evidence(artifact: str = "art-1") -> UtilityEventV2:
    return UtilityEventV2(
        event_id=f"evt-ev-{artifact}",
        event_type=EventTypeV2.EVIDENCE_COMPILED,
        project_id="proj",
        artifact_id=artifact,
        obligation_ids=["O-01"],
        occurred_at=NOW,
        recorded_at=NOW,
        actor_id="system",
        payload=EvidenceCompiledPayload(
            packet_id=f"packet-{artifact}",
            evidence_fingerprint="d" * 64,
            candidate_id=f"cand-{artifact}",
            run_manifest_hash="e" * 64,
            finding_count=1,
        ),
    )


def test_payload_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_event_payload(
            {
                "payload_type": "ExpertTimePayload",
                "hours": 1.0,
                "minutes": 60.0,
                "category": "review",
                "unexpected": True,
            }
        )


def test_event_payload_type_mismatch_rejected() -> None:
    with pytest.raises(ValidationError):
        UtilityEventV2(
            event_id="e1",
            event_type=EventTypeV2.OBLIGATION_FROZEN,
            project_id="p",
            artifact_id="a",
            actor_id="actor",
            occurred_at=NOW,
            recorded_at=NOW,
            payload=ExpertTimePayload(hours=1.0, minutes=60.0, category="review"),
        )


def test_lifecycle_happy_path_to_acceptance(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "v2.sqlite3")
    art = "art-1"
    store.append_v2(_freeze(art))
    store.append_v2(_candidate(art))
    store.append_v2(_evidence(art))
    # R0-style accept directly from evidence
    store.append_v2(
        UtilityEventV2(
            event_id="evt-accept",
            event_type=EventTypeV2.ARTIFACT_ACCEPTED,
            project_id="proj",
            artifact_id=art,
            obligation_ids=["O-01"],
            occurred_at=NOW,
            recorded_at=NOW,
            actor_id="system",
            payload=AcceptanceAggregatedPayload(
                attestation_ids=[],
                quorum_policy_id="quorum.r0.auto",
                evidence_fingerprint="d" * 64,
                semantic_fidelity=True,
                repository_accepted=True,
                implementation_accepted=True,
                accepted_obligation_ids=["O-01"],
                accepted_at=NOW,
                risk_class="R0",
            ),
        )
    )
    store.verify()
    assert len(store.events_v2()) == 4


def test_invalid_transition_rejected_at_append(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "bad.sqlite3")
    store.append_v2(_freeze())
    with pytest.raises(LedgerTransitionError, match="invalid transition"):
        store.append_v2(_evidence())


def test_correction_deterministic(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "corr.sqlite3")
    store.append_v2(_freeze())
    # Side-channel correction targeting freeze
    corr = UtilityEventV2(
        event_id="evt-corr",
        event_type=EventTypeV2.CORRECTION_RECORDED,
        project_id="proj",
        artifact_id="art-1",
        actor_id="auditor",
        occurred_at=NOW,
        recorded_at=NOW,
        supersedes_event_id="evt-freeze-art-1",
        payload=CorrectionPayload(
            target_event_id="evt-freeze-art-1",
            reason="wrong hash",
            authorization_role="auditor",
            invalidation=True,
        ),
    )
    store.append_v2(corr)
    events = store.events_v2()
    effective = apply_corrections_deterministically(events)
    assert effective["evt-freeze-art-1"] is None
    assert effective["evt-corr"] is not None


@pytest.mark.parametrize("seed", range(12))
def test_property_arbitrary_sequences_reject_or_fold(seed: int) -> None:
    rng = random.Random(seed)
    types = list(EventTypeV2)
    history: list[UtilityEventV2] = []
    for i in range(rng.randint(1, 8)):
        et = rng.choice(types)
        # Build minimal payloads where possible; skip complex ones randomly.
        if et is EventTypeV2.EXPERT_TIME_RECORDED:
            event = UtilityEventV2(
                event_id=f"e-{seed}-{i}",
                event_type=et,
                project_id="p",
                artifact_id="a",
                actor_id="actor",
                occurred_at=NOW,
                recorded_at=NOW,
                payload=ExpertTimePayload(hours=0.1, minutes=6.0, category="review"),
            )
        elif et is EventTypeV2.LEGACY_UNRESOLVED:
            from lpe.ledger.events import LegacyUnresolvedPayload

            event = UtilityEventV2(
                event_id=f"e-{seed}-{i}",
                event_type=et,
                project_id="p",
                artifact_id="a",
                actor_id="actor",
                occurred_at=NOW,
                recorded_at=NOW,
                payload=LegacyUnresolvedPayload(
                    legacy_event_type="CANDIDATE_REGISTERED",
                    legacy_payload={"x": i},
                ),
            )
        else:
            continue
        try:
            validate_event_against_history(history, event)
            history.append(event)
        except LifecycleError:
            pass
    if history:
        fold_events(history)


def _review_assigned(artifact: str = "art-1") -> UtilityEventV2:
    from lpe.ledger.events import ReviewAssignedPayload

    return UtilityEventV2(
        event_id=f"evt-assign-{artifact}",
        event_type=EventTypeV2.REVIEW_ASSIGNED,
        project_id="proj",
        artifact_id=artifact,
        obligation_ids=["O-01"],
        occurred_at=NOW,
        recorded_at=NOW,
        actor_id="system",
        payload=ReviewAssignedPayload(
            assignment_id=f"assign-{artifact}",
            packet_id=f"packet-{artifact}",
            evidence_fingerprint="d" * 64,
            reviewer_id="reviewer-1",
            reviewer_role="lean-engineer",
            dimension="IMPLEMENTATION_QUALITY",
            risk_class="R1",
        ),
    )


def _review_attested(artifact: str = "art-1", *, suffix: str = "1") -> UtilityEventV2:
    from lpe.models import ReviewDecisionValue

    return UtilityEventV2(
        event_id=f"evt-attest-{artifact}-{suffix}",
        event_type=EventTypeV2.REVIEW_ATTESTED,
        project_id="proj",
        artifact_id=artifact,
        obligation_ids=["O-01"],
        occurred_at=NOW,
        recorded_at=NOW,
        actor_id="reviewer-1",
        payload=ReviewAttestationPayload(
            attestation_id=f"attest-{artifact}-{suffix}",
            packet_id=f"packet-{artifact}",
            evidence_fingerprint="d" * 64,
            reviewer_id="reviewer-1",
            reviewer_role="lean-engineer",
            dimension="IMPLEMENTATION_QUALITY",
            decision=ReviewDecisionValue.ACCEPT,
            confidence=90,
            conflict_declaration_hash="conflict",
        ),
    )


@pytest.mark.parametrize("seed", range(20))
def test_property_lifecycle_prefixes_and_invalid_jumps(seed: int) -> None:
    """Property: every happy-path prefix folds; illegal jumps raise LifecycleError."""
    from lpe.models import ReviewDecisionValue

    rng = random.Random(seed)
    art = f"art-{seed}"
    happy = [
        _freeze(art),
        _candidate(art),
        _evidence(art),
        _review_assigned(art),
        _review_attested(art).model_copy(
            update={
                "payload": ReviewAttestationPayload(
                    attestation_id=f"attest-{art}",
                    packet_id=f"packet-{art}",
                    evidence_fingerprint="d" * 64,
                    reviewer_id="reviewer-1",
                    reviewer_role="lean-engineer",
                    dimension="IMPLEMENTATION_QUALITY",
                    decision=ReviewDecisionValue.ACCEPT,
                    confidence=90,
                    conflict_declaration_hash="conflict",
                )
            }
        ),
        UtilityEventV2(
            event_id=f"evt-accept-{art}",
            event_type=EventTypeV2.ARTIFACT_ACCEPTED,
            project_id="proj",
            artifact_id=art,
            obligation_ids=["O-01"],
            occurred_at=NOW,
            recorded_at=NOW,
            actor_id="system",
            payload=AcceptanceAggregatedPayload(
                attestation_ids=[f"attest-{art}"],
                quorum_policy_id="quorum.r1.implementation",
                evidence_fingerprint="d" * 64,
                semantic_fidelity=True,
                repository_accepted=True,
                implementation_accepted=True,
                accepted_obligation_ids=["O-01"],
                accepted_at=NOW,
                risk_class="R1",
            ),
        ),
    ]
    cut = rng.randint(1, len(happy))
    prefix = happy[:cut]
    fold_events(prefix)

    # Illegal: skip candidate registration after freeze.
    if cut >= 1:
        with pytest.raises(LifecycleError):
            validate_event_against_history([_freeze(art)], _evidence(art))

    # Illegal: accept before evidence when only freeze exists.
    with pytest.raises(LifecycleError):
        validate_event_against_history(
            [_freeze(art)],
            UtilityEventV2(
                event_id=f"bad-accept-{seed}",
                event_type=EventTypeV2.ARTIFACT_ACCEPTED,
                project_id="proj",
                artifact_id=art,
                actor_id="system",
                occurred_at=NOW,
                recorded_at=NOW,
                payload=AcceptanceAggregatedPayload(
                    attestation_ids=[],
                    quorum_policy_id="quorum.r0.auto",
                    evidence_fingerprint="d" * 64,
                    semantic_fidelity=True,
                    repository_accepted=True,
                    implementation_accepted=True,
                    accepted_at=NOW,
                    risk_class="R0",
                ),
            ),
        )


def test_migration_preserves_and_marks_unresolved(tmp_path: Path) -> None:
    source = tmp_path / "src.sqlite3"
    target = tmp_path / "dst.sqlite3"
    report_path = tmp_path / "report.json"
    store = LedgerStore(source)
    store.append(
        UtilityEvent(
            event_id="legacy-1",
            event_type=EventType.ARTIFACT_ACCEPTED,
            project_id="proj",
            artifact_id="art",
            obligation_id="O-01",
            occurred_at=NOW,
            actor_id="reviewer",
            payload={"semantic_fidelity": True, "repository_accepted": True},
        )
    )
    report = migrate_ledger(source, target, report_path)
    assert report["source_event_count"] == 1
    assert report["invented_acceptance"] is False
    assert report["idempotent_rerun"] is False
    migrated = LedgerStore(target).events_v2()
    assert len(migrated) == 1
    assert migrated[0].event_type is EventTypeV2.LEGACY_UNRESOLVED
    assert LEGACY_UNRESOLVED in migrated[0].payload.unresolved_fields  # type: ignore[union-attr]
    assert report_path.is_file()

    # Idempotent re-run: verify + refresh report without rewriting history.
    report2 = migrate_ledger(source, target, report_path)
    assert report2["idempotent_rerun"] is True
    assert report2["source_event_count"] == 1
    assert report2["invented_acceptance"] is False
    assert len(LedgerStore(target).events_v2()) == 1


def test_migrate_ledger_refuses_same_path_and_mismatched_target(tmp_path: Path) -> None:
    from lpe.ledger.migration import LedgerMigrationError, migrate_ledger

    source = tmp_path / "src.sqlite3"
    report_path = tmp_path / "map.json"
    store = LedgerStore(source)
    store.append(
        UtilityEvent(
            event_id="legacy-1",
            event_type=EventType.ARTIFACT_ACCEPTED,
            project_id="proj",
            artifact_id="art",
            obligation_id="O-01",
            occurred_at=NOW,
            actor_id="reviewer",
            payload={"semantic_fidelity": True},
        )
    )
    with pytest.raises(LedgerMigrationError, match="must differ"):
        migrate_ledger(source, source, report_path)

    target = tmp_path / "dst.sqlite3"
    migrate_ledger(source, target, report_path)
    # Append an extra source event so counts diverge on idempotent re-check.
    store.append(
        UtilityEvent(
            event_id="legacy-2",
            event_type=EventType.CANDIDATE_REGISTERED,
            project_id="proj",
            artifact_id="art",
            obligation_id="O-01",
            occurred_at=NOW,
            actor_id="reviewer",
            payload={"x": 1},
        )
    )
    with pytest.raises(LedgerMigrationError, match="mismatched event count"):
        migrate_ledger(source, target, report_path)


def test_cli_ledger_migrate(tmp_path: Path) -> None:
    source = tmp_path / "src.sqlite3"
    target = tmp_path / "dst.sqlite3"
    report = tmp_path / "map.json"
    store = LedgerStore(source)
    store.append(
        UtilityEvent(
            event_id="legacy-1",
            event_type=EventType.CANDIDATE_REGISTERED,
            project_id="proj",
            artifact_id="art",
            occurred_at=NOW,
            actor_id="tester",
            payload={"x": 1},
        )
    )
    result = runner.invoke(
        app,
        [
            "ledger",
            "migrate",
            "--source",
            str(source),
            "--target",
            str(target),
            "--mapping-report",
            str(report),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert target.exists()
    assert report.exists()
