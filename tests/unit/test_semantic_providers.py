from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from lpe.evidence.compiler import compile_evidence
from lpe.execution.runner import SubprocessLeanExecutor
from lpe.models import (
    CandidateDescriptor,
    ChangedDeclaration,
    FindingStatus,
    GeneratorProvenance,
)
from lpe.providers.base import CancellationToken, ProviderContext
from lpe.providers.semantic import (
    CounterexampleProvider,
    DownstreamReplacementProvider,
    DuplicateRetrievalProvider,
    ExampleRunnerProvider,
)
from lpe.workspace.artifacts import ContentAddressedArtifactStore
from lpe.workspace.models import (
    EvaluationWorkspace,
    ExecutorDescriptor,
    WorkspaceCleanupToken,
)


def _generator() -> GeneratorProvenance:
    return GeneratorProvenance(generator_type="test", name="test", version="0")


def _ctx(project_path: Path, candidate: CandidateDescriptor) -> ProviderContext:
    store = ContentAddressedArtifactStore(project_path)
    desc = ExecutorDescriptor(
        backend="host",
        network_policy="allow",
        readonly_root=False,
        source_mount_readonly=False,
    )
    ws = EvaluationWorkspace(
        run_id="run_test",
        repository_origin=project_path,
        base_path=project_path,
        candidate_path=project_path,
        base_commit=candidate.base_commit,
        head_commit=candidate.head_commit,
        patch_sha256=None,
        base_tree_hash="t1",
        candidate_tree_hash="t2",
        contract_hash="ch",
        obligation_freeze_hash="oh",
        executor=SubprocessLeanExecutor(),
        executor_descriptor=desc,
        artifact_store=store,
        cleanup_token=WorkspaceCleanupToken(run_id="run_test"),
    )
    mock_contract = MagicMock()
    mock_contract.project.execution.environment_allowlist = ["PATH", "HOME", "USER", "TMPDIR"]
    return ProviderContext(
        workspace=ws,
        contract=mock_contract,
        candidate=candidate,
        cancellation=CancellationToken(),
    )


def test_semantic_providers_emit_unknown_not_silent_pass_without_fixtures(
    tmp_path: Path,
) -> None:
    """AUDIT-010: missing structured fixtures must not PASS."""
    project = tmp_path / "proj"
    (project / ".lean-project-contract" / "tests" / "examples").mkdir(parents=True)
    (project / ".lean-project-contract" / "tests" / "counterexamples").mkdir(parents=True)
    (project / ".lean-project-contract" / "tests" / "examples" / "README.md").write_text(
        "# x\n", encoding="utf-8"
    )

    candidate = CandidateDescriptor(
        candidate_id="cand-miss",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+-- none\n",
        claimed_intent="x",
        changed_paths=["docs/x.md"],
        changed_declarations=[],
        generator=_generator(),
    )
    ctx = _ctx(project, candidate)
    examples = ExampleRunnerProvider().collect(ctx)
    counters = CounterexampleProvider().collect(ctx)
    assert examples.findings[0].status is FindingStatus.UNKNOWN
    assert counters.findings[0].status is FindingStatus.UNKNOWN
    assert examples.findings[0].details.get("attempted") is True
    assert counters.findings[0].details.get("attempted") is True


def test_semantic_providers_on_example_project(
    example_project: Path,
    example_candidate,
) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    semantic = [f for f in packet.findings if f.dimension.value == "semantic"]
    assert semantic
    by_id = {f.check_id: f for f in semantic}
    # CLOSURE-013: JSON/README without suite manifest cannot PASS.
    assert by_id["semantic.project_examples"].status is FindingStatus.UNKNOWN
    assert by_id["semantic.counterexamples"].status is FindingStatus.UNKNOWN
    assert by_id["semantic.project_examples"].details.get("attempted") is True
    # Empty corpus for this example → UNKNOWN, never silent PASS.
    assert by_id["semantic.duplicate_retrieval"].status is FindingStatus.UNKNOWN
    statement = by_id["semantic.statement_diff"]
    assert statement.status in {
        FindingStatus.UNKNOWN,
        FindingStatus.NOT_APPLICABLE,
        FindingStatus.FAIL,
        FindingStatus.PASS,
    }
    # CLOSURE-015 intent bundle always synthesized.
    assert "semantic.intent_support" in by_id
    assert packet.recommendation_policy_id is not None


