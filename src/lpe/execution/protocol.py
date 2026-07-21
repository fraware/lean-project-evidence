from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lpe.models import StrictModel


@dataclass(frozen=True)
class ExecutionResult:
    command: tuple[str, ...]
    cwd: Path
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: int
    timed_out: bool


class ValidatedCommand(StrictModel):
    """Allowlisted argv for Lean/Lake execution via the selected executor."""

    argv: tuple[str, ...]
    working_directory: str = "."  # relative to selected snapshot root
    # CLOSURE-014: successor suites must execute on base and candidate.
    snapshot_root: str = "candidate"  # "candidate" | "base"

    @classmethod
    def from_argv(
        cls,
        argv: list[str] | tuple[str, ...],
        *,
        working_directory: str = ".",
        snapshot_root: str = "candidate",
    ) -> ValidatedCommand:
        from lpe.execution.allowlist import validate_build_command

        if snapshot_root not in {"candidate", "base"}:
            raise ValueError(f"snapshot_root must be 'candidate' or 'base', got {snapshot_root!r}")
        validated = validate_build_command(list(argv))
        return cls(
            argv=tuple(validated),
            working_directory=working_directory,
            snapshot_root=snapshot_root,
        )


class ProviderResourceProfile(StrictModel):
    timeout_seconds: int
    max_stdout_bytes: int
    max_stderr_bytes: int
    memory_bytes: int
    pids_limit: int
    cpu_quota: float

    @property
    def max_output_bytes(self) -> int:
        return max(self.max_stdout_bytes, self.max_stderr_bytes)


# Default profiles from closure spec §7.4
DEFAULT_RESOURCE_PROFILES: dict[str, ProviderResourceProfile] = {
    "semantic.statement-diff": ProviderResourceProfile(
        timeout_seconds=60,
        max_stdout_bytes=256 * 1024,
        max_stderr_bytes=256 * 1024,
        memory_bytes=512 * 1024 * 1024,
        pids_limit=128,
        cpu_quota=1.0,
    ),
    "semantic.example-runner": ProviderResourceProfile(
        timeout_seconds=300,
        max_stdout_bytes=1 * 1024 * 1024,
        max_stderr_bytes=1 * 1024 * 1024,
        memory_bytes=2 * 1024 * 1024 * 1024,
        pids_limit=256,
        cpu_quota=2.0,
    ),
    "semantic.counterexample": ProviderResourceProfile(
        timeout_seconds=300,
        max_stdout_bytes=1 * 1024 * 1024,
        max_stderr_bytes=1 * 1024 * 1024,
        memory_bytes=2 * 1024 * 1024 * 1024,
        pids_limit=256,
        cpu_quota=2.0,
    ),
    "semantic.duplicate-retrieval": ProviderResourceProfile(
        timeout_seconds=120,
        max_stdout_bytes=512 * 1024,
        max_stderr_bytes=512 * 1024,
        memory_bytes=1 * 1024 * 1024 * 1024,
        pids_limit=256,
        cpu_quota=2.0,
    ),
    "downstream.replacement": ProviderResourceProfile(
        timeout_seconds=900,
        max_stdout_bytes=2 * 1024 * 1024,
        max_stderr_bytes=2 * 1024 * 1024,
        memory_bytes=4 * 1024 * 1024 * 1024,
        pids_limit=512,
        cpu_quota=4.0,
    ),
    "downstream.successor-suite": ProviderResourceProfile(
        timeout_seconds=900,
        max_stdout_bytes=2 * 1024 * 1024,
        max_stderr_bytes=2 * 1024 * 1024,
        memory_bytes=4 * 1024 * 1024 * 1024,
        pids_limit=512,
        cpu_quota=4.0,
    ),
}


class LeanExecutor(Protocol):
    def verify_build(
        self,
        repository: Path,
        command: list[str],
        timeout_seconds: int,
        max_output_bytes: int,
        environment_allowlist: list[str],
    ) -> ExecutionResult: ...

    def run(
        self,
        *,
        workspace: object,
        command: ValidatedCommand,
        resource_profile: ProviderResourceProfile,
        environment_allowlist: list[str] | None = None,
    ) -> ExecutionResult: ...
