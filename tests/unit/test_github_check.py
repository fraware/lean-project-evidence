"""GitHub Check adapter tests (AUDIT-018)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from lpe.evidence.compiler import compile_evidence
from lpe.github.check import (
    packet_to_github_check,
    recommendation_to_conclusion,
    render_check_payload,
)
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


def _minimal_packet(*, recommendation: Recommendation, head_commit: str | None) -> EvidencePacket:
    now = datetime.now(timezone.utc)
    finding = EvidenceFinding(
        finding_id="f1",
        check_id="contract.valid",
        check_version="0.1.0",
        dimension=EvidenceDimension.REPOSITORY,
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
    return EvidencePacket(
        packet_id="packet_gh",
        run_id="run_gh",
        project_id="example-category-project",
        contract_hash="0" * 64,
        candidate=CandidateDescriptor(
            candidate_id="candidate-gh",
            project_id="example-category-project",
            obligation_ids=["O-01"],
            base_commit="a" * 40,
            head_commit=head_commit,
            patch_text="+--\n",
            claimed_intent="x",
            changed_paths=[],
            changed_declarations=[],
            generator=GeneratorProvenance(generator_type="human", name="test"),
        ),
        risk_class=RiskClass.R0,
        findings=[finding],
        hard_gate_passed=recommendation is Recommendation.ACCEPT,
        recommendation=recommendation,
        recommendation_reasons=["test"],
    )


def test_conclusion_mapping_defaults_fail_closed() -> None:
    assert recommendation_to_conclusion(Recommendation.ACCEPT) == "success"
    assert recommendation_to_conclusion(Recommendation.REJECT) == "failure"
    assert recommendation_to_conclusion(Recommendation.ESCALATE) == "failure"
    assert (
        recommendation_to_conclusion(Recommendation.ESCALATE, escalate_as="neutral")
        == "neutral"
    )
    assert (
        recommendation_to_conclusion(
            Recommendation.ESCALATE, escalate_as="action_required"
        )
        == "action_required"
    )


def test_render_uses_candidate_head_sha() -> None:
    sha = "abc123def4567890abc123def4567890abc123de"
    packet = _minimal_packet(recommendation=Recommendation.ESCALATE, head_commit=sha)
    check = packet_to_github_check(packet)
    payload = render_check_payload(check)
    assert payload["head_sha"] == sha
    assert payload["conclusion"] == "failure"
    assert payload["head_sha"] != "mock-sha"


def test_render_unavailable_sha_when_missing() -> None:
    packet = _minimal_packet(recommendation=Recommendation.ACCEPT, head_commit=None)
    check = packet_to_github_check(packet)
    payload = render_check_payload(check)
    assert payload["head_sha"] == "unavailable-sha"
    assert payload["conclusion"] == "success"


def test_escalate_as_neutral_configurable() -> None:
    packet = _minimal_packet(
        recommendation=Recommendation.ESCALATE,
        head_commit="b" * 40,
    )
    check = packet_to_github_check(packet, escalate_as="neutral")
    payload = render_check_payload(check)
    assert payload["conclusion"] == "neutral"


def test_github_check_adapter_from_compile(
    example_project: Path, example_candidate
) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    check = packet_to_github_check(packet)
    payload = render_check_payload(check)
    # Default fail-closed: ESCALATE → failure (AUDIT-018).
    assert payload["conclusion"] == "failure"
    assert payload["head_sha"] != "mock-sha"
    assert payload["output"]["title"]
    assert payload["output"]["annotations"]
