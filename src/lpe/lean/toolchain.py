"""Invoke Lake/Lean to produce ``.lpe/lean-extraction.json`` (toolchain path).

Export protocol
---------------
Lean projects may emit extraction JSON by any of:

1. ``lake exe lpe_extract`` (recommended; see ``tests/fixtures/lean_project/``)
2. ``lake run lpe_extract`` / custom script writing the same schema
3. Committing a pre-built ``.lpe/lean-extraction.json``

Preferred schema is ``extraction_schema_version: "1.1"`` with
``declaration_dependency_edges`` (Environment constant deps) and
``import_edges`` (module→module). Older artifacts without that field remain
loadable (implicit 1.0 via ``dependency_edges`` only).

After a sandboxed ``lake build``, callers should pass the same ``LeanExecutor``
so ``lake exe lpe_extract`` runs inside the Docker sandbox (same image,
``--network=none``, rw mount) and does not require host Lake. Prefer one
combined ``docker run`` (``verify_build_and_extract``) when available.

LPE never invents ``extractor: lean.toolchain`` / ``complete: true`` from regex
alone. When Lake is absent, callers fall back to ``regex-stub`` (UNKNOWN axioms).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from lpe.hashing import sha256_text
from lpe.lean.extractor import (
    TOOLCHAIN_EXTRACTOR,
    LeanExtractionResult,
    TOOLCHAIN_RESULT_CANDIDATES,
    load_toolchain_json,
)

if TYPE_CHECKING:
    from lpe.execution.protocol import LeanExecutor


DEFAULT_EXTRACT_TIMEOUT = 300
DEFAULT_EXTRACT_MAX_OUTPUT_BYTES = 2_000_000
NOTE_HOST_EXTRACT = "produced by lake exe lpe_extract"
NOTE_DOCKER_EXTRACT = "produced by lake exe lpe_extract via docker-sandbox"


def _lake_bin() -> str | None:
    return shutil.which("lake")


def extract_executor_label(executor: LeanExecutor | None) -> str | None:
    """Stable provenance label for findings (``docker-sandbox`` / host class name)."""
    if executor is None:
        return None
    # Local import avoids pulling Docker into cold import paths.
    from lpe.execution.sandbox import DockerSandboxExecutor

    if isinstance(executor, DockerSandboxExecutor):
        return "docker-sandbox"
    return type(executor).__name__


def has_lakefile(repository: Path) -> bool:
    return (repository / "lakefile.lean").is_file() or (repository / "lakefile.toml").is_file()


def project_declares_lpe_extract(repository: Path) -> bool:
    """Cheap text check for an ``lpe_extract`` Lake exe / script target."""
    for name in ("lakefile.toml", "lakefile.lean"):
        path = repository / name
        if path.is_file() and "lpe_extract" in path.read_text(
            encoding="utf-8", errors="replace"
        ):
            return True
    return False


def extraction_artifact_path(repository: Path) -> Path:
    override = os.environ.get("LPE_LEAN_EXTRACTION_JSON")
    if override:
        return Path(override)
    return repository / TOOLCHAIN_RESULT_CANDIDATES[0]


def _fill_signature_hashes(data: dict) -> dict:
    """Ensure each declaration has a content-addressed signature_hash."""
    decls = data.get("declarations") or []
    for item in decls:
        if not item.get("signature_hash") and item.get("signature"):
            item["signature_hash"] = sha256_text(str(item["signature"]))
    return data


def _normalize_and_load(path: Path) -> LeanExtractionResult | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return load_toolchain_json(path)
    raw = _fill_signature_hashes(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    return load_toolchain_json(path)


def _persist_notes(path: Path, *extra_notes: str) -> LeanExtractionResult | None:
    """Reload artifact, merge notes into JSON on disk, return loaded result."""
    loaded = _normalize_and_load(path)
    if loaded is None:
        return None
    merged = list(dict.fromkeys([*loaded.notes, *extra_notes]))
    loaded.notes = merged
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return loaded
    raw["notes"] = merged
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    return loaded


def _run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _result_from_exit(
    *,
    returncode: int,
    stdout: str,
    stderr: str,
    artifact: Path,
    provenance_note: str,
    via_executor: bool,
) -> LeanExtractionResult | None:
    """Map a finished extract process to a loaded result or fail-closed errors."""
    if returncode != 0:
        err = (stderr or stdout or "").strip()
        # Target may not exist — not an error for adaptive host path.
        if not via_executor:
            if "unknown target" in err.lower() or "unknown executable" in err.lower():
                return None
            if "lpe_extract" in err.lower() and (
                "unknown" in err.lower() or "not found" in err.lower()
            ):
                return None
        return LeanExtractionResult(
            errors=[f"lake exe lpe_extract exit {returncode}: {err[:800]}"],
            extractor=TOOLCHAIN_EXTRACTOR,
            complete=False,
            toolchain_available=True,
            notes=[
                "lake exe lpe_extract failed; not claiming toolchain completeness",
                provenance_note,
            ],
        )

    loaded = _persist_notes(artifact, provenance_note)
    if loaded is not None:
        return loaded
    return LeanExtractionResult(
        errors=["lpe_extract exited 0 but lean-extraction.json was not written"],
        extractor=TOOLCHAIN_EXTRACTOR,
        complete=False,
        toolchain_available=True,
        notes=[provenance_note],
    )


def finalize_extract_from_exit(
    repository: Path,
    *,
    returncode: int,
    stdout: str,
    stderr: str,
    provenance_note: str,
    via_executor: bool = True,
) -> LeanExtractionResult | None:
    """Public wrapper for combined/sequential sandboxed extract exit mapping."""
    return _result_from_exit(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        artifact=extraction_artifact_path(repository),
        provenance_note=provenance_note,
        via_executor=via_executor,
    )


def build_failed_before_extract_result(
    *,
    exit_code: int,
    provenance_note: str,
) -> LeanExtractionResult:
    """Fail closed when the build phase fails before extract can run."""
    return LeanExtractionResult(
        errors=[
            f"exact-environment build failed (exit {exit_code}); "
            "extract not run (no toolchain completeness claim)"
        ],
        extractor=TOOLCHAIN_EXTRACTOR,
        complete=False,
        toolchain_available=True,
        notes=[
            "build failed before extract; not claiming toolchain completeness",
            provenance_note,
        ],
    )


def try_run_lake_extract(
    repository: Path,
    *,
    timeout_seconds: int | None = None,
    force: bool = False,
    executor: LeanExecutor | None = None,
    max_output_bytes: int | None = None,
    environment_allowlist: list[str] | None = None,
) -> LeanExtractionResult | None:
    """Run Lake-backed extraction when possible; return loaded result or None.

    Prefers an existing complete toolchain JSON unless ``force`` is True.
    Invokes ``lake exe lpe_extract`` when that target exists, else honors
    ``LPE_LEAN_EXTRACT_CMD`` (shell-split via list env is not supported; use
    a single executable + args in ``LPE_LEAN_EXTRACT_CMD`` space-separated).

    When ``executor`` is provided (typically the same sandbox used for
    ``lake build``), extract runs via that executor — no host Lake required.
    Sandboxed extract failures fail closed (incomplete result with errors).
    """
    timeout = timeout_seconds or int(
        os.environ.get("LPE_LEAN_EXTRACT_TIMEOUT", DEFAULT_EXTRACT_TIMEOUT)
    )
    output_cap = max_output_bytes or int(
        os.environ.get("LPE_LEAN_EXTRACT_MAX_OUTPUT", DEFAULT_EXTRACT_MAX_OUTPUT_BYTES)
    )
    allowlist = list(environment_allowlist or ["PATH", "HOME", "USER", "TMPDIR", "SYSTEMROOT"])
    artifact = extraction_artifact_path(repository)
    label = extract_executor_label(executor)
    if label == "docker-sandbox":
        provenance_note = NOTE_DOCKER_EXTRACT
    elif label is not None:
        provenance_note = f"{NOTE_HOST_EXTRACT} via {label}"
    else:
        provenance_note = NOTE_HOST_EXTRACT

    if not force:
        loaded = _normalize_and_load(artifact)
        if (
            loaded is not None
            and loaded.extractor == TOOLCHAIN_EXTRACTOR
            and loaded.complete
            and not loaded.errors
        ):
            return loaded
        for rel in TOOLCHAIN_RESULT_CANDIDATES:
            alt = repository / rel
            if alt == artifact:
                continue
            loaded = _normalize_and_load(alt)
            if (
                loaded is not None
                and loaded.extractor == TOOLCHAIN_EXTRACTOR
                and loaded.complete
                and not loaded.errors
            ):
                return loaded

    if not has_lakefile(repository):
        return None

    custom = os.environ.get("LPE_LEAN_EXTRACT_CMD", "").strip()
    out_rel = str(artifact.relative_to(repository)).replace("\\", "/")

    if custom:
        cmd = custom.split()
    elif project_declares_lpe_extract(repository):
        # Bare "lake" when sandboxed — image PATH supplies the binary.
        # Host path resolves to the full which() path below.
        cmd = ["lake", "exe", "lpe_extract", out_rel]
    else:
        return None

    if executor is not None:
        from lpe.execution.allowlist import validate_build_command

        cmd = validate_build_command(cmd)
        try:
            result = executor.verify_build(
                repository=repository,
                command=cmd,
                timeout_seconds=timeout,
                max_output_bytes=output_cap,
                environment_allowlist=allowlist,
            )
        except (OSError, RuntimeError) as exc:
            return LeanExtractionResult(
                errors=[f"lake exe lpe_extract failed: {exc}"],
                extractor=TOOLCHAIN_EXTRACTOR,
                complete=False,
                toolchain_available=True,
                notes=["sandboxed lpe_extract invocation failed", provenance_note],
            )
        if custom:
            if result.exit_code != 0:
                return LeanExtractionResult(
                    errors=[
                        f"LPE_LEAN_EXTRACT_CMD exit {result.exit_code}: "
                        f"{(result.stderr or result.stdout)[:800]}"
                    ],
                    extractor=TOOLCHAIN_EXTRACTOR,
                    complete=False,
                    toolchain_available=True,
                    notes=[provenance_note],
                )
            loaded = _persist_notes(artifact, provenance_note)
            if loaded is not None:
                return loaded
            return LeanExtractionResult(
                errors=["extract command succeeded but lean-extraction.json missing"],
                extractor=TOOLCHAIN_EXTRACTOR,
                complete=False,
                toolchain_available=True,
                notes=[provenance_note],
            )
        return _result_from_exit(
            returncode=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            artifact=artifact,
            provenance_note=provenance_note,
            via_executor=True,
        )

    # Host subprocess path (CLI / adaptive extractor without a sandbox executor).
    lake = _lake_bin()
    if lake is None:
        return None

    if custom:
        try:
            proc = _run_cmd(cmd, cwd=repository, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return LeanExtractionResult(
                errors=[f"LPE_LEAN_EXTRACT_CMD failed: {exc}"],
                extractor=TOOLCHAIN_EXTRACTOR,
                complete=False,
                toolchain_available=True,
            )
        if proc.returncode != 0:
            return LeanExtractionResult(
                errors=[
                    f"LPE_LEAN_EXTRACT_CMD exit {proc.returncode}: "
                    f"{(proc.stderr or proc.stdout)[:800]}"
                ],
                extractor=TOOLCHAIN_EXTRACTOR,
                complete=False,
                toolchain_available=True,
            )
        loaded = _normalize_and_load(artifact)
        if loaded is not None:
            return loaded
        return LeanExtractionResult(
            errors=["extract command succeeded but lean-extraction.json missing"],
            extractor=TOOLCHAIN_EXTRACTOR,
            complete=False,
            toolchain_available=True,
        )

    # Default: lake exe lpe_extract (fixture / partner convention).
    cmd = [lake, "exe", "lpe_extract", out_rel]
    try:
        # Do not insert a bare "--" token: Lean main would treat it as the out path.
        proc = _run_cmd(cmd, cwd=repository, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return LeanExtractionResult(
            errors=[f"lake exe lpe_extract failed: {exc}"],
            extractor=TOOLCHAIN_EXTRACTOR,
            complete=False,
            toolchain_available=True,
            notes=["lake present but lpe_extract invocation failed"],
        )

    return _result_from_exit(
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        artifact=artifact,
        provenance_note=provenance_note,
        via_executor=False,
    )


def ensure_toolchain_extraction(
    repository: Path,
    *,
    timeout_seconds: int | None = None,
    executor: LeanExecutor | None = None,
    max_output_bytes: int | None = None,
    environment_allowlist: list[str] | None = None,
) -> LeanExtractionResult | None:
    """After a build, prefer fresh toolchain JSON (force Lake extract when needed)."""
    return try_run_lake_extract(
        repository,
        timeout_seconds=timeout_seconds,
        force=False,
        executor=executor,
        max_output_bytes=max_output_bytes,
        environment_allowlist=environment_allowlist,
    )


def persist_toolchain_artifact(
    source_repository: Path,
    destination_repository: Path,
) -> Path | None:
    """Copy ``.lpe/lean-extraction.json`` from a build worktree to the primary repo.

    Worktree cleanup must not erase toolchain evidence needed by post-build
    axiom/impact findings and semantic providers that re-read the project path.
    """
    if source_repository.resolve() == destination_repository.resolve():
        artifact = extraction_artifact_path(source_repository)
        return artifact if artifact.is_file() else None

    src = extraction_artifact_path(source_repository)
    if not src.is_file():
        for rel in TOOLCHAIN_RESULT_CANDIDATES:
            candidate = source_repository / rel
            if candidate.is_file():
                src = candidate
                break
        else:
            return None

    dest = extraction_artifact_path(destination_repository)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest
