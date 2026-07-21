"""Week 2: real git-repo candidate enrich / build / invalid-rev failures."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.contract.loader import load_contract
from lpe.evidence.compiler import compile_evidence
from lpe.git.candidate import build_candidate_from_commits, enrich_candidate_from_git
from lpe.git.diff import GitError
from lpe.models import ArtifactType, CandidateDescriptor, FindingStatus, GeneratorProvenance

runner = CliRunner()


def _generator() -> dict:
    return {
        "generator_type": "test",
        "name": "week2-git",
        "version": "0",
    }


def _rev(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return _rev(repo)


def test_build_candidate_from_real_commits(
    git_seeded_project: Path,
) -> None:
    """Candidate built from actual commit range matches git-classified metadata."""
    repo = git_seeded_project
    # Replace seed-only tree with Lean commits.
    lean_dir = repo / "Example" / "Public"
    lean_dir.mkdir(parents=True)
    (lean_dir / "Comparison.lean").write_text(
        "def comparisonFunctor : Nat := 0\n", encoding="utf-8"
    )
    base = _commit(repo, "lean base")
    (lean_dir / "Comparison.lean").write_text(
        "def comparisonFunctor : Nat := 1\n", encoding="utf-8"
    )
    head = _commit(repo, "lean head")
    contract = load_contract(repo)

    candidate = build_candidate_from_commits(
        repo,
        contract,
        candidate_id="cand-week2-git",
        project_id=contract.project.project_id,
        obligation_ids=["O-01"],
        base_commit=base,
        head_commit=head,
        claimed_intent="Week 2 real-git candidate",
        generator=_generator(),
    )

    assert candidate.base_commit == base
    assert candidate.head_commit == head
    assert len(candidate.base_commit) == 40
    assert "Example/Public/Comparison.lean" in candidate.changed_paths
    assert any(d.name == "comparisonFunctor" for d in candidate.changed_declarations)
    decl = next(d for d in candidate.changed_declarations if d.name == "comparisonFunctor")
    assert decl.signature_changed is True
    assert decl.kind is ArtifactType.DEFINITION
    assert decl.public is True


def test_enrich_overrides_self_declared_on_real_repo(
    git_seeded_project: Path,
) -> None:
    repo = git_seeded_project
    lean_dir = repo / "Example" / "Public"
    lean_dir.mkdir(parents=True)
    (lean_dir / "Comparison.lean").write_text(
        "def comparisonFunctor : Nat := 0\n", encoding="utf-8"
    )
    base = _commit(repo, "lean base")
    (lean_dir / "Comparison.lean").write_text(
        "def comparisonFunctor : Nat := 1\n", encoding="utf-8"
    )
    head = _commit(repo, "lean head")
    contract = load_contract(repo)

    forged = CandidateDescriptor(
        candidate_id="cand-forged",
        project_id=contract.project.project_id,
        obligation_ids=["O-01"],
        base_commit=base,
        head_commit=head,
        claimed_intent="forged R0",
        changed_paths=["unrelated.md"],
        changed_declarations=[],
        generator=GeneratorProvenance.model_validate(_generator()),
    )
    enriched = enrich_candidate_from_git(repo, forged, contract)
    assert "Example/Public/Comparison.lean" in enriched.changed_paths
    assert "unrelated.md" not in enriched.changed_paths
    assert enriched.changed_declarations
    assert enriched.changed_declarations[0].signature_changed is True


def test_invalid_revision_fails_actionably(git_seeded_project: Path) -> None:
    contract = load_contract(git_seeded_project)
    head = _rev(git_seeded_project)
    candidate = CandidateDescriptor(
        candidate_id="cand-bad-rev",
        project_id=contract.project.project_id,
        obligation_ids=["O-01"],
        base_commit="not-a-real-revision-zzzz",
        head_commit=head,
        claimed_intent="bad base",
        changed_paths=[],
        changed_declarations=[],
        generator=GeneratorProvenance.model_validate(_generator()),
    )
    with pytest.raises(GitError, match="cannot resolve revision"):
        enrich_candidate_from_git(git_seeded_project, candidate, contract)


def test_null_oid_and_missing_head_fail_actionably(git_seeded_project: Path) -> None:
    contract = load_contract(git_seeded_project)
    head = _rev(git_seeded_project)
    with pytest.raises(GitError, match="null/fake"):
        build_candidate_from_commits(
            git_seeded_project,
            contract,
            candidate_id="cand-null",
            project_id=contract.project.project_id,
            obligation_ids=["O-01"],
            base_commit="0" * 40,
            head_commit=head,
            claimed_intent="null",
            generator=_generator(),
        )


def test_compile_rejects_invalid_rev_on_git_project(
    git_seeded_project: Path,
) -> None:
    contract = load_contract(git_seeded_project)
    head = _rev(git_seeded_project)
    candidate = CandidateDescriptor(
        candidate_id="cand-compile-bad",
        project_id=contract.project.project_id,
        obligation_ids=["O-01"],
        base_commit="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        head_commit=head,
        claimed_intent="compile path",
        changed_paths=["README.md"],
        changed_declarations=[],
        generator=GeneratorProvenance.model_validate(_generator()),
    )
    with pytest.raises(GitError, match="cannot resolve revision"):
        compile_evidence(git_seeded_project, candidate, skip_build=True)


def test_evidence_cli_rejects_invalid_rev(git_seeded_project: Path, tmp_path: Path) -> None:
    head = _rev(git_seeded_project)
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "candidate_id": "cand-cli-bad",
                "project_id": "example-category-project",
                "obligation_ids": ["O-01"],
                "base_commit": "not-a-revision",
                "head_commit": head,
                "claimed_intent": "cli invalid rev",
                "changed_paths": ["README.md"],
                "changed_declarations": [],
                "generator": _generator(),
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "packet.json"
    result = runner.invoke(
        app,
        [
            "evidence",
            "compile",
            "--project",
            str(git_seeded_project),
            "--candidate",
            str(candidate_path),
            "--output",
            str(output),
            "--skip-build",
        ],
    )
    assert result.exit_code == 1, result.stdout + (result.stderr or "")
    combined = (result.stdout or "") + (result.stderr or "")
    assert "cannot resolve revision" in combined or "revision" in combined.lower()


def test_compile_enriched_candidate_skip_build(
    git_seeded_project: Path,
) -> None:
    """Happy path: real commits → enrich → skip-build compile stays honest."""
    repo = git_seeded_project
    lean_dir = repo / "Example" / "Public"
    lean_dir.mkdir(parents=True)
    (lean_dir / "Comparison.lean").write_text(
        "def comparisonFunctor : Nat := 0\n", encoding="utf-8"
    )
    base = _commit(repo, "lean base")
    (lean_dir / "Comparison.lean").write_text(
        "def comparisonFunctor : Nat := 1\n", encoding="utf-8"
    )
    head = _commit(repo, "lean head")
    contract = load_contract(repo)
    candidate = build_candidate_from_commits(
        repo,
        contract,
        candidate_id="cand-week2-compile",
        project_id=contract.project.project_id,
        obligation_ids=["O-01"],
        base_commit=base,
        head_commit=head,
        claimed_intent="compile after enrich",
        generator=_generator(),
    )
    packet = compile_evidence(repo, candidate, skip_build=True)
    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    assert isolation.status is FindingStatus.NOT_APPLICABLE
    assert isolation.status is not FindingStatus.PASS
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is not FindingStatus.PASS
