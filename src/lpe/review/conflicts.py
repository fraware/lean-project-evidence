"""Reviewer conflict declarations and eligibility (CLOSURE-022)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from lpe.hashing import sha256_value
from lpe.models import VersionedStrictModel

DISQUALIFYING_FIELDS = (
    "candidate_author",
    "source_artifact_author",
    "historical_reviewer",
    "direct_collaborator",
    "packet_constructor",
    "outcome_seen_before_review",
)


class ConflictError(ValueError):
    """Raised when an ineligible reviewer attempts primary attestation."""


class ReviewerConflictDeclaration(VersionedStrictModel):
    """Signed conflict questionnaire (§12.3)."""

    schema_version: Literal["0.2.0"] = "0.2.0"
    reviewer_id: str
    project_id: str
    candidate_id: str
    candidate_author: bool = False
    source_artifact_author: bool = False
    historical_reviewer: bool = False
    direct_collaborator: bool = False
    packet_constructor: bool = False
    outcome_seen_before_review: bool = False
    other_conflict: str | None = None
    eligible: bool
    signed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("signed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("signed_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def compute_eligibility(self) -> ReviewerConflictDeclaration:
        computed = True
        for name in DISQUALIFYING_FIELDS:
            if bool(getattr(self, name)):
                computed = False
                break
        if self.other_conflict and self.other_conflict.strip():
            computed = False
        if self.eligible and not computed:
            raise ValueError(
                "eligible=true contradicts disqualifying conflict fields (fail closed)"
            )
        object.__setattr__(self, "eligible", computed)
        return self

    def declaration_hash(self) -> str:
        """Immutable content hash of the conflict declaration."""
        return sha256_value(self.model_dump(mode="json"))


def compute_eligibility(declaration: ReviewerConflictDeclaration) -> bool:
    """``eligible=false`` when any disqualifying field is true or other_conflict set."""
    for name in DISQUALIFYING_FIELDS:
        if bool(getattr(declaration, name)):
            return False
    if declaration.other_conflict and declaration.other_conflict.strip():
        return False
    return True


def require_eligible_for_primary_attestation(
    declaration: ReviewerConflictDeclaration,
) -> str:
    """Return declaration hash or raise if ineligible for primary attestation."""
    if not declaration.eligible or not compute_eligibility(declaration):
        raise ConflictError(
            f"reviewer {declaration.reviewer_id!r} is ineligible for primary "
            "attestation (conflict fail-closed)"
        )
    return declaration.declaration_hash()


def conflict_from_dict(raw: dict[str, Any]) -> ReviewerConflictDeclaration:
    return ReviewerConflictDeclaration.model_validate(raw)
