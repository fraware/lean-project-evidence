from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lpe.evidence.compiler import compile_evidence
from lpe.evidence.router import select_review_question
from lpe.models import (
    CandidateDescriptor,
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    Provenance,
    Recommendation,
    RiskClass,
    Severity,
)


def _finding(
    *,
    check_id: str,
    dimension: EvidenceDimension,
    status: FindingStatus,
) -> EvidenceFinding:
    now = datetime.now(timezone.utc)
    return EvidenceFinding(
        finding_id=f"finding_{check_id}",
        check_id=check_id,
        check_version="0.1.0",
        dimension=dimension,
        status=status,
        severity=Severity.L2,
        summary=check_id,
        provenance=Provenance(
            tool="test",
            tool_version="0",
            input_hash="abc",
            started_at=now,
            finished_at=now,
            elapsed_ms=0,
        ),
    )


def test_semantic_priority_over_repository() -> None:
    findings = [
        _finding(
            check_id="repository.api_fit",
            dimension=EvidenceDimension.REPOSITORY,
            status=FindingStatus.UNKNOWN,
        ),
        _finding(
            check_id="semantic.statement_diff",
            dimension=EvidenceDimension.SEMANTIC,
            status=FindingStatus.UNKNOWN,
        ),
    ]
    question = select_review_question(
        findings=findings,
        risk_class=RiskClass.R3,
        required_roles=["domain-lead"],
        estimated_minutes=30,
    )
    assert question is not None
    assert "mathematical object" in question.question
    assert question.baseline_id == "deterministic_baseline.v1"


def test_r3_always_escalates(example_project: Path, example_candidate) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    assert packet.recommendation is Recommendation.ESCALATE


def test_r3_example_escalates(
    example_project: Path,
    example_candidate,
) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    assert packet.risk_class is RiskClass.R3
    assert packet.recommendation is Recommendation.ESCALATE
    # AUDIT-020: unresolved lean.prohibited_axioms (regex-stub) ⇒ hard gate not passed.
    assert packet.hard_gate_passed is False
    assert packet.review_question is not None
    assert packet.review_question.required_roles == [
        "domain-lead",
        "repository-maintainer",
    ]
    assert packet.review_question.baseline_id == "deterministic_baseline.v1"
    assert packet.evidence_fingerprint
    assert packet.packet_id == f"packet_{packet.evidence_fingerprint}"
    assert any(f.check_id.startswith("semantic.") for f in packet.findings)


def test_private_and_docs_candidates_mark_api_fit_not_applicable(
    example_project: Path,
    repository_root: Path,
) -> None:
    """No public decls → api_fit / declared_use are N/A (not soft UNKNOWN theater)."""
    r0 = CandidateDescriptor.model_validate(
        json.loads(
            (repository_root / "examples" / "candidates" / "R0-comment-only.json").read_text(
                encoding="utf-8"
            )
        )
    )
    r1 = CandidateDescriptor.model_validate(
        json.loads(
            (repository_root / "examples" / "candidates" / "R1-private-lemma.json").read_text(
                encoding="utf-8"
            )
        )
    )
    for candidate in (r0, r1):
        packet = compile_evidence(example_project, candidate, skip_build=True)
        api_fit = next(f for f in packet.findings if f.check_id == "repository.api_fit")
        declared = next(f for f in packet.findings if f.check_id == "downstream.declared_use")
        assert api_fit.status is FindingStatus.NOT_APPLICABLE
        assert declared.status is FindingStatus.NOT_APPLICABLE
    # Public R3 still leaves these unresolved.
    r3 = CandidateDescriptor.model_validate(
        json.loads(
            (repository_root / "examples" / "candidates" / "R3-definition-change.json").read_text(
                encoding="utf-8"
            )
        )
    )
    packet_r3 = compile_evidence(example_project, r3, skip_build=True)
    assert (
        next(f for f in packet_r3.findings if f.check_id == "repository.api_fit").status
        is FindingStatus.UNKNOWN
    )
