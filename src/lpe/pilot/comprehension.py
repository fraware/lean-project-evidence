"""Reviewer calibration and comprehension (CLOSURE-028).

Five external calibration cases; pass rules §15.8; one retry; second fail
excludes from primary analysis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator

from lpe.hashing import sha256_value
from lpe.models import StrictModel
from lpe.pilot.protocol import ComprehensionConfig


class ComprehensionError(ValueError):
    """Raised when comprehension scoring inputs are invalid."""


class MaterialLabel(StrEnum):
    MATERIAL_DEFECT = "material_defect"
    NO_MATERIAL_DEFECT = "no_material_defect"


class EvidenceBasisAnswer(StrEnum):
    KERNEL_CHECKED = "KERNEL_CHECKED"
    ELABORATOR_EXTRACTED = "ELABORATOR_EXTRACTED"
    EXECUTED_TEST = "EXECUTED_TEST"
    STRUCTURAL_COMPARISON = "STRUCTURAL_COMPARISON"
    HEURISTIC_RETRIEVAL = "HEURISTIC_RETRIEVAL"
    HUMAN_ATTESTED = "HUMAN_ATTESTED"
    EXTERNAL_ASSERTION = "EXTERNAL_ASSERTION"


class CalibrationCase(StrictModel):
    case_id: str
    adjudicated_material: MaterialLabel
    adjudicated_basis: EvidenceBasisAnswer
    # If true, confusing semantic-intent with proof-search is a systematic fail.
    traps_semantic_as_proof_search: bool = False


class CaseResponse(StrictModel):
    case_id: str
    material_judgment: MaterialLabel
    basis_answer: EvidenceBasisAnswer
    confused_semantic_with_proof_search: bool = False


class ComprehensionAttempt(StrictModel):
    attempt_number: int = Field(ge=1, le=2)
    responses: list[CaseResponse] = Field(min_length=5, max_length=5)
    conflict_blinding_acknowledged: bool
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("submitted_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("submitted_at must be timezone-aware")
        return value


class ComprehensionResult(StrictModel):
    schema_version: Literal["0.3.0"] = "0.3.0"
    reviewer_id: str
    config_id: str
    attempt_number: int
    material_correct: int
    basis_correct: int
    systematic_semantic_confusion: bool
    conflict_blinding_acknowledged: bool
    passed: bool
    excluded_from_primary: bool
    result_hash: str
    sealed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def score_comprehension(
    *,
    reviewer_id: str,
    config: ComprehensionConfig,
    cases: list[CalibrationCase],
    attempt: ComprehensionAttempt,
    prior_failures: int = 0,
) -> ComprehensionResult:
    """Score one comprehension attempt against adjudicated external cases."""
    if len(cases) != 5:
        raise ComprehensionError("exactly five calibration cases required")
    case_ids = [c.case_id for c in cases]
    if case_ids != list(config.calibration_case_ids):
        raise ComprehensionError("case set must match frozen comprehension config")
    if attempt.attempt_number != prior_failures + 1:
        raise ComprehensionError(
            f"attempt_number {attempt.attempt_number} inconsistent with "
            f"{prior_failures} prior failures"
        )

    by_id = {c.case_id: c for c in cases}
    material_correct = 0
    basis_correct = 0
    systematic = False
    for resp in attempt.responses:
        case = by_id.get(resp.case_id)
        if case is None:
            raise ComprehensionError(f"unknown case_id {resp.case_id}")
        if resp.material_judgment == case.adjudicated_material:
            material_correct += 1
        if resp.basis_answer == case.adjudicated_basis:
            basis_correct += 1
        if case.traps_semantic_as_proof_search and resp.confused_semantic_with_proof_search:
            systematic = True

    passed = (
        material_correct >= config.pass_threshold_material
        and basis_correct >= config.pass_threshold_basis
        and not systematic
        and attempt.conflict_blinding_acknowledged
    )
    excluded = (not passed) and (prior_failures + 1 >= config.max_attempts)

    raw = {
        "reviewer_id": reviewer_id,
        "config_id": config.config_id,
        "attempt_number": attempt.attempt_number,
        "material_correct": material_correct,
        "basis_correct": basis_correct,
        "systematic_semantic_confusion": systematic,
        "conflict_blinding_acknowledged": attempt.conflict_blinding_acknowledged,
        "passed": passed,
        "excluded_from_primary": excluded,
        "responses": [r.model_dump(mode="json") for r in attempt.responses],
    }
    return ComprehensionResult(
        reviewer_id=reviewer_id,
        config_id=config.config_id,
        attempt_number=attempt.attempt_number,
        material_correct=material_correct,
        basis_correct=basis_correct,
        systematic_semantic_confusion=systematic,
        conflict_blinding_acknowledged=attempt.conflict_blinding_acknowledged,
        passed=passed,
        excluded_from_primary=excluded,
        result_hash=sha256_value(raw),
    )
