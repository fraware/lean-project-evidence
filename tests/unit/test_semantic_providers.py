from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from lpe.evidence.compiler import compile_evidence
from lpe.models import (
    CandidateDescriptor,
    ChangedDeclaration,
    FindingStatus,
    GeneratorProvenance,
)
from lpe.providers.semantic import (
    CounterexampleProvider,
    DownstreamReplacementProvider,
    DuplicateRetrievalProvider,
    ExampleRunnerProvider,
)


def _generator() -> GeneratorProvenance:
    return GeneratorProvenance(generator_type="test", name="test", version="0")


def test_semantic_providers_emit_unknown_not_silent_pass_without_fixtures(
    tmp_path: Path,
) -> None:
    """AUDIT-010: missing structured fixtures must not PASS."""
    project = tmp_path / "proj"
    (project / ".lean-project-contract" / "tests" / "examples").mkdir(parents=True)
    (project / ".lean-project-contract" / "tests" / "counterexamples").mkdir(parents=True)
    (
        project / ".lean-project-contract" / "tests" / "examples" / "README.md"
    ).write_text("# x\n", encoding="utf-8")

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
    mock_contract = MagicMock()
    examples = ExampleRunnerProvider().collect(project, mock_contract, candidate)
    counters = CounterexampleProvider().collect(project, mock_contract, candidate)
    assert examples[0].status is FindingStatus.UNKNOWN
    assert counters[0].status is FindingStatus.UNKNOWN
    assert examples[0].details.get("attempted") is True
    assert counters[0].details.get("attempted") is True


def test_semantic_providers_on_example_project(
    example_project: Path,
    example_candidate,
) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    semantic = [f for f in packet.findings if f.dimension.value == "semantic"]
    assert semantic
    by_id = {f.check_id: f for f in semantic}
    # Structured fixtures exist → heuristic PASS (not Lean execution).
    assert by_id["semantic.project_examples"].status is FindingStatus.PASS
    assert by_id["semantic.counterexamples"].status is FindingStatus.PASS
    assert by_id["semantic.project_examples"].details["protocol"]["toolchain_backed"] is False
    # Empty corpus for this example → UNKNOWN, never silent PASS.
    assert by_id["semantic.duplicate_retrieval"].status is FindingStatus.UNKNOWN
    statement = by_id["semantic.statement_diff"]
    assert statement.status in {
        FindingStatus.UNKNOWN,
        FindingStatus.NOT_APPLICABLE,
        FindingStatus.FAIL,
    }


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
    findings = DuplicateRetrievalProvider().collect(tmp_path, MagicMock(), candidate)
    assert findings[0].status in {FindingStatus.PASS, FindingStatus.WARN}
    assert findings[0].details["corpus_size"] >= 1
    assert findings[0].details["closest"]


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
    findings = DownstreamReplacementProvider().collect(tmp_path, MagicMock(), candidate)
    assert findings[0].status in {
        FindingStatus.WARN,
        FindingStatus.PASS,
        FindingStatus.UNKNOWN,
    }
    if findings[0].status is not FindingStatus.UNKNOWN:
        assert findings[0].details["successor_count"] >= 1
        cone = findings[0].details["impact_cone"]
        assert any(name == "userFn" or name.endswith(".userFn") for name in cone)

def test_example_runner_pass_on_structured_fixture(tmp_path: Path) -> None:
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
    findings = ExampleRunnerProvider().collect(tmp_path, MagicMock(), candidate)
    assert findings[0].status is FindingStatus.PASS
    assert findings[0].details["fixture_count"] == 1
