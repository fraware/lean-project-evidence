"""Providers emit typed FindingPayload variants (not bare details dicts)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from lpe.evidence.payloads import (
    ExecutedCheckFindingPayload,
    OpaqueFindingPayload,
    StructuralDiffFindingPayload,
)
from lpe.execution.runner import SubprocessLeanExecutor
from lpe.models import (
    CandidateDescriptor,
    ChangedDeclaration,
    FindingStatus,
    GeneratorProvenance,
)
from lpe.providers.base import CancellationToken, ProviderContext
from lpe.providers.downstream import DownstreamSuccessorProvider
from lpe.providers.fixture_runners import ExampleRunnerProvider
from lpe.providers.semantic import (
    DownstreamReplacementProvider,
    DuplicateRetrievalProvider,
    StatementDiffProvider,
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
        run_id="run_typed_payload",
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
        cleanup_token=WorkspaceCleanupToken(run_id="run_typed_payload"),
    )
    mock_contract = MagicMock()
    mock_contract.project.execution.environment_allowlist = [
        "PATH",
        "HOME",
        "USER",
        "TMPDIR",
    ]
    return ProviderContext(
        workspace=ws,
        contract=mock_contract,
        candidate=candidate,
        cancellation=CancellationToken(),
    )


def test_statement_diff_emits_structural_payload(tmp_path: Path) -> None:
    candidate = CandidateDescriptor(
        candidate_id="cand-sd",
        project_id="p",
        obligation_ids=["O-01"],
        base_commit="a" * 40,
        patch_text="",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    finding = StatementDiffProvider().collect(_ctx(tmp_path, candidate)).findings[0]
    assert finding.status is FindingStatus.NOT_APPLICABLE
    assert isinstance(finding.payload, StructuralDiffFindingPayload)
    assert finding.payload.payload_type == "StructuralDiffFindingPayload"


def test_duplicate_retrieval_emits_opaque_payload(tmp_path: Path) -> None:
    candidate = CandidateDescriptor(
        candidate_id="cand-dup",
        project_id="p",
        obligation_ids=["O-01"],
        base_commit="a" * 40,
        patch_text="",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    finding = DuplicateRetrievalProvider().collect(_ctx(tmp_path, candidate)).findings[0]
    assert isinstance(finding.payload, OpaqueFindingPayload)
    assert finding.payload.data.get("attempted") is True


def test_downstream_replacement_typed_payload(tmp_path: Path) -> None:
    candidate = CandidateDescriptor(
        candidate_id="cand-dr",
        project_id="p",
        obligation_ids=["O-01"],
        base_commit="a" * 40,
        patch_text="",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    finding = DownstreamReplacementProvider().collect(_ctx(tmp_path, candidate)).findings[0]
    assert finding.payload is not None
    assert not isinstance(finding.payload, dict)
    assert hasattr(finding.payload, "payload_type")


def test_downstream_successor_emits_executed_payload(tmp_path: Path) -> None:
    candidate = CandidateDescriptor(
        candidate_id="cand-ds",
        project_id="p",
        obligation_ids=["O-01"],
        base_commit="a" * 40,
        patch_text="",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    finding = DownstreamSuccessorProvider().collect(_ctx(tmp_path, candidate)).findings[0]
    assert isinstance(finding.payload, ExecutedCheckFindingPayload)
    assert finding.payload.check_id == "downstream.successor_suite"


def test_example_runner_emits_executed_payload(tmp_path: Path) -> None:
    examples = tmp_path / ".lean-project-contract" / "tests" / "examples"
    examples.mkdir(parents=True)
    candidate = CandidateDescriptor(
        candidate_id="cand-ex",
        project_id="p",
        obligation_ids=["O-01"],
        base_commit="a" * 40,
        patch_text="",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[
            ChangedDeclaration(
                name="Foo.bar",
                kind="theorem",
                path="Foo.lean",
                signature_changed=True,
                public=False,
                foundational=False,
            )
        ],
        generator=_generator(),
    )
    finding = ExampleRunnerProvider().collect(_ctx(tmp_path, candidate)).findings[0]
    assert isinstance(finding.payload, ExecutedCheckFindingPayload)
    assert finding.payload.check_id.startswith("semantic.")
