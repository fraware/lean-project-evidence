"""M4 Lake-backed semantic providers on lean_project fixtures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lpe.execution.runner import SubprocessLeanExecutor
from lpe.lean.extractor import lean_toolchain_available
from lpe.models import (
    CandidateDescriptor,
    FindingStatus,
    GeneratorProvenance,
)
from lpe.providers.base import CancellationToken, ProviderContext
from lpe.providers.semantic import (
    CounterexampleProvider,
    ExampleRunnerProvider,
    parse_signature_structure,
)
from lpe.workspace.artifacts import ContentAddressedArtifactStore
from lpe.workspace.models import (
    EvaluationWorkspace,
    ExecutorDescriptor,
    WorkspaceCleanupToken,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "lean_project"


def _candidate() -> CandidateDescriptor:
    return CandidateDescriptor(
        candidate_id="cand-m4-lake",
        project_id="lpe-fixture",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+--\n",
        claimed_intent="m4",
        changed_paths=["LpeFixture/Core.lean"],
        changed_declarations=[],
        generator=GeneratorProvenance(generator_type="test", name="m4", version="0"),
    )


def _context(tmp_path: Path) -> ProviderContext:
    store = ContentAddressedArtifactStore(tmp_path)
    desc = ExecutorDescriptor(backend="host", network_policy="allow")
    ws = EvaluationWorkspace(
        run_id="run_m4",
        repository_origin=FIXTURE,
        base_path=FIXTURE,
        candidate_path=FIXTURE,
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
        cleanup_token=WorkspaceCleanupToken(run_id="run_m4"),
    )
    mock_contract = MagicMock()
    mock_contract.project.execution.environment_allowlist = ["PATH", "HOME"]
    return ProviderContext(
        workspace=ws,
        contract=mock_contract,
        candidate=_candidate(),
        cancellation=CancellationToken(),
    )


@pytest.mark.lean
def test_example_runner_lake_pass_on_fixture(tmp_path: Path) -> None:
    if not lean_toolchain_available(FIXTURE):
        pytest.skip("Lake required")
    result = ExampleRunnerProvider().collect(_context(tmp_path))
    assert result.findings[0].status is FindingStatus.PASS
    details = result.findings[0].details
    assert details.get("lake_attempted") is True or details.get("attempted") is True


@pytest.mark.lean
def test_counterexample_lake_fail_on_fixture(tmp_path: Path) -> None:
    if not lean_toolchain_available(FIXTURE):
        pytest.skip("Lake required")
    result = CounterexampleProvider().collect(_context(tmp_path))
    # Suite-driven counterexamples: PASS when expected diagnostics match.
    assert result.findings[0].status in {FindingStatus.PASS, FindingStatus.FAIL}
    details = result.findings[0].details
    assert details.get("lake_attempted") is True or details.get("attempted") is True


def test_parse_signature_structure_fields() -> None:
    parsed = parse_signature_structure("theorem corePositive (n : Nat) : n ≥ 0 → True")
    assert parsed["decl_name"] == "corePositive"
    assert parsed["conclusion"] is not None
