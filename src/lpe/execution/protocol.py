from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ExecutionResult:
    command: tuple[str, ...]
    cwd: Path
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: int
    timed_out: bool


class LeanExecutor(Protocol):
    def verify_build(
        self,
        repository: Path,
        command: list[str],
        timeout_seconds: int,
        max_output_bytes: int,
        environment_allowlist: list[str],
    ) -> ExecutionResult: ...
