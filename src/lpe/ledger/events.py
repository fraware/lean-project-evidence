"""Typed utility ledger events v2 (CLOSURE-018).

Discriminated payloads replace ``payload: dict[str, Any]``. Unknown fields fail
closed via ``StrictModel``. Ambiguous migrated records use ``LEGACY_UNRESOLVED``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter, field_validator, model_validator

from lpe.models import SCHEMA_VERSION, ReviewDecisionValue, StrictModel, VersionedStrictModel

LEGACY_UNRESOLVED = "LEGACY_UNRESOLVED"


class EventTypeV2(StrEnum):
    """Lifecycle + side-channel event types for ledger 0.2.0."""

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
    EXPERT_TIME_RECORDED = "EXPERT_TIME_RECORDED"
    OVERHEAD_SNAPSHOT = "OVERHEAD_SNAPSHOT"
    CORRECTION_RECORDED = "CORRECTION_RECORDED"
    PROTOCOL_FROZEN = "PROTOCOL_FROZEN"
    CONDITION_ASSIGNED = "CONDITION_ASSIGNED"
    LEGACY_UNRESOLVED = "LEGACY_UNRESOLVED"


class PersistenceRule(StrictModel):
    """Persistence window attached to an obligation freeze (§14.2)."""

    rule_id: str
    mode: Literal["calendar_days", "repository_commits", "release_boundary"]
    threshold: int | str
    required_downstream_suite_ids: list[str] = Field(default_factory=list)
    regression_policy: Literal["revoke", "suspend", "retain_with_flag"] = "revoke"


class ObligationFreezePayload(StrictModel):
    payload_type: Literal["ObligationFreezePayload"] = "ObligationFreezePayload"
    freeze_id: str
    obligation_ids: list[str] = Field(min_length=1)
    freeze_hash: str
    persistence_rule: PersistenceRule
    contract_hash: str
    # Optional per-obligation weights for TPPR v2; missing → weight 1.0 (CLOSURE-025).
    obligation_weights: dict[str, float] = Field(default_factory=dict)


class CandidateRegisteredPayload(StrictModel):
    payload_type: Literal["CandidateRegisteredPayload"] = "CandidateRegisteredPayload"
    candidate_id: str
    root_candidate_id: str
    freeze_id: str
    base_ref: str
    head_ref: str
    tree_hash: str
    risk_class: str
    prior_candidate_id: str | None = None
    repair_sequence: int = 0


class EvidenceCompiledPayload(StrictModel):
    payload_type: Literal["EvidenceCompiledPayload"] = "EvidenceCompiledPayload"
    packet_id: str
    evidence_fingerprint: str
    candidate_id: str
    run_manifest_hash: str
    finding_count: int = Field(ge=0)


class ReviewAssignedPayload(StrictModel):
    payload_type: Literal["ReviewAssignedPayload"] = "ReviewAssignedPayload"
    assignment_id: str
    packet_id: str
    evidence_fingerprint: str
    reviewer_id: str
    reviewer_role: str
    dimension: str
    risk_class: str


class ReviewAttestationPayload(StrictModel):
    payload_type: Literal["ReviewAttestationPayload"] = "ReviewAttestationPayload"
    attestation_id: str
    packet_id: str
    evidence_fingerprint: str
    reviewer_id: str
    reviewer_role: str
    dimension: str
    decision: ReviewDecisionValue
    confidence: int = Field(ge=0, le=100)
    conflict_declaration_hash: str
    finding_refs: list[str] = Field(default_factory=list)


class RepairRequestedPayload(StrictModel):
    payload_type: Literal["RepairRequestedPayload"] = "RepairRequestedPayload"
    repair_request_id: str
    candidate_id: str
    attestation_ids: list[str] = Field(min_length=1)
    rationale: str
    required_change: str | None = None


class RepairCompletedPayload(StrictModel):
    payload_type: Literal["RepairCompletedPayload"] = "RepairCompletedPayload"
    repair_request_id: str
    prior_candidate_id: str
    new_candidate_id: str
    applied_change_hash: str
    new_evidence_fingerprint: str | None = None


class AcceptanceAggregatedPayload(StrictModel):
    payload_type: Literal["AcceptanceAggregatedPayload"] = "AcceptanceAggregatedPayload"
    attestation_ids: list[str] = Field(min_length=0)
    quorum_policy_id: str
    evidence_fingerprint: str
    semantic_fidelity: bool
    repository_accepted: bool
    implementation_accepted: bool
    accepted_obligation_ids: list[str] = Field(default_factory=list)
    accepted_at: datetime
    risk_class: str

    @field_validator("accepted_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("accepted_at must be timezone-aware")
        return value


class IntegrationConfirmedPayload(StrictModel):
    payload_type: Literal["IntegrationConfirmedPayload"] = "IntegrationConfirmedPayload"
    candidate_id: str
    integration_ref: str
    merged_at: datetime | None = None


class DownstreamEnabledPayload(StrictModel):
    payload_type: Literal["DownstreamEnabledPayload"] = "DownstreamEnabledPayload"
    candidate_id: str
    suite_ids: list[str] = Field(min_length=1)
    evidence_fingerprint: str


class PersistenceConfirmedPayload(StrictModel):
    payload_type: Literal["PersistenceConfirmedPayload"] = "PersistenceConfirmedPayload"
    candidate_id: str
    persistence_rule_id: str
    confirmed_at: datetime
    window_elapsed: bool = True


class RegressionDetectedPayload(StrictModel):
    payload_type: Literal["RegressionDetectedPayload"] = "RegressionDetectedPayload"
    candidate_id: str
    regression_id: str
    suite_id: str | None = None
    severity: Literal["blocking", "warning"] = "blocking"
    summary: str


class ExpertTimePayload(StrictModel):
    payload_type: Literal["ExpertTimePayload"] = "ExpertTimePayload"
    hours: float = Field(ge=0)
    minutes: float = Field(ge=0)
    category: str
    condition_tag: str | None = None
    measurement_confidence: Literal[
        "exact_timer", "contemporaneous_entry", "retrospective_estimate"
    ] = "contemporaneous_entry"
    evidence_fingerprint: str | None = None


class OverheadSnapshotPayload(StrictModel):
    payload_type: Literal["OverheadSnapshotPayload"] = "OverheadSnapshotPayload"
    snapshot_id: str
    category: str
    minutes: float = Field(ge=0)
    notes: str | None = None


class CorrectionPayload(StrictModel):
    payload_type: Literal["CorrectionPayload"] = "CorrectionPayload"
    target_event_id: str
    reason: str
    authorization_role: str
    invalidation: bool = False
    replacement_payload: dict[str, Any] | None = None


class ProtocolFrozenPayload(StrictModel):
    payload_type: Literal["ProtocolFrozenPayload"] = "ProtocolFrozenPayload"
    protocol_freeze_id: str
    protocol_hash: str
    component_hashes: dict[str, str] = Field(default_factory=dict)


class ConditionAssignedPayload(StrictModel):
    payload_type: Literal["ConditionAssignedPayload"] = "ConditionAssignedPayload"
    condition_assignment_id: str
    condition_tag: str
    candidate_id: str
    assignment_hash: str


class LegacyUnresolvedPayload(StrictModel):
    """Typed wrapper for ambiguous 0.1→0.2 migrations (never invents acceptance)."""

    payload_type: Literal["LegacyUnresolvedPayload"] = "LegacyUnresolvedPayload"
    legacy_event_type: str
    legacy_payload: dict[str, Any] = Field(default_factory=dict)
    unresolved_fields: list[str] = Field(default_factory=lambda: [LEGACY_UNRESOLVED])
    migration_note: str = LEGACY_UNRESOLVED


EventPayload = Annotated[
    (
        ObligationFreezePayload
        | CandidateRegisteredPayload
        | EvidenceCompiledPayload
        | ReviewAssignedPayload
        | ReviewAttestationPayload
        | RepairRequestedPayload
        | RepairCompletedPayload
        | AcceptanceAggregatedPayload
        | IntegrationConfirmedPayload
        | DownstreamEnabledPayload
        | PersistenceConfirmedPayload
        | RegressionDetectedPayload
        | ExpertTimePayload
        | OverheadSnapshotPayload
        | CorrectionPayload
        | ProtocolFrozenPayload
        | ConditionAssignedPayload
        | LegacyUnresolvedPayload
    ),
    Field(discriminator="payload_type"),
]

_PAYLOAD_ADAPTER: TypeAdapter[EventPayload] = TypeAdapter(EventPayload)

EVENT_TYPE_TO_PAYLOAD: dict[EventTypeV2, str] = {
    EventTypeV2.OBLIGATION_FROZEN: "ObligationFreezePayload",
    EventTypeV2.CANDIDATE_REGISTERED: "CandidateRegisteredPayload",
    EventTypeV2.EVIDENCE_COMPILED: "EvidenceCompiledPayload",
    EventTypeV2.REVIEW_ASSIGNED: "ReviewAssignedPayload",
    EventTypeV2.REVIEW_ATTESTED: "ReviewAttestationPayload",
    EventTypeV2.REPAIR_REQUESTED: "RepairRequestedPayload",
    EventTypeV2.REPAIR_COMPLETED: "RepairCompletedPayload",
    EventTypeV2.ARTIFACT_ACCEPTED: "AcceptanceAggregatedPayload",
    EventTypeV2.ARTIFACT_REJECTED: "ReviewAttestationPayload",
    EventTypeV2.INTEGRATION_CONFIRMED: "IntegrationConfirmedPayload",
    EventTypeV2.DOWNSTREAM_ENABLED: "DownstreamEnabledPayload",
    EventTypeV2.PERSISTENCE_CONFIRMED: "PersistenceConfirmedPayload",
    EventTypeV2.REGRESSION_DETECTED: "RegressionDetectedPayload",
    EventTypeV2.EXPERT_TIME_RECORDED: "ExpertTimePayload",
    EventTypeV2.OVERHEAD_SNAPSHOT: "OverheadSnapshotPayload",
    EventTypeV2.CORRECTION_RECORDED: "CorrectionPayload",
    EventTypeV2.PROTOCOL_FROZEN: "ProtocolFrozenPayload",
    EventTypeV2.CONDITION_ASSIGNED: "ConditionAssignedPayload",
    EventTypeV2.LEGACY_UNRESOLVED: "LegacyUnresolvedPayload",
}

# Side-channel events that do not advance the artifact lifecycle reducer.
SIDE_CHANNEL_EVENT_TYPES: frozenset[EventTypeV2] = frozenset(
    {
        EventTypeV2.EXPERT_TIME_RECORDED,
        EventTypeV2.OVERHEAD_SNAPSHOT,
        EventTypeV2.CORRECTION_RECORDED,
        EventTypeV2.PROTOCOL_FROZEN,
        EventTypeV2.CONDITION_ASSIGNED,
        EventTypeV2.LEGACY_UNRESOLVED,
    }
)


def parse_event_payload(raw: dict[str, Any] | EventPayload) -> EventPayload:
    """Validate a payload dict against the discriminated union (unknown fields fail)."""
    if not isinstance(raw, dict):
        return raw
    return _PAYLOAD_ADAPTER.validate_python(raw)


class UtilityEventV2(VersionedStrictModel):
    """Typed ledger envelope (§13.2)."""

    schema_version: Literal["0.2.0"] = "0.2.0"
    event_id: str
    event_type: EventTypeV2
    project_id: str
    artifact_id: str
    obligation_ids: list[str] = Field(default_factory=list)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor_id: str
    protocol_freeze_id: str | None = None
    condition_assignment_id: str | None = None
    payload: EventPayload
    supersedes_event_id: str | None = None

    @field_validator("occurred_at", "recorded_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value

    @field_validator("schema_version")
    @classmethod
    def only_v2(cls, value: str) -> str:
        if value != SCHEMA_VERSION and value != "0.2.0":
            raise ValueError(f"UtilityEventV2 requires schema_version 0.2.0, got {value!r}")
        return "0.2.0"

    @model_validator(mode="after")
    def payload_matches_event_type(self) -> UtilityEventV2:
        expected = EVENT_TYPE_TO_PAYLOAD.get(self.event_type)
        actual = getattr(self.payload, "payload_type", None)
        if expected is None:
            raise ValueError(f"unsupported event_type {self.event_type!r}")
        if actual != expected:
            # ARTIFACT_REJECTED may carry attestation or a minimal reject payload;
            # allow LegacyUnresolved for migration only.
            if self.event_type is EventTypeV2.ARTIFACT_REJECTED and actual in {
                "ReviewAttestationPayload",
                "LegacyUnresolvedPayload",
            }:
                return self
            raise ValueError(
                f"event_type {self.event_type.value} requires payload_type "
                f"{expected!r}, got {actual!r}"
            )
        return self

    def payload_dict(self) -> dict[str, Any]:
        return self.payload.model_dump(mode="json")
