"""Phase 3 kernel-truth tests (AUDIT-011/012/020/003/010)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from lpe.evidence.compiler import _check_axioms, compile_evidence
from lpe.evidence.gates import decide
from lpe.contract.loader import load_contract
from lpe.lean.extractor import LeanExtractionResult, REGEX_STUB_EXTRACTOR, TOOLCHAIN_EXTRACTOR
from lpe.models import (
    CandidateDescriptor,
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    GeneratorProvenance,
    Provenance,
    Recommendation,
    RiskClass,
    Severity,
)
from lpe.providers.semantic import StatementDiffProvider


def _generator() -> GeneratorProvenance:
    return GeneratorProvenance(generator_type="test", name="test", version="0")


def _finding(
    check_id: str,
    status: FindingStatus,
    *,
    summary: str = "x",
) -> EvidenceFinding:
    now = datetime.now(timezone.utc)
    return EvidenceFinding(
        finding_id=f"f_{check_id}_{status.value}",
        check_id=check_id,
        check_version="0.1.0",
        dimension=EvidenceDimension.KERNEL,
        status=status,
        severity=Severity.L2,
        summary=summary,
        provenance=Provenance(
            tool="t",
            tool_version="0",
            input_hash="x",
            started_at=now,
            finished_at=now,
            elapsed_ms=0,
        ),
    )


def test_audit020_unknown_axiom_does_not_pass_hard_gate() -> None:
    findings = [
        _finding("contract.valid", FindingStatus.PASS),
        _finding("candidate.obligations", FindingStatus.PASS),
        _finding("lean.build", FindingStatus.PASS),
        _finding("lean.placeholders", FindingStatus.PASS),
        _finding(
            "lean.prohibited_axioms",
            FindingStatus.UNKNOWN,
            summary="Axiom closure incomplete",
        ),
        _finding("repository.changed_paths", FindingStatus.PASS),
    ]
    decision = decide(findings, RiskClass.R0, auto_accept_eligible=True)
    assert decision.hard_gate_passed is False
    assert decision.recommendation is Recommendation.ESCALATE
    assert "lean.prohibited_axioms" in decision.unresolved_hard_checks
    assert decision.hard_failures == []
    assert any("unresolved" in r.lower() for r in decision.reasons)


def test_audit020_hard_fail_still_rejects() -> None:
    findings = [
        _finding("lean.placeholders", FindingStatus.FAIL, summary="sorry found"),
    ]
    decision = decide(findings, RiskClass.R0, auto_accept_eligible=True)
    assert decision.hard_gate_passed is False
    assert decision.recommendation is Recommendation.REJECT
    assert "lean.placeholders" in decision.hard_failures


def test_compile_hard_gate_false_with_regex_stub_axioms(
    example_project: Path,
    example_candidate: CandidateDescriptor,
) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is FindingStatus.UNKNOWN
    assert packet.hard_gate_passed is False
    assert packet.recommendation is Recommendation.ESCALATE
    assert any("unresolved hard-relevant" in r for r in packet.recommendation_reasons)


def test_impact_cone_finding_unknown_under_regex_stub(
    example_project: Path,
    example_candidate: CandidateDescriptor,
) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    impact = next(f for f in packet.findings if f.check_id == "lean.impact_cone")
    assert impact.status is FindingStatus.UNKNOWN
    assert impact.details.get("extractor") == REGEX_STUB_EXTRACTOR


def test_axiom_fail_when_prohibited_even_on_regex(
    example_project: Path,
) -> None:
    contract = load_contract(example_project)
    extraction = LeanExtractionResult(
        axioms_used=["Definitely.Prohibited.Axiom"],
        extractor=REGEX_STUB_EXTRACTOR,
        complete=False,
    )
    finding = _check_axioms(contract, extraction, started=datetime.now(timezone.utc))
    assert finding.status is FindingStatus.FAIL


def test_axiom_pass_only_for_complete_toolchain(example_project: Path) -> None:
    contract = load_contract(example_project)
    extraction = LeanExtractionResult(
        axioms_used=[],
        extractor=TOOLCHAIN_EXTRACTOR,
        complete=True,
    )
    finding = _check_axioms(contract, extraction, started=datetime.now(timezone.utc))
    assert finding.status is FindingStatus.PASS


def test_statement_diff_provider_structural_pass(tmp_path: Path) -> None:
    lean = tmp_path / "Demo.lean"
    lean.write_text("def demoVal : Nat := 1\n", encoding="utf-8")
    (tmp_path / ".lean-project-contract").mkdir()
    candidate = CandidateDescriptor(
        candidate_id="cand-stmt",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+def demoVal : Nat := 1\n",
        claimed_intent="structural",
        changed_paths=["Demo.lean"],
        changed_declarations=[
            {
                "name": "Demo.demoVal",
                "kind": "definition",
                "path": "Demo.lean",
                "signature_changed": True,
                "public": True,
            }
        ],
        generator=_generator(),
    )
    from unittest.mock import MagicMock

    from lpe.execution.runner import SubprocessLeanExecutor
    from lpe.providers.base import CancellationToken, ProviderContext
    from lpe.workspace.artifacts import ContentAddressedArtifactStore
    from lpe.workspace.models import (
        EvaluationWorkspace,
        ExecutorDescriptor,
        WorkspaceCleanupToken,
    )

    store = ContentAddressedArtifactStore(tmp_path / "cas")
    desc = ExecutorDescriptor(backend="host", network_policy="allow")
    ws = EvaluationWorkspace(
        run_id="run_stmt",
        repository_origin=tmp_path,
        base_path=tmp_path,
        candidate_path=tmp_path,
        base_commit="b",
        head_commit="h",
        patch_sha256=None,
        base_tree_hash="t1",
        candidate_tree_hash="t2",
        contract_hash="ch",
        obligation_freeze_hash="oh",
        executor=SubprocessLeanExecutor(),
        executor_descriptor=desc,
        artifact_store=store,
        cleanup_token=WorkspaceCleanupToken(run_id="run_stmt"),
    )
    ctx = ProviderContext(
        workspace=ws,
        contract=MagicMock(),
        candidate=candidate,
        cancellation=CancellationToken(),
    )
    result = StatementDiffProvider().collect(ctx)
    assert len(result.findings) == 1
    assert result.findings[0].check_id == "semantic.statement_diff"
    # Without paired elaborations, structural compare may be UNKNOWN (fail-closed);
    # PASS only when structural evidence is complete.
    assert result.findings[0].status in {FindingStatus.PASS, FindingStatus.UNKNOWN}
    assert "intent fidelity not claimed" in result.findings[0].summary.lower() or (
        "elaborat" in result.findings[0].summary.lower()
        or "structural" in result.findings[0].summary.lower()
    )
