from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from lpe.evidence.compiler import compile_evidence
from lpe.evidence.gates import decide
from lpe.models import (
    CandidateDescriptor,
    EvidenceDimension,
    EvidenceFinding,
    EvidencePacket,
    FindingStatus,
    GeneratorProvenance,
    Provenance,
    Recommendation,
    RiskClass,
    Severity,
)


@pytest.fixture
def load_candidate(repository_root: Path):
    def _load(name: str) -> CandidateDescriptor:
        path = repository_root / "examples" / "candidates" / name
        return CandidateDescriptor.model_validate(json.loads(path.read_text(encoding="utf-8")))

    return _load


@pytest.fixture
def packet_schema(repository_root: Path) -> dict:
    path = repository_root / "schemas" / "evidence-packet.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_schema_valid(packet: EvidencePacket, schema: dict) -> None:
    Draft202012Validator(schema).validate(json.loads(packet.model_dump_json()))


# Dimensions that routinely force ESCALATE under skip_build / regex-stub extraction.
FORCED_ESCALATE_DIMENSIONS = frozenset(
    {
        "lean.build",  # skip_build → UNKNOWN (hard-relevant)
        "lean.prohibited_axioms",  # regex-stub → UNKNOWN (hard-relevant)
        "repository.api_fit",
        "downstream.declared_use",
        "semantic.duplicate_retrieval",  # empty example corpus
        "downstream.replacement_tests",  # empty cone without Lean sources
    }
)


@pytest.mark.parametrize(
    ("fixture", "expected_risk", "expected_recommendation"),
    [
        ("R0-comment-only.json", RiskClass.R0, Recommendation.ESCALATE),
        ("R1-private-lemma.json", RiskClass.R1, Recommendation.ESCALATE),
        ("R2-public-theorem.json", RiskClass.R2, Recommendation.ESCALATE),
        ("R3-definition-change.json", RiskClass.R3, Recommendation.ESCALATE),
        ("R4-foundational.json", RiskClass.R4, Recommendation.ESCALATE),
    ],
)
def test_golden_packet_matrix(
    example_project: Path,
    load_candidate,
    packet_schema: dict,
    fixture: str,
    expected_risk: RiskClass,
    expected_recommendation: Recommendation,
) -> None:
    candidate = load_candidate(fixture)
    packet = compile_evidence(example_project, candidate, skip_build=True)
    assert packet.risk_class is expected_risk
    assert packet.recommendation is expected_recommendation
    # AUDIT-020: regex-stub axiom UNKNOWN means hard_gate_passed is False.
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    if axiom.status.value == "UNKNOWN":
        assert packet.hard_gate_passed is False
    assert packet.contract_hash
    assert len(packet.findings) >= 10
    for finding in packet.findings:
        assert finding.provenance.input_hash
        assert finding.provenance.tool_version
    _assert_schema_valid(packet, packet_schema)


def test_golden_accept_path_via_gates_and_schema(packet_schema: dict) -> None:
    """AUDIT-029 ACCEPT path: low-risk gate ACCEPT when no UNKNOWN remain.

    End-to-end ``compile_evidence(..., skip_build=True)`` cannot ACCEPT because
    hard-relevant checks stay UNKNOWN (see FORCED_ESCALATE_DIMENSIONS). The
    ACCEPT golden is therefore the gate decision itself plus a schema-valid packet.
    """
    now = datetime.now(timezone.utc)

    def _pass(check_id: str) -> EvidenceFinding:
        return EvidenceFinding(
            finding_id=f"f_{check_id}",
            check_id=check_id,
            check_version="0.1.0",
            dimension=EvidenceDimension.KERNEL,
            status=FindingStatus.PASS,
            severity=Severity.INFO,
            summary="ok",
            provenance=Provenance(
                tool="t",
                tool_version="0",
                input_hash="x",
                started_at=now,
                finished_at=now,
                elapsed_ms=0,
            ),
        )

    findings = [
        _pass("contract.valid"),
        _pass("candidate.obligations"),
        _pass("lean.build"),
        _pass("lean.placeholders"),
        _pass("lean.prohibited_axioms"),
        _pass("repository.changed_paths"),
    ]
    decision = decide(findings, RiskClass.R0, auto_accept_eligible=True)
    assert decision.recommendation is Recommendation.ACCEPT
    assert decision.hard_gate_passed is True

    packet = EvidencePacket(
        packet_id="packet_golden_accept",
        run_id="run_golden_accept",
        project_id="example-category-project",
        contract_hash="0" * 64,
        candidate=CandidateDescriptor(
            candidate_id="candidate-golden-accept",
            project_id="example-category-project",
            obligation_ids=["O-01"],
            base_commit="0" * 40,
            patch_text="+<!-- docs -->\n",
            claimed_intent="documentation only",
            changed_paths=["docs/notes.md"],
            changed_declarations=[],
            generator=GeneratorProvenance(generator_type="human", name="test"),
        ),
        risk_class=RiskClass.R0,
        findings=findings,
        hard_gate_passed=True,
        recommendation=Recommendation.ACCEPT,
        recommendation_reasons=list(decision.reasons),
        unresolved_uncertainty=[],
    )
    _assert_schema_valid(packet, packet_schema)


