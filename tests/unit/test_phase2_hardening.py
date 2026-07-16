"""Phase 2 hardening tests (AUDIT-005/006/007/008/014/019/027)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from lpe.evidence.compiler import (
    NetworkPolicyError,
    compile_evidence,
)
from lpe.execution.allowlist import CommandAllowlistError, validate_build_command
from lpe.execution.env import is_denied_env_key, scrub_environment
from lpe.execution.redact import REDACTION_MARKER, redact_secrets
from lpe.execution.runner import SubprocessLeanExecutor, _truncate
from lpe.execution.sandbox import DockerSandboxExecutor, isolation_status_for_executor
from lpe.execution.worktree import WorktreeError, create_isolated_worktree
from lpe.models import (
    CandidateDescriptor,
    FindingStatus,
    GeneratorProvenance,
)


def _generator() -> GeneratorProvenance:
    return GeneratorProvenance(generator_type="test", name="test", version="0")


def _candidate() -> CandidateDescriptor:
    return CandidateDescriptor(
        candidate_id="cand-phase2",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="# comment\n",
        claimed_intent="phase2",
        changed_paths=["README.md"],
        changed_declarations=[],
        generator=_generator(),
    )


def _set_network_policy(project: Path, policy: str) -> None:
    path = project / ".lean-project-contract" / "project.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["execution"]["network_policy"] = policy
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


# --- AUDIT-005 ---


def test_allowlist_accepts_lake() -> None:
    assert validate_build_command(["lake", "build"]) == ["lake", "build"]


def test_allowlist_rejects_arbitrary_command() -> None:
    with pytest.raises(CommandAllowlistError, match="allowlist"):
        validate_build_command(["curl", "https://evil.example"])


def test_allowlist_rejects_shell_wrapper() -> None:
    with pytest.raises(CommandAllowlistError, match="shell/interpreter"):
        validate_build_command(["bash", "-c", "lake build"])


def test_compile_rejects_disallowed_build_command(
    example_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    project = tmp_path / "proj"
    shutil.copytree(example_project, project)
    _set_network_policy(project, "allow")
    path = project / ".lean-project-contract" / "project.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["execution"]["build_command"] = ["rm", "-rf", "/"]
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))
    with pytest.raises(CommandAllowlistError, match="allowlist"):
        compile_evidence(
            project,
            _candidate(),
            skip_build=False,
            insecure_host_exec=True,
        )


# --- AUDIT-006 ---


def test_isolation_not_applicable_when_skip_build() -> None:
    status, name = isolation_status_for_executor(
        DockerSandboxExecutor(),
        build_ran=False,
        skip_build=True,
        network_isolated=True,
    )
    assert status == "NOT_APPLICABLE"
    assert name == "docker-sandbox"


def test_isolation_pass_only_when_sandboxed_build_ran() -> None:
    status, _ = isolation_status_for_executor(
        DockerSandboxExecutor(),
        build_ran=True,
        skip_build=False,
        network_isolated=True,
    )
    assert status == "PASS"


def test_isolation_unknown_for_subprocess_even_if_build_ran() -> None:
    status, name = isolation_status_for_executor(
        SubprocessLeanExecutor(),
        build_ran=True,
        skip_build=False,
        network_isolated=False,
    )
    assert status == "UNKNOWN"
    assert name == "SubprocessLeanExecutor"


def test_skip_build_isolation_is_not_pass(
    example_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: True))
    packet = compile_evidence(
        example_project, _candidate(), skip_build=True, use_sandbox=True
    )
    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    assert isolation.status is FindingStatus.NOT_APPLICABLE
    assert isolation.status is not FindingStatus.PASS


def test_docker_image_defaults_and_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LPE_DOCKER_IMAGE", raising=False)
    assert DockerSandboxExecutor().image == "ubuntu:22.04"
    monkeypatch.setenv("LPE_DOCKER_IMAGE", "leanprover/lean4:latest")
    assert DockerSandboxExecutor().image == "leanprover/lean4:latest"


# --- AUDIT-007 ---


def test_redact_github_pat() -> None:
    log = "auth failed token=ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    out = redact_secrets(log)
    assert "ghp_" not in out
    assert REDACTION_MARKER in out


def test_redact_aws_key_and_bearer() -> None:
    log = "AKIAIOSFODNN7EXAMPLE Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature"
    # Bearer pattern redacts token; JWT pattern also catches eyJ...
    out = redact_secrets(log)
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert "Bearer" in out
    assert REDACTION_MARKER in out


def test_redact_env_assignment_shape() -> None:
    log = "export API_KEY=supersecretvalue123\npassword=hunter2hunter2"
    out = redact_secrets(log)
    assert "supersecretvalue123" not in out
    assert "hunter2hunter2" not in out


# --- AUDIT-008 ---


def test_env_denylist_blocks_secret_names() -> None:
    assert is_denied_env_key("MY_API_TOKEN")
    assert is_denied_env_key("DB_SECRET")
    assert is_denied_env_key("LOGIN_PASSWORD")
    assert is_denied_env_key("GITHUB_TOKEN")
    assert is_denied_env_key("AWS_ACCESS_KEY_ID")
    assert is_denied_env_key("CI")
    assert not is_denied_env_key("PATH")
    assert not is_denied_env_key("HOME")


def test_scrub_environment_drops_denied_even_if_allowlisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_should_not_leak")
    monkeypatch.setenv("MY_TOKEN", "secret")
    env = scrub_environment(["PATH", "CI", "GITHUB_TOKEN", "MY_TOKEN"])
    assert env == {"PATH": "/usr/bin"}


def test_default_allowlist_excludes_ci() -> None:
    from lpe.models import ExecutionPolicy

    assert "CI" not in ExecutionPolicy().environment_allowlist


# --- AUDIT-014 ---


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


def test_worktree_create_and_cleanup(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo)
    (repo / "README").write_text("x\n", encoding="utf-8")
    head = _commit_all(repo, "init")

    session = create_isolated_worktree(repo, head_commit=head, base_dir=tmp_path / "wt")
    assert session.worktree_path.is_dir()
    assert (session.worktree_path / "README").is_file()
    assert session.log_dir.is_dir()
    session.cleanup()
    # After cleanup the worktree path should be gone (or removed by git).
    assert not session.worktree_path.exists() or not any(session.worktree_path.iterdir())


def test_worktree_rejects_unknown_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git(repo)
    (repo / "README").write_text("x\n", encoding="utf-8")
    _commit_all(repo, "init")
    with pytest.raises(WorktreeError):
        create_isolated_worktree(repo, head_commit="0" * 40)


# --- AUDIT-019 ---


def test_network_deny_refuses_host_exec(
    example_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))
    with pytest.raises(NetworkPolicyError, match="network_policy"):
        compile_evidence(
            example_project,
            _candidate(),
            skip_build=False,
            insecure_host_exec=True,
        )


def test_network_allow_permits_insecure_host_exec(
    example_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    project = tmp_path / "proj"
    shutil.copytree(example_project, project)
    _set_network_policy(project, "allow")
    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))

    class FakeExecutor:
        def verify_build(self, **kwargs):  # type: ignore[no-untyped-def]
            from lpe.execution.protocol import ExecutionResult

            return ExecutionResult(
                command=("lake", "build"),
                cwd=kwargs["repository"],
                exit_code=0,
                stdout="ok",
                stderr="",
                elapsed_ms=1,
                timed_out=False,
            )

    monkeypatch.setattr("lpe.evidence.compiler.SubprocessLeanExecutor", FakeExecutor)
    packet = compile_evidence(
        project,
        _candidate(),
        skip_build=False,
        insecure_host_exec=True,
    )
    build = next(f for f in packet.findings if f.check_id == "lean.build")
    assert build.status is FindingStatus.PASS
    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    assert isolation.status is FindingStatus.UNKNOWN


# --- AUDIT-027 ---


def test_output_truncation() -> None:
    big = "x" * 5000
    out = _truncate(big, max_bytes=100)
    assert len(out.encode("utf-8")) <= 100
    assert "truncated by lpe" in out


def test_subprocess_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    # Use a cross-platform sleep via python if available.
    import sys

    cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    # Bypass allowlist for this unit test of the executor itself.
    result = SubprocessLeanExecutor().verify_build(
        repository=tmp_path,
        command=cmd,
        timeout_seconds=1,
        max_output_bytes=10_000,
        environment_allowlist=["PATH", "SYSTEMROOT", "WINDIR"],
    )
    assert result.timed_out is True
    assert result.exit_code == 124


def test_subprocess_applies_redaction_and_env_scrub(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    monkeypatch.setenv("PATH", os.environ.get("PATH") or "/usr/bin")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_shouldnotappearintheenv")
    monkeypatch.setenv("SAFE_VAR", "ok")
    # Preserve Windows runtime vars python may need.
    allow = ["PATH", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "GITHUB_TOKEN", "SAFE_VAR"]
    script = (
        "import os;"
        "print('token ghp_abcdefghijklmnopqrstuvwxyz012345');"
        "print('GH=' + os.environ.get('GITHUB_TOKEN','missing'));"
        "print('SAFE=' + os.environ.get('SAFE_VAR','missing'))"
    )
    result = SubprocessLeanExecutor().verify_build(
        repository=tmp_path,
        command=[sys.executable, "-c", script],
        timeout_seconds=10,
        max_output_bytes=50_000,
        environment_allowlist=allow,
    )
    assert REDACTION_MARKER in result.stdout
    assert "ghp_abcdefghijklmnopqrstuvwxyz012345" not in result.stdout
    assert "GH=missing" in result.stdout
    assert "SAFE=ok" in result.stdout
