"""AUDIT-001 / AUDIT-019: Docker default; host exec and network_policy fail-closed."""

from __future__ import annotations

from pathlib import Path

import pytest

from lpe.evidence.compiler import (
    HostExecutionRefusedError,
    NetworkPolicyError,
    compile_evidence,
)
from lpe.execution.sandbox import DockerSandboxExecutor
from lpe.models import CandidateDescriptor, GeneratorProvenance


def _candidate() -> CandidateDescriptor:
    return CandidateDescriptor(
        candidate_id="cand-exec-defaults",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="# comment\n",
        claimed_intent="execution defaults",
        changed_paths=["README.md"],
        changed_declarations=[],
        generator=GeneratorProvenance(generator_type="test", name="test", version="0"),
    )


def test_host_exec_refused_without_insecure_host_exec_flag(
    example_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invariant: host subprocess builds never run without --insecure-host-exec."""
    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))
    with pytest.raises(HostExecutionRefusedError, match="insecure-host-exec"):
        compile_evidence(
            example_project,
            _candidate(),
            skip_build=False,
            insecure_host_exec=False,
        )


def test_network_policy_deny_refuses_host_exec_even_with_insecure_flag(
    example_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invariant: network_policy=deny cannot be satisfied by host subprocess."""
    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))
    with pytest.raises(NetworkPolicyError, match="network_policy"):
        compile_evidence(
            example_project,
            _candidate(),
            skip_build=False,
            insecure_host_exec=True,
        )


def test_skip_build_does_not_require_host_or_docker(
    example_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invariant: --skip-build is policy-only and never claims isolation PASS."""
    from lpe.models import FindingStatus

    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))
    packet = compile_evidence(example_project, _candidate(), skip_build=True)
    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    assert isolation.status is not FindingStatus.PASS
