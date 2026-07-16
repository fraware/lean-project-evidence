from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from lpe.execution.env import scrub_environment
from lpe.execution.protocol import ExecutionResult, LeanExecutor
from lpe.execution.redact import redact_secrets
from lpe.execution.runner import _truncate

# Default is a generic base image (no Lean/Lake). Prefer a Lean-capable image via
# LPE_DOCKER_IMAGE — e.g. local `lpe-lean:4.14` from docker/lpe-lean/ (elan + Lean
# matching the project toolchain). Community `leanprovercommunity/lean4` exists but
# is stale; there is no maintained official leanprover/lean4 Docker Hub image.
# Documented in SECURITY.md and docker/lpe-lean/README.md.
DEFAULT_DOCKER_IMAGE = "ubuntu:22.04"
DEFAULT_LEAN_DOCKER_IMAGE = "lpe-lean:4.14"
DEFAULT_MEMORY_LIMIT = "2g"

# Linux PATH used inside containers when the host PATH is Windows-flavored
# (Docker Desktop on Windows). Includes common elan install prefixes.
_CONTAINER_PATH = (
    "/root/.elan/bin:/home/lean/.elan/bin:"
    "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
)
_WIN_PATH_HINT = re.compile(r"[A-Za-z]:\\|;")

# Combined build+extract runs inside one ``docker run`` via a fixed script body.
# User argv is never interpolated into the script — only passed as ``"$@"``.
# Phase markers on stderr let the compiler fail closed without a second container.
LPE_PHASE_BUILD = "LPE_PHASE=build"
LPE_PHASE_EXTRACT = "LPE_PHASE=extract"
LPE_PHASE_OK = "LPE_PHASE=ok"
COMBINED_BUILD_EXTRACT_SCRIPT = f"""
set +e
"$@"
b=$?
if [ "$b" -ne 0 ]; then
  printf '%s\\n' '{LPE_PHASE_BUILD}' >&2
  exit "$b"
fi
lake exe lpe_extract "$LPE_EXTRACT_OUT"
e=$?
if [ "$e" -ne 0 ]; then
  printf '%s\\n' '{LPE_PHASE_EXTRACT}' >&2
  exit "$e"
fi
printf '%s\\n' '{LPE_PHASE_OK}' >&2
exit 0
""".strip()


def combined_build_extract_enabled() -> bool:
    """Return True unless ``LPE_DOCKER_COMBINED_BUILD_EXTRACT`` disables the path."""
    return os.environ.get("LPE_DOCKER_COMBINED_BUILD_EXTRACT", "1").lower() not in {
        "0",
        "false",
        "no",
    }


def parse_combined_phase(stderr: str, stdout: str = "") -> str | None:
    """Return ``build`` / ``extract`` / ``ok`` from combined-script phase markers."""
    phase: str | None = None
    for line in f"{stderr}\n{stdout}".splitlines():
        token = line.strip()
        if token == LPE_PHASE_BUILD:
            phase = "build"
        elif token == LPE_PHASE_EXTRACT:
            phase = "extract"
        elif token == LPE_PHASE_OK:
            phase = "ok"
    return phase


