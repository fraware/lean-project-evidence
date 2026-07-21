"""Artifact/obligation lifecycle reducers (CLOSURE-019).

Invalid transitions are rejected at append time. Corrections never mutate
history; obligation freezes are immutable per candidate.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from lpe.ledger.events import (
    SIDE_CHANNEL_EVENT_TYPES,
    CandidateRegisteredPayload,
    CorrectionPayload,
    EventTypeV2,
    ObligationFreezePayload,
    RepairCompletedPayload,
    UtilityEventV2,
)


class LifecycleError(ValueError):
    """Raised when an event would violate the lifecycle state machine."""


class ArtifactPhase(StrEnum):
    """Lifecycle phase for a single artifact lineage tip."""

    EMPTY = "EMPTY"
    OBLIGATION_FROZEN = "OBLIGATION_FROZEN"
    CANDIDATE_REGISTERED = "CANDIDATE_REGISTERED"
    EVIDENCE_COMPILED = "EVIDENCE_COMPILED"
    REVIEW_ASSIGNED = "REVIEW_ASSIGNED"
    REVIEW_ATTESTED = "REVIEW_ATTESTED"
    REPAIR_REQUESTED = "REPAIR_REQUESTED"
    REPAIR_COMPLETED = "REPAIR_COMPLETED"
    ARTIFACT_ACCEPTED = "ARTIFACT_ACCEPTED"
    ARTIFACT_REJECTED = "ARTIFACT_REJECTED"
    INTEGRATION_CONFIRMED = "INTEGRATION_CONFIRMED"
    DOWNSTREAM_ENABLED = "DOWNSTREAM_ENABLED"
    PERSISTENCE_CONFIRMED = "PERSISTENCE_CONFIRMED"
    REGRESSION_DETECTED = "REGRESSION_DETECTED"


# Lifecycle advances (side-channel types omitted).
_TRANSITIONS: dict[ArtifactPhase, frozenset[EventTypeV2]] = {
    # Repair lineage may register a new artifact tip under an existing freeze_id.
    ArtifactPhase.EMPTY: frozenset(
        {EventTypeV2.OBLIGATION_FROZEN, EventTypeV2.CANDIDATE_REGISTERED}
    ),
    ArtifactPhase.OBLIGATION_FROZEN: frozenset({EventTypeV2.CANDIDATE_REGISTERED}),
    ArtifactPhase.CANDIDATE_REGISTERED: frozenset({EventTypeV2.EVIDENCE_COMPILED}),
    ArtifactPhase.EVIDENCE_COMPILED: frozenset(
        {
            EventTypeV2.REVIEW_ASSIGNED,
            EventTypeV2.ARTIFACT_ACCEPTED,  # R0 auto-accept aggregate
        }
    ),
    ArtifactPhase.REVIEW_ASSIGNED: frozenset(
        {
            EventTypeV2.REVIEW_ASSIGNED,
            EventTypeV2.REVIEW_ATTESTED,
        }
    ),
    ArtifactPhase.REVIEW_ATTESTED: frozenset(
        {
            EventTypeV2.REVIEW_ATTESTED,
            EventTypeV2.ARTIFACT_ACCEPTED,
            EventTypeV2.REPAIR_REQUESTED,
            EventTypeV2.ARTIFACT_REJECTED,
        }
    ),
    ArtifactPhase.REPAIR_REQUESTED: frozenset({EventTypeV2.REPAIR_COMPLETED}),
    # Prior tip closed; new candidate_id registers on a new artifact_id.
    ArtifactPhase.REPAIR_COMPLETED: frozenset(),
    ArtifactPhase.ARTIFACT_ACCEPTED: frozenset({EventTypeV2.INTEGRATION_CONFIRMED}),
    ArtifactPhase.ARTIFACT_REJECTED: frozenset(),
    ArtifactPhase.INTEGRATION_CONFIRMED: frozenset({EventTypeV2.DOWNSTREAM_ENABLED}),
    ArtifactPhase.DOWNSTREAM_ENABLED: frozenset(
        {
            EventTypeV2.PERSISTENCE_CONFIRMED,
            EventTypeV2.REGRESSION_DETECTED,
        }
    ),
    ArtifactPhase.PERSISTENCE_CONFIRMED: frozenset({EventTypeV2.REGRESSION_DETECTED}),
    ArtifactPhase.REGRESSION_DETECTED: frozenset(),
}

_EVENT_TO_PHASE: dict[EventTypeV2, ArtifactPhase] = {
    EventTypeV2.OBLIGATION_FROZEN: ArtifactPhase.OBLIGATION_FROZEN,
    EventTypeV2.CANDIDATE_REGISTERED: ArtifactPhase.CANDIDATE_REGISTERED,
    EventTypeV2.EVIDENCE_COMPILED: ArtifactPhase.EVIDENCE_COMPILED,
    EventTypeV2.REVIEW_ASSIGNED: ArtifactPhase.REVIEW_ASSIGNED,
    EventTypeV2.REVIEW_ATTESTED: ArtifactPhase.REVIEW_ATTESTED,
    EventTypeV2.REPAIR_REQUESTED: ArtifactPhase.REPAIR_REQUESTED,
    EventTypeV2.REPAIR_COMPLETED: ArtifactPhase.REPAIR_COMPLETED,
    EventTypeV2.ARTIFACT_ACCEPTED: ArtifactPhase.ARTIFACT_ACCEPTED,
    EventTypeV2.ARTIFACT_REJECTED: ArtifactPhase.ARTIFACT_REJECTED,
    EventTypeV2.INTEGRATION_CONFIRMED: ArtifactPhase.INTEGRATION_CONFIRMED,
    EventTypeV2.DOWNSTREAM_ENABLED: ArtifactPhase.DOWNSTREAM_ENABLED,
    EventTypeV2.PERSISTENCE_CONFIRMED: ArtifactPhase.PERSISTENCE_CONFIRMED,
    EventTypeV2.REGRESSION_DETECTED: ArtifactPhase.REGRESSION_DETECTED,
}


@dataclass
class ObligationFreezeRecord:
    freeze_id: str
    freeze_hash: str
    obligation_ids: tuple[str, ...]
    active: bool = True


@dataclass
class ArtifactLifecycleState:
    """Reducer state for one artifact_id chain."""

    phase: ArtifactPhase = ArtifactPhase.EMPTY
    active_freeze_id: str | None = None
    active_freeze_hash: str | None = None
    candidate_id: str | None = None
    root_candidate_id: str | None = None
    attestation_ids: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)


@dataclass
class LedgerReducerState:
    """In-memory projection used to validate appends."""

    artifacts: dict[str, ArtifactLifecycleState] = field(default_factory=dict)
    freezes_by_id: dict[str, ObligationFreezeRecord] = field(default_factory=dict)
    # freeze_id → candidate_ids governed (immutability: cannot rebind)
    freeze_candidates: dict[str, set[str]] = field(default_factory=dict)
    known_event_ids: set[str] = field(default_factory=set)
    # Deterministic correction application order (event_id of corrections).
    correction_order: list[str] = field(default_factory=list)

    def artifact_state(self, artifact_id: str) -> ArtifactLifecycleState:
        if artifact_id not in self.artifacts:
            self.artifacts[artifact_id] = ArtifactLifecycleState()
        return self.artifacts[artifact_id]


def reduce_event(state: LedgerReducerState, event: UtilityEventV2) -> LedgerReducerState:
    """Apply ``event`` to ``state`` or raise ``LifecycleError``.

    Returns the same state object after in-place mutation (for chaining).
    """
    if event.event_id in state.known_event_ids:
        raise LifecycleError(f"duplicate event_id {event.event_id!r}")

    if event.supersedes_event_id is not None:
        if event.supersedes_event_id not in state.known_event_ids:
            raise LifecycleError(
                f"event {event.event_id} supersedes unknown event {event.supersedes_event_id}"
            )

    if event.event_type in SIDE_CHANNEL_EVENT_TYPES:
        _apply_side_channel(state, event)
        state.known_event_ids.add(event.event_id)
        return state

    art = state.artifact_state(event.artifact_id)
    allowed = _TRANSITIONS.get(art.phase, frozenset())
    if event.event_type not in allowed:
        raise LifecycleError(
            f"invalid transition for artifact {event.artifact_id!r}: "
            f"phase={art.phase.value} cannot accept {event.event_type.value}"
        )

    if event.event_type is EventTypeV2.OBLIGATION_FROZEN:
        _apply_obligation_frozen(state, art, event)
    elif event.event_type is EventTypeV2.CANDIDATE_REGISTERED:
        _apply_candidate_registered(state, art, event)
    elif event.event_type is EventTypeV2.REVIEW_ATTESTED:
        _apply_review_attested(art, event)
    elif event.event_type is EventTypeV2.REPAIR_COMPLETED:
        _apply_repair_completed(art, event)
    else:
        art.phase = _EVENT_TO_PHASE[event.event_type]

    art.event_ids.append(event.event_id)
    state.known_event_ids.add(event.event_id)
    return state


def _apply_side_channel(state: LedgerReducerState, event: UtilityEventV2) -> None:
    if event.event_type is EventTypeV2.CORRECTION_RECORDED:
        payload = event.payload
        if not isinstance(payload, CorrectionPayload):
            raise LifecycleError("CORRECTION_RECORDED requires CorrectionPayload")
        if payload.target_event_id not in state.known_event_ids:
            raise LifecycleError(
                f"correction {event.event_id} targets unknown event {payload.target_event_id}"
            )
        if not payload.reason.strip():
            raise LifecycleError("correction reason must be non-empty")
        if not payload.authorization_role.strip():
            raise LifecycleError("correction authorization_role must be non-empty")
        if payload.invalidation is False and payload.replacement_payload is None:
            raise LifecycleError(
                "correction must set invalidation=True or provide replacement_payload"
            )
        state.correction_order.append(event.event_id)
        art = state.artifact_state(event.artifact_id)
        art.corrections.append(event.event_id)
    # Other side channels are append-only annotations; no phase change.


def _apply_obligation_frozen(
    state: LedgerReducerState,
    art: ArtifactLifecycleState,
    event: UtilityEventV2,
) -> None:
    payload = event.payload
    if not isinstance(payload, ObligationFreezePayload):
        raise LifecycleError("OBLIGATION_FROZEN requires ObligationFreezePayload")
    if payload.freeze_id in state.freezes_by_id:
        raise LifecycleError(f"freeze_id {payload.freeze_id!r} already exists (immutable)")
    state.freezes_by_id[payload.freeze_id] = ObligationFreezeRecord(
        freeze_id=payload.freeze_id,
        freeze_hash=payload.freeze_hash,
        obligation_ids=tuple(payload.obligation_ids),
        active=True,
    )
    art.phase = ArtifactPhase.OBLIGATION_FROZEN
    art.active_freeze_id = payload.freeze_id
    art.active_freeze_hash = payload.freeze_hash


def _apply_candidate_registered(
    state: LedgerReducerState,
    art: ArtifactLifecycleState,
    event: UtilityEventV2,
) -> None:
    payload = event.payload
    if not isinstance(payload, CandidateRegisteredPayload):
        raise LifecycleError("CANDIDATE_REGISTERED requires CandidateRegisteredPayload")
    freeze = state.freezes_by_id.get(payload.freeze_id)
    if freeze is None:
        raise LifecycleError(f"candidate references unknown freeze_id {payload.freeze_id!r}")
    if art.phase is ArtifactPhase.EMPTY:
        # Repair / forked tip: must reference an already-recorded freeze.
        pass
    elif art.active_freeze_id is not None and art.active_freeze_id != payload.freeze_id:
        raise LifecycleError(
            f"candidate cannot switch freeze from {art.active_freeze_id!r} to {payload.freeze_id!r}"
        )
    governed = state.freeze_candidates.setdefault(payload.freeze_id, set())
    art.phase = ArtifactPhase.CANDIDATE_REGISTERED
    art.active_freeze_id = payload.freeze_id
    art.active_freeze_hash = freeze.freeze_hash
    art.candidate_id = payload.candidate_id
    art.root_candidate_id = payload.root_candidate_id
    art.attestation_ids = []  # prior attestations do not transfer
    governed.add(payload.candidate_id)


def _apply_review_attested(art: ArtifactLifecycleState, event: UtilityEventV2) -> None:
    from lpe.ledger.events import ReviewAttestationPayload

    payload = event.payload
    if not isinstance(payload, ReviewAttestationPayload):
        raise LifecycleError("REVIEW_ATTESTED requires ReviewAttestationPayload")
    art.phase = ArtifactPhase.REVIEW_ATTESTED
    art.attestation_ids.append(payload.attestation_id)


def _apply_repair_completed(art: ArtifactLifecycleState, event: UtilityEventV2) -> None:
    payload = event.payload
    if not isinstance(payload, RepairCompletedPayload):
        raise LifecycleError("REPAIR_COMPLETED requires RepairCompletedPayload")
    art.phase = ArtifactPhase.REPAIR_COMPLETED
    # Lineage tip closed; new candidate registers under new artifact_id.


def fold_events(events: Iterable[UtilityEventV2]) -> LedgerReducerState:
    """Fold a sequence of V2 events into reducer state (property-test helper)."""
    state = LedgerReducerState()
    for event in events:
        reduce_event(state, event)
    return state


def validate_event_against_history(
    history: Iterable[UtilityEventV2],
    new_event: UtilityEventV2,
) -> None:
    """Validate that ``new_event`` is a legal append given ``history``."""
    state = fold_events(history)
    reduce_event(state, new_event)


def apply_corrections_deterministically(
    events: list[UtilityEventV2],
) -> dict[str, UtilityEventV2 | None]:
    """Return effective event map after ordered corrections.

    Keys are original event_ids. Value is ``None`` when invalidated, else the
    original event (replacement payloads are recorded but do not mutate history;
    consumers read corrections in ``correction_order``).
    """
    state = fold_events(events)
    by_id = {event.event_id: event for event in events}
    effective: dict[str, UtilityEventV2 | None] = {
        event_id: event for event_id, event in by_id.items()
    }
    for correction_id in state.correction_order:
        correction = by_id[correction_id]
        payload = correction.payload
        assert isinstance(payload, CorrectionPayload)
        if payload.invalidation:
            effective[payload.target_event_id] = None
        # Replacement is advisory metadata; history stays immutable.
    return effective
