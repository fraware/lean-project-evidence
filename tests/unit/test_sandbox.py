from __future__ import annotations

from pathlib import Path

import pytest

from lpe.execution.sandbox import DockerSandboxExecutor, isolation_status_for_executor
from lpe.execution.runner import SubprocessLeanExecutor


def test_parse_combined_phase_markers() -> None:
    from lpe.execution.sandbox import parse_combined_phase

    assert parse_combined_phase("LPE_PHASE=build\n") == "build"
    assert parse_combined_phase("noise\nLPE_PHASE=extract\n") == "extract"
    assert parse_combined_phase("LPE_PHASE=build\nLPE_PHASE=ok\n") == "ok"
    assert parse_combined_phase("") is None


def test_validate_extract_out_rel_rejects_traversal() -> None:
    from lpe.execution.sandbox import validate_extract_out_rel

    assert validate_extract_out_rel(".lpe/lean-extraction.json") == ".lpe/lean-extraction.json"
    with pytest.raises(ValueError):
        validate_extract_out_rel("../etc/passwd")
    with pytest.raises(ValueError):
        validate_extract_out_rel("/abs/path")


def test_verify_build_and_extract_single_docker_argv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Combined path packs build+extract into one docker run argv (no second container)."""
    from lpe.execution.sandbox import (
        COMBINED_BUILD_EXTRACT_SCRIPT,
        DockerSandboxExecutor,
        LPE_PHASE_OK,
    )

    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(list(cmd))

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = f"{LPE_PHASE_OK}\n"

        return _Proc()

    monkeypatch.setattr("lpe.execution.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr("lpe.execution.sandbox.subprocess.run", _fake_run)
    (tmp_path / "README").write_text("ok\n", encoding="utf-8")
    executor = DockerSandboxExecutor(image="lpe-lean:4.14", network_none=True)
    result = executor.verify_build_and_extract(
        repository=tmp_path,
        build_command=["lake", "build"],
        extract_out=".lpe/lean-extraction.json",
        timeout_seconds=30,
        max_output_bytes=10_000,
        environment_allowlist=["PATH", "HOME"],
    )
    assert len(calls) == 1
    joined = " ".join(calls[0])
    assert joined.count("docker") == 1 or calls[0][0] == "docker"
    assert "--network=none" in joined
    assert COMBINED_BUILD_EXTRACT_SCRIPT in calls[0]
    assert "lake" in calls[0]
    assert "build" in calls[0]
    assert any(x.startswith("LPE_EXTRACT_OUT=") for x in calls[0])
    assert result.exit_code == 0


def test_isolation_unknown_for_subprocess() -> None:
    status, name = isolation_status_for_executor(
        SubprocessLeanExecutor(), build_ran=True, network_isolated=False
    )
    assert status == "UNKNOWN"
    assert name == "SubprocessLeanExecutor"


def test_isolation_pass_for_docker_when_build_ran() -> None:
    status, name = isolation_status_for_executor(
        DockerSandboxExecutor(),
        build_ran=True,
        skip_build=False,
        network_isolated=True,
        image_digest_resolved=True,
    )
    assert status == "PASS"
    assert name == "docker-sandbox"


def test_isolation_not_pass_for_docker_when_skipped() -> None:
    status, name = isolation_status_for_executor(
        DockerSandboxExecutor(),
        build_ran=False,
        skip_build=True,
        network_isolated=True,
    )
    assert status == "NOT_APPLICABLE"
    assert name == "docker-sandbox"


def test_docker_availability_is_boolean() -> None:
    assert isinstance(DockerSandboxExecutor.is_available(), bool)


def test_container_env_rewrites_windows_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows host PATH must not be forwarded into Linux containers."""
    from lpe.execution.sandbox import _container_environment

    monkeypatch.setenv("PATH", r"C:\Windows\System32;C:\Program Files\Git\cmd")
    monkeypatch.setenv("HOME", r"C:\Users\mateo")
    env = _container_environment(["PATH", "HOME", "USER", "TMPDIR"], uid=0)
    assert "C:\\" not in env["PATH"]
    assert "/root/.elan/bin" in env["PATH"] or "/home/lpe/.elan/bin" in env["PATH"]
    assert env["HOME"] == "/root"


@pytest.mark.skipif(
    not DockerSandboxExecutor.is_available(),
    reason="docker not available",
)
def test_docker_verify_build_smoke(tmp_path: Path) -> None:
    """Optional smoke: run a trivial command in the sandbox when Docker exists."""
    (tmp_path / "README").write_text("ok\n", encoding="utf-8")
    executor = DockerSandboxExecutor(image="ubuntu:22.04", network_none=True)
    # Use an allowlisted binary name; ubuntu image has no lake — expect non-zero.
    result = executor.verify_build(
        repository=tmp_path,
        command=["lean", "--version"],
        timeout_seconds=60,
        max_output_bytes=50_000,
        environment_allowlist=["PATH", "HOME", "USER", "TMPDIR"],
    )
    assert result.timed_out is False
    assert isinstance(result.exit_code, int)
    # Command should include hardening flags.
    joined = " ".join(result.command)
    assert "--network=none" in joined
    assert "--cap-drop=ALL" in joined
    assert "no-new-privileges" in joined