def test_downstream_replacement_provider_present(
    example_project: Path,
    example_candidate,
) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    finding = next(f for f in packet.findings if f.check_id == "downstream.replacement_tests")
    assert finding.status is FindingStatus.UNKNOWN
    assert finding.details.get("attempted") is True


def test_duplicate_retrieval_reports_closest(tmp_path: Path) -> None:
    (tmp_path / "Core.lean").write_text(
        "def demoVal : Nat := 1\ndef demoValAlt : Nat := 2\n",
        encoding="utf-8",
    )
    candidate = CandidateDescriptor(
        candidate_id="cand-dup",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+def demoVal : Nat := 1\n",
        claimed_intent="dup",
        changed_paths=["Core.lean"],
        changed_declarations=[
            ChangedDeclaration(
                name="demoVal",
                kind="definition",
                path="Core.lean",
                signature_changed=True,
                public=False,
                foundational=False,
            )
        ],
        generator=_generator(),
    )
    result = DuplicateRetrievalProvider().collect(_ctx(tmp_path, candidate))
    assert result.findings[0].status in {FindingStatus.PASS, FindingStatus.WARN}
    assert result.findings[0].details["corpus_size"] >= 1
    assert result.findings[0].details["closest"]


def test_downstream_replacement_with_cone(tmp_path: Path) -> None:
    (tmp_path / "Lib.lean").write_text(
        "def seedFn : Nat := 1\ndef userFn : Nat := seedFn\n",
        encoding="utf-8",
    )
    candidate = CandidateDescriptor(
        candidate_id="cand-down",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+def seedFn : Nat := 1\n",
        claimed_intent="downstream",
        changed_paths=["Lib.lean"],
        changed_declarations=[
            ChangedDeclaration(
                name="seedFn",
                kind="definition",
                path="Lib.lean",
                signature_changed=False,
                public=False,
                foundational=False,
            )
        ],
        generator=_generator(),
    )
    result = DownstreamReplacementProvider().collect(_ctx(tmp_path, candidate))
    finding = result.findings[0]
    assert finding.status in {
        FindingStatus.WARN,
        FindingStatus.PASS,
        FindingStatus.UNKNOWN,
    }
    if finding.status is not FindingStatus.UNKNOWN:
        assert finding.details["successor_count"] >= 1
        cone = finding.details["impact_cone"]
        assert any(name == "userFn" or name.endswith(".userFn") for name in cone)


def test_example_runner_requires_suite_manifest(tmp_path: Path) -> None:
    """CLOSURE-013: JSON alone cannot PASS; suite manifest is required."""
    examples = tmp_path / ".lean-project-contract" / "tests" / "examples"
    examples.mkdir(parents=True)
    (examples / "ok.json").write_text(
        json.dumps(
            {
                "name": "ok",
                "obligation_id": "O-01",
                "distinguishes": "x",
                "expected": "y",
            }
        ),
        encoding="utf-8",
    )
    candidate = CandidateDescriptor(
        candidate_id="cand-ex",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+--\n",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    result = ExampleRunnerProvider().collect(_ctx(tmp_path, candidate))
    assert result.findings[0].status is FindingStatus.UNKNOWN
    assert result.findings[0].details.get("attempted") is True
    assert "manifest" in str(result.findings[0].details.get("load_report", {})).lower() or (
        result.findings[0].details.get("load_report", {}).get("error") == "manifest_missing"
    )