def validate_extract_out_rel(extract_out: str) -> str:
    """Reject absolute / parent-path extract outputs (container-relative only)."""
    raw = (extract_out or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or raw.startswith("~"):
        raise ValueError(f"extract_out must be a relative path, got {extract_out!r}")
    parts = Path(raw).parts
    if ".." in parts or parts[:1] == ("/",):
        raise ValueError(f"extract_out must not contain '..', got {extract_out!r}")
    return raw


def _container_environment(allowlist: list[str]) -> dict[str, str]:
    """Scrub host env, then rewrite Windows PATH/HOME for Linux containers."""
    env = scrub_environment(allowlist)
    path = env.get("PATH", "")
    if path and _WIN_PATH_HINT.search(path):
        env["PATH"] = os.environ.get("LPE_DOCKER_PATH", _CONTAINER_PATH)
    home = env.get("HOME", "")
    if home and _WIN_PATH_HINT.search(home):
        env["HOME"] = os.environ.get("LPE_DOCKER_HOME", "/root")
    return env


def docker_image_present(image: str) -> bool:
    """Return True when ``docker image inspect`` succeeds for ``image``."""
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


class DockerNotAvailableError(RuntimeError):
    pass


class DockerSandboxExecutor:
    """Run build commands inside Docker with network-none and scrubbed environment.

    Mount policy: the repository is mounted read-write at ``/work`` so Lake/Lean can
    write build artifacts (``.lake/``, ``build/``). Prefer ``--worktree`` so the live
    checkout is not mutated. Set ``LPE_DOCKER_READONLY=1`` to force ``:ro``; builds that
    need write access will then fail with a Docker permission/IO error (fail closed).

    Prefer ``verify_build_and_extract`` for Docker toolchain compiles: one
    ``docker run`` executes allowlisted ``lake build`` then ``lake exe lpe_extract``
    (set ``LPE_DOCKER_COMBINED_BUILD_EXTRACT=0`` to force sequential fallback).
    """

    def __init__(
        self,
        *,
        image: str | None = None,
        memory_limit: str | None = None,
        readonly_mount: bool | None = None,
        network_none: bool = True,
    ) -> None:
        self.image = image or os.environ.get("LPE_DOCKER_IMAGE", DEFAULT_DOCKER_IMAGE)
        self.memory_limit = memory_limit or os.environ.get(
            "LPE_DOCKER_MEMORY", DEFAULT_MEMORY_LIMIT
        )
        if readonly_mount is None:
            readonly_mount = os.environ.get("LPE_DOCKER_READONLY", "").lower() in {
                "1",
                "true",
                "yes",
            }
        self.readonly_mount = readonly_mount
        self.network_none = network_none

    @staticmethod
    def is_available() -> bool:
        return shutil.which("docker") is not None

    def verify_build(
        self,
        repository: Path,
        command: list[str],
        timeout_seconds: int,
        max_output_bytes: int,
        environment_allowlist: list[str],
    ) -> ExecutionResult:
        return self._run_docker(
            repository=repository,
            command=command,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            environment_allowlist=environment_allowlist,
        )

    def verify_build_and_extract(
        self,
        repository: Path,
        build_command: list[str],
        extract_out: str,
        timeout_seconds: int,
        max_output_bytes: int,
        environment_allowlist: list[str],
    ) -> ExecutionResult:
        """One ``docker run``: allowlisted build, then ``lake exe lpe_extract``.

        The shell wrapper is fixed (not user-controlled). ``build_command`` is passed
        as argv to ``"$@"`` after allowlist validation by the caller. Extract output
        path is passed only via ``LPE_EXTRACT_OUT`` (validated relative path).
        """
        if not build_command:
            raise ValueError("build_command must not be empty for combined build+extract")
        out_rel = validate_extract_out_rel(extract_out)
        # argv: sh -ec SCRIPT sh <build...>  →  $0=sh, "$@"=build argv
        combined = [
            "sh",
            "-ec",
            COMBINED_BUILD_EXTRACT_SCRIPT,
            "sh",
            *list(build_command),
        ]
        return self._run_docker(
            repository=repository,
            command=combined,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            environment_allowlist=environment_allowlist,
            extra_env={"LPE_EXTRACT_OUT": out_rel},
        )

    def _run_docker(
        self,
        *,
        repository: Path,
        command: list[str],
        timeout_seconds: int,
        max_output_bytes: int,
        environment_allowlist: list[str],
        extra_env: dict[str, str] | None = None,
    ) -> ExecutionResult:
        if not self.is_available():
            raise DockerNotAvailableError("docker is not available on PATH")

        env = _container_environment(environment_allowlist)
        if extra_env:
            env.update(extra_env)
        mount_mode = "ro" if self.readonly_mount else "rw"
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            f"--memory={self.memory_limit}",
            "--pids-limit=256",
            "-v",
            f"{repository.resolve()}:/work:{mount_mode}",
            "-w",
            "/work",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=256m",
        ]
        if self.network_none:
            docker_cmd.append("--network=none")
        for key, value in env.items():
            docker_cmd.extend(["-e", f"{key}={value}"])
        docker_cmd.append(self.image)
        docker_cmd.extend(command)

        started = time.monotonic()
        try:
            result = subprocess.run(
                docker_cmd,
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

        if self.readonly_mount and exit_code != 0:
            hint = (
                "Docker mount is read-only (LPE_DOCKER_READONLY). "
                "Lake/Lean builds need a writable mount for artifacts; unset "
                "LPE_DOCKER_READONLY or use --worktree with the default rw mount."
            )
            stderr = f"{stderr}\n{hint}" if stderr else hint

        elapsed_ms = int((time.monotonic() - started) * 1000)
        return ExecutionResult(
            command=tuple(docker_cmd),
            cwd=repository,
            exit_code=exit_code,
            stdout=_truncate(redact_secrets(str(stdout)), max_output_bytes),
            stderr=_truncate(redact_secrets(str(stderr)), max_output_bytes),
            elapsed_ms=elapsed_ms,
            timed_out=timed_out,
        )


def isolation_status_for_executor(
    executor: LeanExecutor,
    *,
    build_ran: bool = False,
    skip_build: bool = False,
    network_isolated: bool = False,
) -> tuple[str, str]:
    """Return (status, executor_name) for execution.isolation finding.

    Isolation PASS requires an actual sandboxed build with network isolation.
    skip_build never claims PASS (NOT_APPLICABLE). Host subprocess never claims PASS.
    """
    name = (
        "docker-sandbox"
        if isinstance(executor, DockerSandboxExecutor)
        else type(executor).__name__
    )
    if skip_build or not build_ran:
        return "NOT_APPLICABLE", name
    if isinstance(executor, DockerSandboxExecutor) and network_isolated:
        return "PASS", name
    return "UNKNOWN", name


def isolation_status_for_executor(
    executor: LeanExecutor,
    *,
    build_ran: bool = False,
    skip_build: bool = False,
    network_isolated: bool = False,
) -> tuple[str, str]:
    """Return (status, executor_name) for execution.isolation finding.

    Isolation PASS requires an actual sandboxed build with network isolation.
    skip_build never claims PASS (NOT_APPLICABLE). Host subprocess never claims PASS.
    """
    name = (
        "docker-sandbox"
        if isinstance(executor, DockerSandboxExecutor)
        else type(executor).__name__
    )
    if skip_build or not build_ran:
        return "NOT_APPLICABLE", name
    if isinstance(executor, DockerSandboxExecutor) and network_isolated:
        return "PASS", name
    return "UNKNOWN", name
