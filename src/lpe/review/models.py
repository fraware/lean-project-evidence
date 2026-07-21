"""Dimension-specific review attestation models (CLOSURE-021)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from lpe.hashing import sha256_value
from lpe.models import ReviewDecisionValue, StrictModel, VersionedStrictModel


class ReviewDimension(StrEnum):
    SEMANTIC_FIDELITY = "SEMANTIC_FIDELITY"
    REPOSITORY_FIT = "REPOSITORY_FIT"
    IMPLEMENTATION_QUALITY = "IMPLEMENTATION_QUALITY"
    DOWNSTREAM_VALUE = "DOWNSTREAM_VALUE"
    ADJUDICATION = "ADJUDICATION"


class ReviewAttestationV2(VersionedStrictModel):
    """Single-dimension attestation (§12.2). One record = one dimension only."""

    schema_version: Literal["0.2.0"] = "0.2.0"
    attestation_id: str
    packet_id: str
    evidence_fingerprint: str
    reviewer_id: str
    reviewer_role: str
    dimension: ReviewDimension
    decision: ReviewDecisionValue
    confidence: int = Field(ge=0, le=100)
    rationale: str
    finding_refs: list[str] = Field(default_factory=list)
    conflict_declaration_hash: str
    blinded_condition: str = "UNBLINDED"
    review_started_at: datetime
    review_submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    review_minutes: float = Field(gt=0)

    @field_validator("evidence_fingerprint", "conflict_declaration_hash")
    @classmethod
    def non_empty_hashes(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("evidence_fingerprint and conflict_declaration_hash are mandatory")
        return cleaned

    @field_validator("review_started_at", "review_submitted_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def single_dimension_only(self) -> ReviewAttestationV2:
        # Structural guarantee: model has exactly one dimension field (enum).
        # Reject multi-dimension smuggling via finding_refs metadata conventions.
        if "," in self.dimension.value:
            raise ValueError("one attestation cannot cover multiple dimensions")
        return self

    def content_fingerprint(self) -> str:
        """Stable hash over attestation identity fields (excludes wall-clock submit)."""
        return sha256_value(
            {
                "attestation_id": self.attestation_id,
                "packet_id": self.packet_id,
                "evidence_fingerprint": self.evidence_fingerprint,
                "reviewer_id": self.reviewer_id,
                "reviewer_role": self.reviewer_role,
                "dimension": self.dimension.value,
                "decision": self.decision.value,
                "confidence": self.confidence,
                "conflict_declaration_hash": self.conflict_declaration_hash,
                "finding_refs": self.finding_refs,
            }
        )


class QuorumRequirement(StrictModel):
    dimension: ReviewDimension
    reviewer_role: str
    decision: ReviewDecisionValue = ReviewDecisionValue.ACCEPT


class QuorumPolicy(StrictModel):
    policy_id: str
    risk_class: str
    requirements: list[QuorumRequirement]
    require_distinct_reviewers: bool = True
    allow_auto_accept: bool = False
