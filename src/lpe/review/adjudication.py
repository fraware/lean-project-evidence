"""Independent adjudication for review disagreements (CLOSURE-024)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from lpe.models import ReviewDecisionValue, VersionedStrictModel
from lpe.review.conflicts import (
    ConflictError,
    ReviewerConflictDeclaration,
    require_eligible_for_primary_attestation,
)
from lpe.review.models import ReviewAttestationV2, ReviewDimension


class AdjudicationError(ValueError):
    """Raised when adjudication rules are violated."""


ADJUDICATOR_ROLE = "adjudicator"


class ProvisionalJudgment(VersionedStrictModel):
    """Independent provisional judgment recorded *before* seeing peer attestations."""

    schema_version: Literal["0.2.0"] = "0.2.0"
    judgment_id: str
    adjudicator_id: str
    packet_id: str
    evidence_fingerprint: str
    provisional_decision: ReviewDecisionValue
    rationale: str
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    peer_attestations_revealed: bool = False

    @field_validator("recorded_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def must_be_blind_at_creation(self) -> ProvisionalJudgment:
        if self.peer_attestations_revealed:
            raise ValueError(
                "provisional judgment must be recorded before peer attestations are revealed"
            )
        return self


class AdjudicationRecord(VersionedStrictModel):
    """Final adjudication after independent provisional judgment."""

    schema_version: Literal["0.2.0"] = "0.2.0"
    adjudication_id: str
    packet_id: str
    evidence_fingerprint: str
    adjudicator_id: str
    provisional_judgment_id: str
    original_attestation_ids: list[str] = Field(min_length=1)
    decision: ReviewDecisionValue
    rationale: str
    conflict_declaration_hash: str
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def validate_adjudicator(
    *,
    adjudicator_id: str,
    adjudicator_roles: list[str],
    original_reviewer_ids: list[str],
    conflict: ReviewerConflictDeclaration,
) -> str:
    """Enforce adjudicator conflict rules; return conflict declaration hash."""
    if adjudicator_id in original_reviewer_ids:
        raise AdjudicationError(f"adjudicator {adjudicator_id!r} was an original reviewer")
    if ADJUDICATOR_ROLE not in adjudicator_roles:
        raise AdjudicationError(
            f"adjudicator {adjudicator_id!r} lacks configured role {ADJUDICATOR_ROLE!r}"
        )
    try:
        return require_eligible_for_primary_attestation(conflict)
    except ConflictError as exc:
        raise AdjudicationError(str(exc)) from exc


def reveal_peer_attestations(
    provisional: ProvisionalJudgment,
    peer_attestations: list[ReviewAttestationV2],
) -> ProvisionalJudgment:
    """Allow viewing peer attestations only after provisional judgment exists."""
    if provisional.peer_attestations_revealed:
        return provisional
    if not peer_attestations:
        raise AdjudicationError("no peer attestations to reveal")
    return provisional.model_copy(update={"peer_attestations_revealed": True})


def build_adjudication_attestation(
    record: AdjudicationRecord,
    *,
    reviewer_role: str = ADJUDICATOR_ROLE,
    review_minutes: float,
    review_started_at: datetime | None = None,
) -> ReviewAttestationV2:
    """Materialize an ADJUDICATION-dimension attestation from a resolved record."""
    started = review_started_at or record.resolved_at
    return ReviewAttestationV2(
        attestation_id=f"attest_adj_{record.adjudication_id}",
        packet_id=record.packet_id,
        evidence_fingerprint=record.evidence_fingerprint,
        reviewer_id=record.adjudicator_id,
        reviewer_role=reviewer_role,
        dimension=ReviewDimension.ADJUDICATION,
        decision=record.decision,
        confidence=100,
        rationale=record.rationale,
        finding_refs=list(record.original_attestation_ids),
        conflict_declaration_hash=record.conflict_declaration_hash,
        review_started_at=started,
        review_submitted_at=record.resolved_at,
        review_minutes=review_minutes,
    )


def auditable_lineage(
    *,
    provisional: ProvisionalJudgment,
    record: AdjudicationRecord,
    peer_attestations: list[ReviewAttestationV2],
) -> dict[str, object]:
    """Return an auditable adjudication lineage bundle."""
    if not provisional.peer_attestations_revealed:
        raise AdjudicationError(
            "lineage requires peer attestations revealed after provisional judgment"
        )
    if provisional.judgment_id != record.provisional_judgment_id:
        raise AdjudicationError("provisional judgment id mismatch")
    return {
        "provisional_judgment_id": provisional.judgment_id,
        "adjudication_id": record.adjudication_id,
        "adjudicator_id": record.adjudicator_id,
        "original_attestation_ids": list(record.original_attestation_ids),
        "peer_attestation_ids": [a.attestation_id for a in peer_attestations],
        "decision": record.decision.value,
        "evidence_fingerprint": record.evidence_fingerprint,
        "conflict_declaration_hash": record.conflict_declaration_hash,
        "resolved_at": record.resolved_at.isoformat(),
    }
