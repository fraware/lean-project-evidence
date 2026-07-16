"""Week 2: worktree create/cleanup and dirty-tree safety under compile."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from lpe.evidence.compiler import compile_evidence
from lpe.execution.protocol import ExecutionResult
from lpe.execution.sandbox import DockerSandboxExecutor
from lpe.execution.worktree import WorktreeError, create_isolated_worktree
from lpe.models import CandidateDescriptor, FindingStatus, GeneratorProvenance


def _generator() -> GeneratorProvenance:
    return GeneratorProvenance(generator_type="test", name="week2-worktree", version="0")


def _init_git(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "week2@example.org"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Week2"],
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


def test_worktree_excludes_uncommitted_dirty_main_tree(tmp_path: Path) -> None:
    """Detached worktree must not include uncommitted dirt from the main checkout."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo)
    (repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
    head = _commit_all(repo, "clean")

    (repo / "dirty-uncommitted.txt").write_text("SHOULD NOT LEAK\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("dirty overwrite\n", encoding="utf-8")

    session = create_isolated_worktree(repo, head_commit=head, base_dir=tmp_path / "wt")
    try:
        assert (session.worktree_path / "tracked.txt").read_text(encoding="utf-8") == "clean\n"
        assert not (session.worktree_path / "dirty-uncommitted.txt").exists()
        # Main tree remains dirty.
        assert (repo / "dirty-uncommitted.txt").is_file()
        assert (repo / "tracked.txt").read_text(encoding="utf-8") == "dirty overwrite\n"
    finally:
        session.cleanup()
    assert not session.worktree_path.exists() or not any(session.worktree_path.iterdir())


def test_worktree_rejects_unknown_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo)
    (repo / "README").write_text("x\n", encoding="utf-8")
    _commit_all(repo, "init")
    with pytest.raises(WorktreeError):
        create_isolated_worktree(repo, head_commit="0" * 40)


def test_compile_cleans_worktree_even_when_build_raises(
    example_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUDIT-014: worktree must be removed if verify_build raises mid-compile."""
    project = tmp_path / "proj"
    shutil.copytree(example_project, project)
    _init_git(project)
    (project / "README.md").write_text("seed\n", encoding="utf-8")
    head = _commit_all(project, "seed")

    path = project / ".lean-project-contract" / "project.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["execution"]["network_policy"] = "allow"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    created: list[Path] = []
    real_create = create_isolated_worktree

    def tracking_create(*args, **kwargs):  # type: ignore[no-untyped-def]
        session = real_create(*args, **kwargs)
        created.append(session.worktree_path)
        return session

    monkeypatch.setattr("lpe.evidence.compiler.create_isolated_worktree", tracking_create)
    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))

    class ExplodingExecutor:
        def verify_build(self, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("simulated build failure")

    monkeypatch.setattr("lpe.evidence.compiler.SubprocessLeanExecutor", ExplodingExecutor)

    candidate = CandidateDescriptor(
        candidate_id="cand-wt-cleanup",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit=head,
        head_commit=head,
        claimed_intent="worktree cleanup",
        changed_paths=["README.md"],
        changed_declarations=[],
        generator=_generator(),
    )
    with pytest.raises(RuntimeError, match="simulated build failure"):
        compile_evidence(
            project,
            candidate,
            skip_build=False,
            insecure_host_exec=True,
            use_worktree=True,
        )
    assert created, "worktree should have been created"
    for path in created:
        assert not path.exists() or not any(path.iterdir())


def test_compile_uses_worktree_path_for_build(
    example_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "proj"
    shutil.copytree(example_project, project)
    _init_git(project)
    (project / "README.md").write_text("seed\n", encoding="utf-8")
    head = _commit_all(project, "seed")
    (project / "dirty.txt").write_text("dirt\n", encoding="utf-8")

    path = project / ".lean-project-contract" / "project.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["execution"]["network_policy"] = "allow"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    seen_repos: list[Path] = []

    class CapturingExecutor:
        def verify_build(self, **kwargs):  # type: ignore[no-untyped-def]
            seen_repos.append(Path(kwargs["repository"]))
            assert not (Path(kwargs["repository"]) / "dirty.txt").exists()
            return ExecutionResult(
                command=("lake", "build"),
                cwd=kwargs["repository"],
                exit_code=0,
                stdout="ok",
                stderr="",
                elapsed_ms=1,
                timed_out=False,
            )

    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))
    monkeypatch.setattr("lpe.evidence.compiler.SubprocessLeanExecutor", CapturingExecutor)

    candidate = CandidateDescriptor(
        candidate_id="cand-wt-path",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit=head,
        head_commit=head,
        claimed_intent="worktree path",
        changed_paths=["README.md"],
        changed_declarations=[],
        generator=_generator(),
    )
    packet = compile_evidence(
        project,
        candidate,
        skip_build=False,
        insecure_host_exec=True,
        use_worktree=True,
    )
    assert seen_repos
    assert seen_repos[0].resolve() != project.resolve()
    build = next(f for f in packet.findings if f.check_id == "lean.build")
    assert build.status is FindingStatus.PASS
    assert build.details.get("worktree")
    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    assert isolation.status is FindingStatus.UNKNOWN  # host subprocess