def test_golden_reject_placeholder_fail(
    example_project: Path,
    load_candidate,
    packet_schema: dict,
) -> None:
    """AUDIT-029 REJECT: hard-fail on prohibited placeholder."""
    candidate = load_candidate("R0-sorry-reject.json")
    packet = compile_evidence(example_project, candidate, skip_build=True)
    placeholders = next(f for f in packet.findings if f.check_id == "lean.placeholders")
    assert placeholders.status is FindingStatus.FAIL
    assert packet.recommendation is Recommendation.REJECT
    assert packet.hard_gate_passed is False
    _assert_schema_valid(packet, packet_schema)


def test_golden_escalate_documents_forced_dimensions(
    example_project: Path,
    load_candidate,
) -> None:
    """AUDIT-029 ESCALATE: document dimensions that force escalate under skip_build."""
    candidate = load_candidate("R0-comment-only.json")
    packet = compile_evidence(example_project, candidate, skip_build=True)
    assert packet.recommendation is Recommendation.ESCALATE
    unknown_ids = {f.check_id for f in packet.findings if f.status is FindingStatus.UNKNOWN}
    # At least the hard-relevant skip_build / axiom unknowns must be present.
    assert "lean.build" in unknown_ids
    overlap = unknown_ids & FORCED_ESCALATE_DIMENSIONS
    assert overlap, f"expected forced escalate unknowns, got {unknown_ids}"


def test_r3_has_semantic_finding(example_project: Path, load_candidate) -> None:
    candidate = load_candidate("R3-definition-change.json")
    packet = compile_evidence(example_project, candidate, skip_build=True)
    semantic = [f for f in packet.findings if f.dimension.value == "semantic"]
    assert semantic


def test_r4_never_auto_accepts(example_project: Path, load_candidate) -> None:
    candidate = load_candidate("R4-foundational.json")
    packet = compile_evidence(example_project, candidate, skip_build=True)
    assert packet.recommendation is Recommendation.ESCALATE
    assert packet.review_question is not None


def test_sandbox_isolation_not_applicable_when_skip_build(
    example_project: Path,
    load_candidate,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lpe.execution.sandbox import DockerSandboxExecutor

    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: True))
    candidate = load_candidate("R0-comment-only.json")
    packet = compile_evidence(
        example_project, candidate, skip_build=True, use_sandbox=True
    )
    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    # AUDIT-006: skip_build must not claim isolation PASS.
    assert isolation.status is FindingStatus.NOT_APPLICABLE


def test_build_skipped_honesty_in_packet(
    example_project: Path,
    load_candidate,
    packet_schema: dict,
) -> None:
    """AUDIT-029: packet with build skipped must keep lean.build UNKNOWN."""
    candidate = load_candidate("R1-private-lemma.json")
    packet = compile_evidence(example_project, candidate, skip_build=True)
    build = next(f for f in packet.findings if f.check_id == "lean.build")
    assert build.status is FindingStatus.UNKNOWN
    assert "skipped" in build.summary.lower()
    assert packet.recommendation is Recommendation.ESCALATE
    _assert_schema_valid(packet, packet_schema)
