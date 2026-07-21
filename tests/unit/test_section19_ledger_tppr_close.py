"""Close remaining §19 ledger / TPPR line gaps toward 95%."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from lpe.ledger.events import (
    AcceptanceAggregatedPayload,
    CandidateRegisteredPayload,
    CorrectionPayload,
    DownstreamEnabledPayload,
    EventTypeV2,
    ExpertTimePayload,
    IntegrationConfirmedPayload,
    ObligationFreezePayload,
    PersistenceConfirmedPayload,
    PersistenceRule,
    UtilityEventV2,
    parse_event_payload,
)
from lpe.ledger.migration import LedgerMigrationError, migrate_ledger
from lpe.ledger.seal import LedgerSealError, verify_seal, write_seal
from lpe.ledger.state import LedgerReducerState, LifecycleError, reduce_event
from lpe.ledger.store import LedgerIntegrityError, LedgerStore
from lpe.metrics.tppr import compute_tppr
from lpe.metrics.tppr_v2 import (
    TPPRAntiGamingError,
    compute_tppr_v2,
    events_from_legacy_dicts,
)
from lpe.models import EventType, UtilityEvent

NOW = datetime(2026, 7, 21, tzinfo=UTC)
FP = "f" * 64


def _legacy(
    event_id: str,
    event_type: EventType,
    payload: dict,
    *,
    obligation_id: str | None = "O-01",
) -> UtilityEvent:
    return UtilityEvent(
        event_id=event_id,
        event_type=event_type,
        project_id="proj",
        artifact_id="art",
        obligation_id=obligation_id,
        actor_id="op",
        payload=payload,
        occurred_at=NOW,
    )


def _v2(
    event_id: str,
    event_type: EventTypeV2,
    payload: object,
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
        obligation_ids=obligations if obligations is not None else ["O-01"],
        occurred_at=occurred or NOW,
        recorded_at=occurred or NOW,
        actor_id="operator",
        payload=payload,
    )


def test_tppr_v1_missing_time_and_correction() -> None:
    events = [
        _legacy("e1", EventType.OBLIGATION_REGISTERED, {"weight": 1}),
        _legacy(
            "e2",
            EventType.EXPERT_TIME_RECORDED,
            {"category": "review"},
            obligation_id=None,
        ),
        _legacy(
            "e3",
            EventType.CORRECTION_RECORDED,
            {"reason": "fix"},
            obligation_id=None,
        ),
    ]
    events[-1] = events[-1].model_copy(update={"supersedes_event_id": "e1"})
    report = compute_tppr(events, "proj")
    assert any("missing hours" in e for e in report.exclusions)
    assert any("correction" in e for e in report.exclusions)


def test_tppr_v2_credit_gaps_and_lineage() -> None:
    with pytest.raises(ValidationError):
        events_from_legacy_dicts([{"event_id": "bad"}])

    rule = PersistenceRule(
        rule_id="persist-default",
        mode="calendar_days",
        threshold=30,
        required_downstream_suite_ids=["must-have"],
        regression_policy="revoke",
    )
    t0 = NOW
    incomplete = [
        _v2(
            "f",
            EventTypeV2.OBLIGATION_FROZEN,
            ObligationFreezePayload(
                freeze_id="fr1",
                obligation_ids=["O-01"],
                freeze_hash="a" * 64,
                persistence_rule=rule,
                contract_hash="b" * 64,
                obligation_weights={"O-01": 1.0},
            ),
        ),
        _v2(
            "c",
            EventTypeV2.CANDIDATE_REGISTERED,
            CandidateRegisteredPayload(
                candidate_id="c1",
                root_candidate_id="root-1",
                freeze_id="fr1",
                base_ref="b",
                head_ref="h",
                tree_hash="c" * 64,
                risk_class="R1",
            ),
            occurred=t0 + timedelta(hours=1),
        ),
        _v2(
            "a",
            EventTypeV2.ARTIFACT_ACCEPTED,
            AcceptanceAggregatedPayload(
                attestation_ids=["a1"],
                quorum_policy_id="quorum.r1.implementation",
                evidence_fingerprint=FP,
                semantic_fidelity=False,
                repository_accepted=False,
                implementation_accepted=True,
                accepted_obligation_ids=["O-01"],
                accepted_at=t0 + timedelta(days=1),
                risk_class="R1",
            ),
            occurred=t0 + timedelta(days=1),
        ),
        _v2(
            "t",
            EventTypeV2.EXPERT_TIME_RECORDED,
            ExpertTimePayload(
                hours=1.0,
                minutes=60.0,
                category="review",
                measurement_confidence="exact_timer",
            ),
            obligations=[],
        ),
    ]
    report = compute_tppr_v2(incomplete, "proj")
    assert "O-01" in report.pending_persistence_obligations
    assert report.credited_obligations == []

    almost = [
        *incomplete[:-1],
        _v2(
            "i",
            EventTypeV2.INTEGRATION_CONFIRMED,
            IntegrationConfirmedPayload(candidate_id="root-1", integration_ref="m"),
            occurred=t0 + timedelta(days=2),
        ),
        _v2(
            "d",
            EventTypeV2.DOWNSTREAM_ENABLED,
            DownstreamEnabledPayload(
                candidate_id="c1",
                suite_ids=["other"],
                evidence_fingerprint=FP,
            ),
            occurred=t0 + timedelta(days=3),
        ),
        _v2(
            "p",
            EventTypeV2.PERSISTENCE_CONFIRMED,
            PersistenceConfirmedPayload(
                candidate_id="c1",
                persistence_rule_id="persist-default",
                confirmed_at=t0 + timedelta(days=40),
                window_elapsed=True,
            ),
            occurred=t0 + timedelta(days=40),
        ),
        incomplete[-1],
    ]
    report2 = compute_tppr_v2(almost, "proj")
    reasons = " ".join(r for row in report2.numerator_audit for r in row.blocking_reasons)
    assert "downstream" in reasons

    multi_freeze = [
        _v2(
            "f1",
            EventTypeV2.OBLIGATION_FROZEN,
            ObligationFreezePayload(
                freeze_id="fr1",
                obligation_ids=["O-01"],
                freeze_hash="a" * 64,
                persistence_rule=rule,
                contract_hash="b" * 64,
                obligation_weights={"O-01": 1.0},
            ),
        ),
        _v2(
            "f2",
            EventTypeV2.OBLIGATION_FROZEN,
            ObligationFreezePayload(
                freeze_id="fr2",
                obligation_ids=["O-01"],
                freeze_hash="c" * 64,
                persistence_rule=rule,
                contract_hash="d" * 64,
                obligation_weights={"O-01": 1.0},
            ),
            occurred=t0 + timedelta(seconds=1),
        ),
    ]
    with pytest.raises(TPPRAntiGamingError, match="multiple freezes"):
        compute_tppr_v2(multi_freeze, "proj")

    bad_cond = UtilityEventV2.model_construct(
        event_id="bad",
        event_type=EventTypeV2.CONDITION_ASSIGNED,
        project_id="proj",
        artifact_id="art",
        obligation_ids=[],
        occurred_at=NOW,
        recorded_at=NOW,
        actor_id="op",
        payload=ExpertTimePayload(
            hours=1.0,
            minutes=60.0,
            category="review",
            measurement_confidence="exact_timer",
        ),
    )
    with pytest.raises(TPPRAntiGamingError, match="payload mismatch"):
        compute_tppr_v2([bad_cond], "proj")


def test_ledger_events_validators_and_parse() -> None:
    with pytest.raises(ValidationError):
        AcceptanceAggregatedPayload(
            attestation_ids=["a"],
            quorum_policy_id="q",
            evidence_fingerprint=FP,
            semantic_fidelity=True,
            repository_accepted=True,
            implementation_accepted=True,
            accepted_obligation_ids=["O-01"],
            accepted_at=datetime(2026, 1, 1),
            risk_class="R1",
        )
    parsed = parse_event_payload(
        {
            "payload_type": "ExpertTimePayload",
            "hours": 1.0,
            "minutes": 60.0,
            "category": "review",
            "measurement_confidence": "exact_timer",
        }
    )
    assert parsed.payload_type == "ExpertTimePayload"
    assert parse_event_payload(parsed) is parsed

    with pytest.raises(ValidationError):
        UtilityEventV2(
            event_id="e",
            event_type=EventTypeV2.EXPERT_TIME_RECORDED,
            project_id="p",
            artifact_id="a",
            actor_id="op",
            payload=ExpertTimePayload(
                hours=1.0,
                minutes=60.0,
                category="review",
                measurement_confidence="exact_timer",
            ),
            occurred_at=datetime(2026, 1, 1),
        )


def test_ledger_migration_verify_failures(tmp_path: Path) -> None:
    source = tmp_path / "src.sqlite"
    target = tmp_path / "tgt.sqlite"
    report = tmp_path / "mig.json"
    store = LedgerStore(source)
    store.initialize()
    store.append(_legacy("e1", EventType.OBLIGATION_REGISTERED, {"weight": 1}))

    with sqlite3.connect(source) as conn:
        conn.execute("DROP TRIGGER IF EXISTS deny_events_update")
        conn.execute("UPDATE events SET event_hash = 'deadbeef'")
        conn.commit()
    with pytest.raises(LedgerMigrationError, match="source ledger verify"):
        migrate_ledger(source, target, report)

    source2 = tmp_path / "src2.sqlite"
    target2 = tmp_path / "tgt2.sqlite"
    store2 = LedgerStore(source2)
    store2.initialize()
    store2.append(_legacy("e1", EventType.OBLIGATION_REGISTERED, {"weight": 1}))
    migrate_ledger(source2, target2, report)
    with sqlite3.connect(target2) as conn:
        conn.execute("DROP TRIGGER IF EXISTS deny_events_update")
        conn.execute("UPDATE events SET event_hash = 'bad'")
        conn.commit()
    with pytest.raises(LedgerMigrationError, match="target ledger exists"):
        migrate_ledger(source2, target2, report)


def test_ledger_state_candidate_and_correction_guards() -> None:
    rule = PersistenceRule(
        rule_id="r", mode="calendar_days", threshold=1, regression_policy="revoke"
    )
    state = LedgerReducerState()
    reduce_event(
        state,
        _v2(
            "f1",
            EventTypeV2.OBLIGATION_FROZEN,
            ObligationFreezePayload(
                freeze_id="fr1",
                obligation_ids=["O-01"],
                freeze_hash="a" * 64,
                persistence_rule=rule,
                contract_hash="b" * 64,
            ),
        ),
    )
    with pytest.raises(LifecycleError, match="unknown freeze"):
        reduce_event(
            state,
            _v2(
                "c-bad",
                EventTypeV2.CANDIDATE_REGISTERED,
                CandidateRegisteredPayload(
                    candidate_id="c1",
                    root_candidate_id="c1",
                    freeze_id="missing",
                    base_ref="b",
                    head_ref="h",
                    tree_hash="t" * 64,
                    risk_class="R1",
                ),
            ),
        )

    bad_freeze = UtilityEventV2.model_construct(
        event_id="bf",
        event_type=EventTypeV2.OBLIGATION_FROZEN,
        project_id="proj",
        artifact_id="art-x",
        obligation_ids=["O-9"],
        occurred_at=NOW,
        recorded_at=NOW,
        actor_id="op",
        payload=CandidateRegisteredPayload(
            candidate_id="c",
            root_candidate_id="c",
            freeze_id="frx",
            base_ref="b",
            head_ref="h",
            tree_hash="t" * 64,
            risk_class="R1",
        ),
    )
    with pytest.raises(LifecycleError, match="OBLIGATION_FROZEN"):
        reduce_event(LedgerReducerState(), bad_freeze)

    with pytest.raises(LifecycleError, match="authorization_role"):
        reduce_event(
            state,
            _v2(
                "corr",
                EventTypeV2.CORRECTION_RECORDED,
                CorrectionPayload(
                    target_event_id="f1",
                    reason="x",
                    authorization_role="  ",
                    invalidation=True,
                ),
                obligations=[],
            ),
        )

    with pytest.raises(LifecycleError, match="invalidation"):
        reduce_event(
            state,
            _v2(
                "corr2",
                EventTypeV2.CORRECTION_RECORDED,
                CorrectionPayload(
                    target_event_id="f1",
                    reason="x",
                    authorization_role="lead",
                    invalidation=False,
                    replacement_payload=None,
                ),
                obligations=[],
            ),
        )


def test_ledger_store_verify_and_wal_paths(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite"
    store = LedgerStore(path)
    store.initialize()
    store.append(_legacy("e1", EventType.OBLIGATION_REGISTERED, {"weight": 1}))
    store.verify()

    with sqlite3.connect(path) as conn:
        conn.execute("DROP TRIGGER IF EXISTS deny_events_update")
        conn.execute("UPDATE events SET previous_hash = 'nope' WHERE event_id = 'e1'")
        conn.commit()
    with pytest.raises(LedgerIntegrityError, match=r"previous_hash|event_hash"):
        store.verify()

    with patch.object(LedgerStore, "connect") as connect:
        fake = connect.return_value.__enter__.return_value
        fake.execute.return_value.fetchone.return_value = ("delete",)
        fake.executescript = lambda *_a, **_k: None
        bad = LedgerStore(tmp_path / "wal-fail.sqlite")
        bad._initialized = False
        with pytest.raises(LedgerIntegrityError, match="WAL"):
            bad.initialize()


def test_ledger_seal_mismatch_paths(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite"
    store = LedgerStore(path)
    store.initialize()
    store.append(_legacy("e1", EventType.OBLIGATION_REGISTERED, {"weight": 1}))
    seal_path = tmp_path / "seal.json"
    write_seal(store, seal_path, protocol_freeze_hash="p" * 64)
    verify_seal(store, seal_path)

    sealed = json.loads(seal_path.read_text(encoding="utf-8"))
    sealed["event_count"] = 999
    seal_path.write_text(json.dumps(sealed, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(LedgerSealError, match="event_count"):
        verify_seal(store, seal_path)


def test_ledger_events_schema_and_reject_payload() -> None:
    from lpe.ledger.events import LegacyUnresolvedPayload, ReviewAttestationPayload

    with pytest.raises(ValueError, match="schema_version"):
        UtilityEventV2.only_v2("9.9.9")

    # ARTIFACT_REJECTED may carry LegacyUnresolvedPayload
    rejected = UtilityEventV2(
        event_id="rej",
        event_type=EventTypeV2.ARTIFACT_REJECTED,
        project_id="p",
        artifact_id="a",
        actor_id="op",
        payload=LegacyUnresolvedPayload(legacy_event_type="ARTIFACT_REJECTED"),
    )
    assert rejected.payload.payload_type == "LegacyUnresolvedPayload"
    assert "payload_type" in rejected.payload_dict()

    # Mismatched payload for non-reject types
    with pytest.raises(ValidationError, match="requires payload_type"):
        UtilityEventV2(
            event_id="bad",
            event_type=EventTypeV2.INTEGRATION_CONFIRMED,
            project_id="p",
            artifact_id="a",
            actor_id="op",
            payload=ReviewAttestationPayload(
                attestation_id="a1",
                packet_id="p",
                evidence_fingerprint=FP,
                reviewer_id="r",
                reviewer_role="lean-engineer",
                dimension="IMPLEMENTATION_QUALITY",
                decision="ACCEPT",
                confidence=90,
                conflict_declaration_hash="c" * 64,
            ),
        )


def test_ledger_migration_idempotent_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "src.sqlite"
    other = tmp_path / "other.sqlite"
    target = tmp_path / "tgt.sqlite"
    report = tmp_path / "mig.json"

    store = LedgerStore(source)
    store.initialize()
    store.append(_legacy("e1", EventType.OBLIGATION_REGISTERED, {"weight": 1}))

    other_store = LedgerStore(other)
    other_store.initialize()
    other_store.append(_legacy("e2", EventType.OBLIGATION_REGISTERED, {"weight": 1}))
    migrate_ledger(other, target, report)

    # Target is a valid 1-event LEGACY ledger whose event_id differs from source.
    with pytest.raises(LedgerMigrationError, match="event_id mismatch"):
        migrate_ledger(source, target, report)


def test_ledger_push_to_95_edges(tmp_path: Path) -> None:
    """Cover the last few ledger statements needed for the §19 95% group gate."""
    from lpe.ledger.store import LedgerTransitionError

    # migration: target exists with matching count but non-LEGACY events
    source = tmp_path / "src.sqlite"
    target = tmp_path / "tgt.sqlite"
    report = tmp_path / "mig.json"
    src = LedgerStore(source)
    src.initialize()
    src.append(_legacy("e1", EventType.OBLIGATION_REGISTERED, {"weight": 1}))

    rule = PersistenceRule(
        rule_id="r", mode="calendar_days", threshold=1, regression_policy="revoke"
    )
    tgt = LedgerStore(target)
    tgt.initialize()
    tgt.append_v2(
        _v2(
            "e1",
            EventTypeV2.OBLIGATION_FROZEN,
            ObligationFreezePayload(
                freeze_id="fr1",
                obligation_ids=["O-01"],
                freeze_hash="a" * 64,
                persistence_rule=rule,
                contract_hash="b" * 64,
            ),
        )
    )
    with pytest.raises(LedgerMigrationError, match="LEGACY_UNRESOLVED"):
        migrate_ledger(source, target, report)

    # Successful append_correction_v2 (hits return path)
    live = LedgerStore(tmp_path / "live.sqlite")
    live.initialize()
    live.append_v2(
        _v2(
            "f1",
            EventTypeV2.OBLIGATION_FROZEN,
            ObligationFreezePayload(
                freeze_id="fr1",
                obligation_ids=["O-01"],
                freeze_hash="a" * 64,
                persistence_rule=rule,
                contract_hash="b" * 64,
            ),
        )
    )
    digest = live.append_correction_v2(
        _v2(
            "corr",
            EventTypeV2.CORRECTION_RECORDED,
            CorrectionPayload(
                target_event_id="f1",
                reason="fix",
                authorization_role="lead",
                invalidation=True,
            ),
            obligations=[],
        )
    )
    assert isinstance(digest, str)
    assert live.events_v2(project_id="proj")
    assert live.events_v2(project_id="missing") == []

    # Force default branch of _V2_TO_LEGACY_TYPE.get(...)
    class _FakeType:
        value = "NOT_A_REAL_TYPE"

    fake_evt = UtilityEventV2.model_construct(
        event_id="fx",
        event_type=_FakeType(),  # type: ignore[arg-type]
        project_id="p",
        artifact_id="a",
        obligation_ids=[],
        occurred_at=NOW,
        recorded_at=NOW,
        actor_id="op",
        payload=ExpertTimePayload(
            hours=1.0,
            minutes=60.0,
            category="review",
            measurement_confidence="exact_timer",
        ),
    )
    projected = LedgerStore._as_legacy_event(fake_evt)
    assert projected.event_type is EventType.CORRECTION_RECORDED

    # events.py: unsupported event_type branch
    with pytest.raises(ValueError, match="unsupported event_type"):
        UtilityEventV2.payload_matches_event_type(fake_evt)

    with pytest.raises(LedgerTransitionError):
        live.append_correction_v2(
            _v2(
                "bad",
                EventTypeV2.EXPERT_TIME_RECORDED,
                ExpertTimePayload(
                    hours=1.0,
                    minutes=60.0,
                    category="review",
                    measurement_confidence="exact_timer",
                ),
                obligations=[],
            )
        )
