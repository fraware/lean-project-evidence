from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from lpe.execution.env import scrub_environment
from lpe.execution.protocol import ExecutionResult, LeanExecutor
from lpe.execution.redact import redact_secrets
from lpe.execution.runner import _truncate

if TYPE_CHECKING:
    from lpe.workspace.models import ExecutorDescriptor

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
_WIN_PATH_HINT = re.compile(r"[A-Za-z]:\\|;")
_DIGEST_UNRESOLVED = object()

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


# Linux PATH used for unprivileged container user (elan may live under /home/lpe).
_CONTAINER_PATH_LPE = (
    "/home/lpe/.elan/bin:/root/.elan/bin:/home/lean/.elan/bin:"
    "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
)


def _container_environment(allowlist: list[str], *, uid: int | None = None) -> dict[str, str]:
    """Scrub host env, then rewrite Windows PATH/HOME for Linux containers."""
    env = scrub_environment(allowlist)
    path = env.get("PATH", "")
    if path and _WIN_PATH_HINT.search(path):
        env["PATH"] = os.environ.get("LPE_DOCKER_PATH", _CONTAINER_PATH_LPE)
    home = env.get("HOME", "")
    # Prefer /root when running as root so preinstalled elan under /root/.elan works.
    default_home = "/root" if uid == 0 else "/home/lpe"
    if not home or (home and _WIN_PATH_HINT.search(home)):
        env["HOME"] = os.environ.get("LPE_DOCKER_HOME", default_home)
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


def resolve_docker_image_digest(image: str) -> str | None:
    """Resolve a RepoDigest (preferred) or Image Id for ``image`` (CLOSURE-004)."""
    if shutil.which("docker") is None:
        return None
    result = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            "--format",
            "{{if .RepoDigests}}{{index .RepoDigests 0}}{{else}}{{.Id}}{{end}}",
            image,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    raw = (result.stdout or "").strip()
    if not raw:
        return None
    if "@sha256:" in raw:
        return "sha256:" + raw.split("@sha256:", 1)[1]
    if raw.startswith("sha256:"):
        return raw
    return None


def _parse_memory_bytes(limit: str) -> int:
    text = (limit or "2g").strip().lower()
    try:
        if text.endswith("g"):
            return int(float(text[:-1]) * 1024 * 1024 * 1024)
        if text.endswith("m"):
            return int(float(text[:-1]) * 1024 * 1024)
        if text.endswith("k"):
            return int(float(text[:-1]) * 1024)
        return int(text)
    except ValueError:
        return 2 * 1024 * 1024 * 1024


def _format_memory(memory_bytes: int) -> str:
    if memory_bytes % (1024 * 1024 * 1024) == 0:
        return f"{memory_bytes // (1024 * 1024 * 1024)}g"
    if memory_bytes % (1024 * 1024) == 0:
        return f"{memory_bytes // (1024 * 1024)}m"
    return str(memory_bytes)


def _host_uid_gid() -> tuple[int, int]:
    uid = os.environ.get("LPE_DOCKER_UID")
    gid = os.environ.get("LPE_DOCKER_GID")
    if uid is not None and gid is not None:
        return int(uid), int(gid)
    try:
        return os.getuid(), os.getgid()  # type: ignore[attr-defined]
    except AttributeError:
        # Windows / non-POSIX Docker Desktop: images currently ship elan under
        # /root. Default to root until the published digest image is unprivileged.
        # Linux CI should rely on getuid/getgid or explicit LPE_DOCKER_UID/GID.
        return 0, 0


class DockerNotAvailableError(RuntimeError):
    pass


