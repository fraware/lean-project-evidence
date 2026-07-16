from __future__ import annotations

import subprocess
import time
from pathlib import Path

from lpe.execution.env import scrub_environment
from lpe.execution.protocol import ExecutionResult
from lpe.execution.redact import redact_secrets


def _truncate(value: str, max_bytes: int) -> str:
    data = value.encode("utf-8", errors="replace")
    if len(data) <= max_bytes:
        return value
    marker = b"\n...[output truncated by lpe]...\n"
    return (data[: max_bytes - len(marker)] + marker).decode(
        "utf-8", errors="replace"
    )


class SubprocessLeanExecutor:
    """Host subprocess executor. Does not enforce network isolation (AUDIT-019)."""

    def verify_build(
        self,
        repository: Path,
        command: list[str],
        timeout_seconds: int,
        max_output_bytes: int,
        environment_allowlist: list[str],
    ) -> ExecutionResult:
        env = scrub_environment(environment_allowlist)
        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=repository,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            timed_out = False
            exit_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return ExecutionResult(
            command=tuple(command),
            cwd=repository,
            exit_code=exit_code,
            stdout=_truncate(redact_secrets(str(stdout)), max_output_bytes),
            stderr=_truncate(redact_secrets(str(stderr)), max_output_bytes),
            elapsed_ms=elapsed_ms,
            timed_out=timed_out,
        )
