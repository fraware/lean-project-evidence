from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from lpe.models import CandidateDescriptor


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "docker: requires a working Docker daemon (skipped when unavailable)",
    )
    config.addinivalue_line(
        "markers",
        "lean: requires Lean/Lake on PATH (skipped when unavailable)",
    )
    config.addinivalue_line(
        "markers",
        "performance: soft §17 budget checks (fail only on >2× regressions)",
    )
    config.addinivalue_line(
        "markers",
        "longevity: scale / migration / historical drills (10k ledger in default CI)",
    )
    config.addinivalue_line(
        "markers",
        "slow: long-running drills such as 100k ledger (excluded from default via -m 'not slow')",
    )


def _docker_available(*, attempts: int = 3, base_delay_s: float = 0.35) -> bool:
    """Return True when ``docker info`` succeeds.

    Retries with short backoff to absorb intermittent daemon/CLI flakes on
    Windows Desktop; still skips when the daemon is truly down.
    """
    if shutil.which("docker") is None:
        return False
    import time

    for attempt in range(attempts):
        try:
            completed = subprocess.run(
                ["docker", "info"],
                check=False,
                capture_output=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            completed = None
        if completed is not None and completed.returncode == 0:
            return True
        if attempt + 1 < attempts:
            time.sleep(base_delay_s * (attempt + 1))
    return False


def _lean_available() -> bool:
    return shutil.which("lake") is not None or shutil.which("lean") is not None


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("docker") is not None and not _docker_available():
        pytest.skip("Docker daemon unavailable (@pytest.mark.docker)")
    if item.get_closest_marker("lean") is not None and not _lean_available():
        pytest.skip("Lean/Lake unavailable (@pytest.mark.lean)")


@pytest.fixture
def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def example_project(repository_root: Path) -> Path:
    return repository_root / "examples" / "minimal-project"


@pytest.fixture
def example_candidate(repository_root: Path) -> CandidateDescriptor:
    path = repository_root / "examples" / "candidates" / "R3-definition-change.json"
    return CandidateDescriptor.model_validate(json.loads(path.read_text(encoding="utf-8")))
