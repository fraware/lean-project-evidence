"""AUDIT-004 / AUDIT-015 / AUDIT-016: candidate trust and placeholder honesty."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from lpe.contract.loader import load_contract
from lpe.evidence.compiler import compile_evidence
from lpe.git.candidate import enrich_candidate_from_git
from lpe.git.diff import GitError
from lpe.models import (
    ArtifactType,
    CandidateDescriptor,
    ChangedDeclaration,
    FindingStatus,
    GeneratorProvenance,
    Recommendation,
)


def _generator() -> GeneratorProvenance:
    return GeneratorProvenance(generator_type="test", name="test", version="0")


def _init_git(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.org"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _commit_all(repo: Path, message: str) -> str:
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_null_oid_head_commit_rejected(tmp_path: Path, example_project: Path) -> None:
    """Invariant: null/fake OIDs are refused during git enrichment."""
    _init_git(tmp_path)
    (tmp_path / "README").write_text("x\n", encoding="utf-8")
    _commit_all(tmp_path, "init")
    shutil.copytree(
        example_project / ".lean-project-contract",
        tmp_path / ".lean-project-contract",
    )
    contract = load_contract(tmp_path)
    candidate = CandidateDescriptor(
        candidate_id="cand-null-oid",
        project_id=contract.project.project_id,
        obligation_ids=["O-01"],
        base_commit="0" * 40,
        head_commit="1" * 40,
        claimed_intent="forge",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    with pytest.raises(GitError, match="null/fake"):
        enrich_candidate_from_git(tmp_path, candidate, contract)


def test_self_declared_risk_metadata_overridden_by_git(
    tmp_path: Path, example_project: Path
) -> None:
    """Invariant: self-declared low-risk metadata cannot override git classification."""
    _init_git(tmp_path)
    lean = tmp_path / "Internal.lean"
    lean.write_text("def foo : Nat := 1\n", encoding="utf-8")
    base = _commit_all(tmp_path, "base")
    lean.write_text("def foo : Int := 1\n", encoding="utf-8")
    head = _commit_all(tmp_path, "head")
    shutil.copytree(
        example_project / ".lean-project-contract",
        tmp_path / ".lean-project-contract",
    )
    contract = load_contract(tmp_path)

    forged = CandidateDescriptor(
        candidate_id="cand-forge-risk",
        project_id=contract.project.project_id,
        obligation_ids=["O-01"],
        base_commit=base,
        head_commit=head,
        claimed_intent="downgrade risk",
        changed_paths=["unrelated.md"],
        changed_declarations=[
            ChangedDeclaration(
                name="foo",
                kind=ArtifactType.THEOREM,
                path="Internal.lean",
                signature_changed=False,
                public=False,
                foundational=False,
            )
        ],
        generator=_generator(),
    )
    enriched = enrich_candidate_from_git(tmp_path, forged, contract)
    assert enriched.changed_paths == ["Internal.lean"]
    assert enriched.changed_declarations[0].signature_changed is True
    assert enriched.changed_declarations[0].kind is ArtifactType.DEFINITION


def test_placeholder_sorry_in_lean_file_with_empty_patch_text_rejects(
    example_project: Path,
) -> None:
    """Invariant: empty patch_text cannot hide sorry in a changed .lean file → REJECT."""
    lean_dir = example_project / "Example" / "Public"
    lean_dir.mkdir(parents=True, exist_ok=True)
    lean_file = lean_dir / "SecuritySorryProbe.lean"
    lean_file.write_text("theorem t : True := by sorry\n", encoding="utf-8")
    try:
        candidate = CandidateDescriptor(
            candidate_id="cand-sorry-sec",
            project_id="example-category-project",
            obligation_ids=["O-01"],
            base_commit="deadbeef",
            patch_text="",
            claimed_intent="empty patch hides sorry",
            changed_paths=["Example/Public/SecuritySorryProbe.lean"],
            changed_declarations=[],
            generator=_generator(),
        )
        packet = compile_evidence(example_project, candidate, skip_build=True)
        placeholders = next(f for f in packet.findings if f.check_id == "lean.placeholders")
        assert placeholders.status is FindingStatus.FAIL
        assert "sorry" in placeholders.details["tokens"]
        assert packet.recommendation is Recommendation.REJECT
    finally:
        lean_file.unlink(missing_ok=True)
