"""Orchestration overhead: skip-build baseline + optional Docker cold-start."""

from __future__ import annotations

from pathlib import Path

import pytest

from lpe.contract.loader import load_contract
from lpe.evidence.compiler import compile_evidence
from lpe.execution.sandbox import DockerSandboxExecutor
from lpe.models import CandidateDescriptor
from tests.performance.budgets import assert_within_soft_budget
from tests.performance.metrics import record, timed


@pytest.mark.performance
def test_orchestration_skip_build_baseline(
    example_project: Path,
    example_candidate: CandidateDescriptor,
) -> None:
    """Policy-only path: no container cost; isolation must not claim PASS.

    True orchestration/Lean ratio (§17 <10%) needs a real Lean wall clock; that
    is documented in the Week 3 baseline. This test guards skip-build orchestration
    stay cheap.
    """
    contract = load_contract(example_project)
    with timed() as elapsed:
        packet = compile_evidence(
            example_project,
            example_candidate,
            skip_build=True,
            contract=contract,
        )
    orch_s = elapsed[0]
    record(
        "orchestration_skip_build_s",
        orch_s,
        unit="s",
        notes="skip_build orchestration wall (Lean wall ≈ 0)",
    )
    assert_within_soft_budget("orchestration_skip_build_s", orch_s)

    isolation = next(
        (f for f in packet.findings if f.check_id == "execution.isolation"),
        None,
    )
    assert isolation is not None
    assert isolation.status.value in {"NOT_APPLICABLE", "UNKNOWN"}


@pytest.mark.performance
@pytest.mark.docker
def test_docker_cold_start_cost(tmp_path: Path) -> None:
    """Measure Docker container create+run vs host insecure path when Docker exists.

    Does not weaken security: host path is measured for documentation only and is
    not used as a default. Skipped when Docker daemon is unavailable.
    """
    (tmp_path / "README").write_text("ok\n", encoding="utf-8")
    # Trivial allowlisted-shaped binary; ubuntu may lack lean — timing still valid.
    docker = DockerSandboxExecutor(image="ubuntu:22.04", network_none=True)

    with timed() as elapsed:
        docker_result = docker.verify_build(
            repository=tmp_path,
            command=["lean", "--version"],
            timeout_seconds=60,
            max_output_bytes=50_000,
            environment_allowlist=["PATH", "HOME", "USER", "TMPDIR"],
        )
    docker_s = elapsed[0]
    record(
        "docker_cold_start_s",
        docker_s,
        unit="s",
        notes=(
            f"docker run --rm ubuntu:22.04 lean --version; "
            f"exit={docker_result.exit_code} (command may be missing in image); "
            "combined build+extract uses one container start "
            "(sandbox_invocations=1) vs sequential=2"
        ),
    )

    # Document preferred Docker cost model: one invocation for build+extract.
    record(
        "docker_combined_build_extract_invocations",
        1.0,
        unit="count",
        notes=(
            "Preferred DockerSandboxExecutor.verify_build_and_extract path; "
            "set LPE_DOCKER_COMBINED_BUILD_EXTRACT=0 for sequential fallback (2 starts)"
        ),
    )

    from lpe.execution.runner import SubprocessLeanExecutor

    host = SubprocessLeanExecutor()
    with timed() as elapsed:
        host_result = host.verify_build(
            repository=tmp_path,
            command=["python", "-c", "print(0)"],
            timeout_seconds=30,
            max_output_bytes=10_000,
            environment_allowlist=["PATH", "HOME", "USER", "TMPDIR", "SYSTEMROOT"],
        )
    host_s = elapsed[0]
    record(
        "host_insecure_trivial_s",
        host_s,
        unit="s",
        notes=f"host python -c print; exit={host_result.exit_code}",
    )
    # Soft sanity: Docker cold start should complete well under a minute on CI.
    assert docker_s < 60.0
    assert host_s < 10.0