class DockerSandboxExecutor:
    """Run commands in a hardened Docker sandbox (CLOSURE-004).

    Hardening: ``--read-only`` root, non-root ``--user``, cap-drop, no-new-privileges,
    network none (when configured), memory=swap, cpus, pids, fsize ulimit, tmpfs for
    ``/tmp`` and ``/home/lpe``, ephemeral mounts for ``/worktree-output`` and
    ``/lake-cache``. The evaluated tree is an ephemeral worktree mounted at ``/work``
    (writable); the operator checkout is never the mount target for writes.

    Prefer ``verify_build_and_extract`` for Docker toolchain compiles: one
    ``docker run`` executes allowlisted ``lake build`` then ``lake exe lpe_extract``
    (set ``LPE_DOCKER_COMBINED_BUILD_EXTRACT=0`` to force sequential fallback).
    """

    def __init__(
        self,
        *,
        image: str | None = None,
        memory_limit: str | None = None,
        memory_bytes: int | None = None,
        cpu_quota: float = 2.0,
        pids_limit: int = 256,
        fsize_bytes: int = 512 * 1024 * 1024,
        readonly_mount: bool | None = None,
        readonly_root: bool = True,
        source_mount_readonly: bool = True,
        network_none: bool = True,
        uid: int | None = None,
        gid: int | None = None,
    ) -> None:
        self.image = image or os.environ.get("LPE_DOCKER_IMAGE", DEFAULT_DOCKER_IMAGE)
        if memory_bytes is not None:
            self.memory_bytes = memory_bytes
            self.memory_limit = _format_memory(memory_bytes)
        else:
            self.memory_limit = memory_limit or os.environ.get(
                "LPE_DOCKER_MEMORY", DEFAULT_MEMORY_LIMIT
            )
            self.memory_bytes = _parse_memory_bytes(self.memory_limit)
        self.cpu_quota = cpu_quota
        self.pids_limit = pids_limit
        self.fsize_bytes = fsize_bytes
        # Legacy flag: when True, mount /work as :ro (breaks Lake). Default False —
        # ephemeral candidate worktrees are mounted rw; rootfs stays --read-only.
        if readonly_mount is None:
            readonly_mount = os.environ.get("LPE_DOCKER_READONLY", "").lower() in {
                "1",
                "true",
                "yes",
            }
        self.readonly_mount = readonly_mount
        self.readonly_root = readonly_root
        self.source_mount_readonly = source_mount_readonly
        self.network_none = network_none
        host_uid, host_gid = _host_uid_gid()
        self.uid = uid if uid is not None else host_uid
        self.gid = gid if gid is not None else host_gid
        self._resolved_digest: str | None | object = _DIGEST_UNRESOLVED

    @staticmethod
    def is_available() -> bool:
        return shutil.which("docker") is not None

    def image_digest(self) -> str | None:
        if self._resolved_digest is _DIGEST_UNRESOLVED:
            self._resolved_digest = resolve_docker_image_digest(self.image)
        assert self._resolved_digest is not _DIGEST_UNRESOLVED
        return self._resolved_digest  # type: ignore[return-value]

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

    def run(
        self,
        *,
        workspace: object,
        command: object,
        resource_profile: object,
        environment_allowlist: list[str] | None = None,
    ) -> ExecutionResult:
        from lpe.execution.protocol import ProviderResourceProfile, ValidatedCommand

        assert isinstance(command, ValidatedCommand)
        assert isinstance(resource_profile, ProviderResourceProfile)
        root_attr = (
            "base_path"
            if getattr(command, "snapshot_root", "candidate") == "base"
            else "candidate_path"
        )
        root = Path(getattr(workspace, root_attr))
        cwd = (root / command.working_directory).resolve()
        if not cwd.is_relative_to(root.resolve()):
            raise ValueError(f"command working_directory escapes {root_attr} workspace")
        return self.verify_build(
            repository=cwd,
            command=list(command.argv),
            timeout_seconds=resource_profile.timeout_seconds,
            max_output_bytes=resource_profile.max_output_bytes,
            environment_allowlist=list(environment_allowlist or ["PATH", "HOME", "USER", "TMPDIR"]),
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
        source_origin: Path | None = None,
    ) -> ExecutionResult:
        if not self.is_available():
            raise DockerNotAvailableError("docker is not available on PATH")

        env = _container_environment(environment_allowlist, uid=self.uid)
        if extra_env:
            env.update(extra_env)
        env.setdefault("ELAN_HOME", "/lake-cache/elan")
        env.setdefault("XDG_CACHE_HOME", "/lake-cache/xdg")

        # Ephemeral candidate / worktree is writable at /work. Operator origin
        # (when provided) is mounted read-only at /source and never used as cwd.
        work_mode = "ro" if self.readonly_mount else "rw"
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            f"--memory={self.memory_limit}",
            f"--memory-swap={self.memory_limit}",
            f"--cpus={self.cpu_quota}",
            f"--pids-limit={self.pids_limit}",
            f"--ulimit=fsize={self.fsize_bytes}",
            "--user",
            f"{self.uid}:{self.gid}",
            "-v",
            f"{repository.resolve()}:/work:{work_mode}",
            "-w",
            "/work",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=256m",
            "--tmpfs",
            "/home/lpe:rw,noexec,nosuid,nodev,size=256m",
            "--tmpfs",
            "/worktree-output:rw,noexec,nosuid,nodev,size=512m",
            "--tmpfs",
            "/lake-cache:rw,noexec,nosuid,nodev,size=512m",
        ]
        if self.readonly_root:
            docker_cmd.append("--read-only")
        if source_origin is not None and self.source_mount_readonly:
            docker_cmd.extend(["-v", f"{source_origin.resolve()}:/source:ro"])
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
            stdout = (
                exc.stdout.decode("utf-8", errors="replace")
                if isinstance(exc.stdout, (bytes, bytearray))
                else (exc.stdout or "")
            )
            stderr = (
                exc.stderr.decode("utf-8", errors="replace")
                if isinstance(exc.stderr, (bytes, bytearray))
                else (exc.stderr or "")
            )

        if self.readonly_mount and exit_code != 0:
            hint = (
                "Docker /work mount is read-only (LPE_DOCKER_READONLY). "
                "Lake/Lean builds need a writable ephemeral worktree mount."
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


def build_executor_descriptor(
    executor: DockerSandboxExecutor,
    *,
    network_policy: str,
    image_digest: str | None = None,
) -> ExecutorDescriptor:
    from lpe.workspace.models import ExecutorDescriptor

    digest = image_digest if image_digest is not None else executor.image_digest()
    policy: Literal["deny", "allow"] = "deny" if network_policy == "deny" else "allow"
    return ExecutorDescriptor(
        backend="docker",
        image_reference=executor.image,
        image_digest=digest,
        network_policy=policy,
        uid=executor.uid,
        gid=executor.gid,
        memory_bytes=executor.memory_bytes,
        cpu_quota=executor.cpu_quota,
        pids_limit=executor.pids_limit,
        readonly_root=executor.readonly_root,
        source_mount_readonly=executor.source_mount_readonly,
    )


def isolation_status_for_executor(
    executor: LeanExecutor,
    *,
    build_ran: bool = False,
    skip_build: bool = False,
    network_isolated: bool = False,
    image_digest_resolved: bool | None = None,
) -> tuple[str, str]:
    """Return (status, executor_name) for execution.isolation finding.

    Isolation PASS requires an actual sandboxed build with network isolation and
    a resolved image digest. skip_build never claims PASS (NOT_APPLICABLE).
    Host subprocess never claims PASS. Unresolved digest → UNKNOWN.
    """
    name = (
        "docker-sandbox" if isinstance(executor, DockerSandboxExecutor) else type(executor).__name__
    )
    if skip_build or not build_ran:
        return "NOT_APPLICABLE", name
    if isinstance(executor, DockerSandboxExecutor) and network_isolated:
        digest_ok = (
            image_digest_resolved
            if image_digest_resolved is not None
            else bool(executor.image_digest())
        )
        if digest_ok:
            return "PASS", name
        return "UNKNOWN", name
    return "UNKNOWN", name
