"""Week 2: Docker evidence builds — skip cleanly; isolation PASS only when sandboxed."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from lpe.evidence.compiler import compile_evidence
from lpe.execution.allowlist import CommandAllowlistError, validate_build_command
from lpe.execution.sandbox import DockerSandboxExecutor, isolation_status_for_executor
from lpe.models import CandidateDescriptor, FindingStatus, GeneratorProvenance


def _generator() -> GeneratorProvenance:
    return GeneratorProvenance(generator_type="test", name="week2-docker", version="0")


def _patch_project(project: Path, *, build_command: list[str], network_policy: str) -> None:
    path = project / ".lean-project-contract" / "project.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["execution"]["build_command"] = build_command
    data["execution"]["network_policy"] = network_policy
    data["execution"]["timeout_seconds"] = 120
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _docs_candidate() -> CandidateDescriptor:
    return CandidateDescriptor(
        candidate_id="cand-docker-week2",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="# docs\n",
        claimed_intent="docker isolation smoke",
        changed_paths=["README.md"],
        changed_declarations=[],
        generator=_generator(),
    )


def test_isolation_pass_requires_sandboxed_build_ran() -> None:
    """Unit-level honesty: PASS only when Docker + network_isolated + build_ran."""
    status, name = isolation_status_for_executor(
        DockerSandboxExecutor(network_none=True),
        build_ran=True,
        skip_build=False,
        network_isolated=True,
    )
    assert status == "PASS"
    assert name == "docker-sandbox"

    skipped, _ = isolation_status_for_executor(
        DockerSandboxExecutor(network_none=True),
        build_ran=False,
        skip_build=True,
        network_isolated=True,
    )
    assert skipped == "NOT_APPLICABLE"


def test_allowlist_still_rejects_shell_even_for_docker_path() -> None:
    with pytest.raises(CommandAllowlistError, match="shell/interpreter|allowlist"):
        validate_build_command(["bash", "-c", "lake build"])


@pytest.mark.docker
def test_docker_sandbox_flags_network_none_and_hardening(tmp_path: Path) -> None:
    """When Docker is available, verify --network=none and hardening flags are present."""
    (tmp_path / "README").write_text("ok\n", encoding="utf-8")
    executor = DockerSandboxExecutor(image="ubuntu:22.04", network_none=True)
    result = executor.verify_build(
        repository=tmp_path,
        command=["/bin/true"],
        timeout_seconds=60,
        max_output_bytes=50_000,
        environment_allowlist=["PATH", "HOME", "USER", "TMPDIR"],
    )
    joined = " ".join(result.command)
    assert "--network=none" in joined
    assert "--cap-drop=ALL" in joined
    assert "no-new-privileges" in joined
    assert result.timed_out is False
    assert result.exit_code == 0


@pytest.mark.docker
def test_docker_default_mount_is_writable(tmp_path: Path) -> None:
    """Lake needs rw mounts for ``.lake/``; default must not be read-only."""
    (tmp_path / "probe.txt").write_text("x\n", encoding="utf-8")
    executor = DockerSandboxExecutor(image="ubuntu:22.04", network_none=True)
    assert executor.readonly_mount is False
    result = executor.verify_build(
        repository=tmp_path,
        command=[
            "/bin/sh",
            "-c",
            "printf 'ok\\n' > /work/.lpe_write_probe && /bin/cat /work/.lpe_write_probe",
        ],
        timeout_seconds=60,
        max_output_bytes=50_000,
        environment_allowlist=["PATH", "HOME", "USER", "TMPDIR"],
    )
    joined = " ".join(result.command)
    assert ":/work:rw" in joined.replace("\\", "/")
    assert result.exit_code == 0, result.stderr
    assert "ok" in result.stdout
    assert (tmp_path / ".lpe_write_probe").is_file()


@pytest.mark.docker
def test_docker_readonly_mount_fails_closed_with_hint(tmp_path: Path) -> None:
    (tmp_path / "probe.txt").write_text("x\n", encoding="utf-8")
    executor = DockerSandboxExecutor(
        image="ubuntu:22.04", network_none=True, readonly_mount=True
    )
    result = executor.verify_build(
        repository=tmp_path,
        command=["/bin/sh", "-c", "echo fail > /work/cannot_write"],
        timeout_seconds=60,
        max_output_bytes=50_000,
        environment_allowlist=["PATH", "HOME", "USER", "TMPDIR"],
    )
    assert result.exit_code != 0
    assert "LPE_DOCKER_READONLY" in result.stderr
    assert "writable mount" in result.stderr.lower() or "read-only" in result.stderr.lower()


@pytest.mark.docker
def test_compile_isolation_pass_only_after_sandboxed_build(
    example_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """network_policy=deny + real Docker run → execution.isolation PASS; skip_build never PASS."""
    project = tmp_path / "proj"
    shutil.copytree(example_project, project)
    # ubuntu image has no lean; build will FAIL but still ran under network-none sandbox.
    _patch_project(project, build_command=["lean", "--version"], network_policy="deny")
    monkeypatch.setenv("LPE_DOCKER_IMAGE", "ubuntu:22.04")

    packet = compile_evidence(
        project,
        _docs_candidate(),
        skip_build=False,
        use_sandbox=True,
        use_worktree=False,
    )
    build = next(f for f in packet.findings if f.check_id == "lean.build")
    assert build.status is FindingStatus.FAIL  # lean missing in ubuntu image
    joined = " ".join(build.provenance.command)
    assert "--network=none" in joined
    assert "--cap-drop=ALL" in joined

    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    assert isolation.status is FindingStatus.PASS
    assert isolation.details.get("build_ran") is True
    assert isolation.details.get("network_isolated") is True
    assert isolation.details.get("executor") == "docker-sandbox"


@pytest.mark.docker
def test_compile_skip_build_never_claims_isolation_pass(
    example_project: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "proj"
    shutil.copytree(example_project, project)
    _patch_project(project, build_command=["lake", "build"], network_policy="deny")

    packet = compile_evidence(project, _docs_candidate(), skip_build=True)
    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    assert isolation.status is FindingStatus.NOT_APPLICABLE
    assert isolation.status is not FindingStatus.PASS


@pytest.mark.docker
def test_compile_rejects_disallowed_command_before_docker(
    example_project: Path,
    tmp_path: Path,
) -> None:
    project = tmp_path / "proj"
    shutil.copytree(example_project, project)
    _patch_project(project, build_command=["curl", "https://evil.example"], network_policy="deny")
    with pytest.raises(CommandAllowlistError, match="allowlist"):
        compile_evidence(
            project,
            _docs_candidate(),
            skip_build=False,
            use_sandbox=True,
        )
