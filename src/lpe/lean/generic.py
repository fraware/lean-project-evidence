"""Generic injected Lean extractor (CLOSURE-006 / spec §9.3-9.4).

Discovers a Lake workspace, builds an ephemeral injector package that depends
on the target by local path, compiles with the *target* lean-toolchain inside
the selected sandbox, and returns protocol-validated JSON.

Never modifies permanent target-repository files.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lpe.hashing import sha256_file, sha256_text, sha256_value
from lpe.lean.models import (
    EXTRACTION_PROTOCOL_VERSION,
    GENERIC_EXTRACTOR_ID,
    MODULE_DISCOVERY_AMBIGUOUS_CODE,
    MODULE_DISCOVERY_UNKNOWN_CODE,
    UNSUPPORTED_TOOLCHAIN_CODE,
    ExtractionCompleteness,
    ExtractionError,
    LeanExtractionResultV2,
    empty_extraction_v2,
)

if TYPE_CHECKING:
    from lpe.execution.protocol import LeanExecutor

# Default supported prefixes; compatibility-matrix.yaml may extend at runtime.
DEFAULT_SUPPORTED_TOOLCHAIN_PREFIXES: tuple[str, ...] = (
    "leanprover/lean4:v4.14.",
    "leanprover/lean4:v4.14.0",
)

SKIP_DIR_PARTS = frozenset(
    {
        ".git",
        ".lake",
        ".lean-project-contract",
        ".lpe",
        "lake-packages",
        "node_modules",
    }
)

_NAME_RE = re.compile(r'^name\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_LEAN_LIB_RE = re.compile(
    r"\[\[lean_lib\]\]\s*(?:[^\[]*?name\s*=\s*[\"']([^\"']+)[\"'])",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True)
class LakeWorkspaceInfo:
    package_name: str
    library_roots: tuple[str, ...]
    source_roots: tuple[str, ...]
    lakefile_kind: str  # "toml" | "lean"
    discovery: str  # "lake_metadata" | "filesystem"


@dataclass(frozen=True)
class ModuleDiscovery:
    modules: tuple[str, ...]
    roots: tuple[str, ...]
    method: str
    error: ExtractionError | None = None


def bundled_extractor_root() -> Path:
    """Resolve shipped LpeExtract sources (wheel package-data or repo ``lean/``)."""
    override = os.environ.get("LPE_EXTRACT_SOURCES", "").strip()
    if override:
        path = Path(override)
        if (path / "LpeExtract").is_dir() or (path / "Protocol.lean").is_file():
            return path.resolve()
    packaged = Path(__file__).resolve().parent / "bundled"
    if (packaged / "LpeExtract").is_dir():
        return packaged
    # Editable / monorepo: src/lpe/lean -> repo root / lean
    repo_lean = Path(__file__).resolve().parents[3] / "lean"
    if (repo_lean / "LpeExtract").is_dir():
        return repo_lean
    raise FileNotFoundError(
        "LpeExtract sources not found; expected src/lpe/lean/bundled or repo lean/"
    )


def read_toolchain_spec(repository: Path) -> str:
    path = repository / "lean-toolchain"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[0].strip()


def load_supported_toolchain_prefixes(
    matrix_path: Path | None = None,
) -> tuple[str, ...]:
    """Load supported toolchain prefixes from compatibility matrix when present."""
    candidates: list[Path] = []
    if matrix_path is not None:
        candidates.append(matrix_path)
    candidates.append(
        Path(__file__).resolve().parents[3] / "docs" / "closure" / "compatibility-matrix.yaml"
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            import yaml

            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        prefixes: list[str] = []
        for entry in data.get("toolchains") or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("status") == "pending_selection":
                continue
            for key in ("prefix", "spec", "id"):
                val = entry.get(key)
                if isinstance(val, str) and val.strip() and val.strip() != "pending_selection":
                    prefixes.append(val.strip())
                    break
            for p in entry.get("accepted_prefixes") or []:
                if isinstance(p, str) and p.strip() and p.strip() != "pending_selection":
                    prefixes.append(p.strip())
        if prefixes:
            return tuple(dict.fromkeys([*DEFAULT_SUPPORTED_TOOLCHAIN_PREFIXES, *prefixes]))
    return DEFAULT_SUPPORTED_TOOLCHAIN_PREFIXES


def toolchain_is_supported(
    toolchain_spec: str,
    *,
    prefixes: tuple[str, ...] | None = None,
) -> bool:
    spec = (toolchain_spec or "").strip()
    if not spec:
        return False
    allowed = prefixes or load_supported_toolchain_prefixes()
    return any(spec == p or spec.startswith(p) for p in allowed)


def snapshot_fingerprint_for(
    *,
    tree_hash: str,
    toolchain_spec: str,
    protocol_version: str = EXTRACTION_PROTOCOL_VERSION,
) -> str:
    return sha256_value(
        {
            "tree_hash": tree_hash,
            "toolchain_spec": toolchain_spec,
            "protocol_version": protocol_version,
        }
    )


def discover_lake_workspace(repository: Path) -> LakeWorkspaceInfo | ExtractionError:
    """Discover Lake package name and library roots from metadata."""
    repository = repository.resolve()
    toml = repository / "lakefile.toml"
    lean = repository / "lakefile.lean"
    if toml.is_file():
        text = toml.read_text(encoding="utf-8", errors="replace")
        name_match = _NAME_RE.search(text)
        package_name = name_match.group(1) if name_match else repository.name
        libs = tuple(_LEAN_LIB_RE.findall(text)) or (package_name,)
        return LakeWorkspaceInfo(
            package_name=package_name,
            library_roots=libs,
            source_roots=libs,
            lakefile_kind="toml",
            discovery="lake_metadata",
        )
    if lean.is_file():
        text = lean.read_text(encoding="utf-8", errors="replace")
        # Best-effort: package name from `package «name»` or `package name`
        pkg = re.search(r"package\s+«([^»]+)»", text) or re.search(
            r"package\s+([A-Za-z0-9_]+)", text
        )
        package_name = pkg.group(1) if pkg else repository.name
        libs = tuple(re.findall(r"lean_lib\s+«([^»]+)»", text)) or tuple(
            re.findall(r"lean_lib\s+([A-Za-z0-9_]+)", text)
        )
        if not libs:
            libs = (package_name,)
        return LakeWorkspaceInfo(
            package_name=package_name,
            library_roots=libs,
            source_roots=libs,
            lakefile_kind="lean",
            discovery="lake_metadata",
        )
    return ExtractionError(
        code=MODULE_DISCOVERY_UNKNOWN_CODE,
        message=f"no lakefile.toml or lakefile.lean under {repository}",
        actionable="Add a Lake lakefile or point LPE at a Lake project root",
    )


def _list_lean_modules_under(root: Path, *, rel_prefix: str = "") -> list[str]:
    modules: list[str] = []
    if not root.is_dir():
        return modules
    for path in sorted(root.rglob("*.lean")):
        if SKIP_DIR_PARTS.intersection(path.parts):
            continue
        if path.name in {"lakefile.lean"}:
            continue
        rel = path.relative_to(root)
        if rel_prefix:
            # root is already the source tree; module = prefix + relative
            parts = Path(rel_prefix).parts + rel.with_suffix("").parts
        else:
            parts = rel.with_suffix("").parts
        modules.append(".".join(parts))
    return modules


def discover_modules(repository: Path, info: LakeWorkspaceInfo) -> ModuleDiscovery:
    """Lake metadata first; filesystem fallback only when unambiguous (§9.4)."""
    repository = repository.resolve()
    modules: list[str] = []

    # Prefer roots matching library names as directories or root .lean files.
    for lib in info.library_roots:
        lib_dir = repository / lib.replace(".", "/")
        lib_file = repository / f"{lib.replace('.', '/')}.lean"
        if lib_file.is_file():
            modules.append(lib)
        if lib_dir.is_dir():
            modules.extend(_list_lean_modules_under(lib_dir, rel_prefix=lib))

    modules = list(dict.fromkeys(modules))
    if modules:
        return ModuleDiscovery(
            modules=tuple(modules),
            roots=info.library_roots,
            method="lake_metadata",
        )

    # Filesystem fallback: single unambiguous source root only.
    candidates: list[Path] = []
    for child in sorted(repository.iterdir()):
        if not child.is_dir() or child.name in SKIP_DIR_PARTS or child.name.startswith("."):
            continue
        if any(child.rglob("*.lean")):
            candidates.append(child)
    root_leans = [
        p for p in repository.glob("*.lean") if p.name not in {"lakefile.lean"} and p.is_file()
    ]
    if len(candidates) == 1 and not root_leans:
        only = candidates[0]
        mods = _list_lean_modules_under(only, rel_prefix=only.name)
        if mods:
            return ModuleDiscovery(
                modules=tuple(dict.fromkeys(mods)),
                roots=(only.name,),
                method="filesystem",
            )
    if len(candidates) == 0 and len(root_leans) == 1:
        mod = root_leans[0].stem
        return ModuleDiscovery(
            modules=(mod,),
            roots=(mod,),
            method="filesystem",
        )

    if len(candidates) > 1 or (candidates and root_leans):
        return ModuleDiscovery(
            modules=(),
            roots=(),
            method="ambiguous",
            error=ExtractionError(
                code=MODULE_DISCOVERY_AMBIGUOUS_CODE,
                message=(
                    "filesystem module discovery is ambiguous: "
                    f"dirs={[c.name for c in candidates]} "
                    f"root_leans={[p.name for p in root_leans]}"
                ),
                actionable=("Declare lean_lib roots in lakefile.toml so LPE can use Lake metadata"),
            ),
        )
    return ModuleDiscovery(
        modules=(),
        roots=(),
        method="unknown",
        error=ExtractionError(
            code=MODULE_DISCOVERY_UNKNOWN_CODE,
            message="no Lean modules discovered under project roots",
            actionable="Ensure the Lake library source tree contains .lean files",
        ),
    )


def _copy_extractor_sources(dest: Path) -> None:
    src_root = bundled_extractor_root()
    src_pkg = src_root / "LpeExtract"
    dest_pkg = dest / "LpeExtract"
    dest_pkg.mkdir(parents=True, exist_ok=True)
    for name in ("Protocol.lean", "Json.lean", "Modules.lean", "Environment.lean", "Main.lean"):
        shutil.copy2(src_pkg / name, dest_pkg / name)


def _write_ephemeral_lakefile(
    dest: Path,
    *,
    target_name: str,
    target_path: Path,
) -> None:
    # Use forward slashes for Lake on all platforms.
    path_lit = target_path.resolve().as_posix()
    content = f"""name = "LpeExtractDriver"
version = "0.1.0"
defaultTargets = ["lpe_extract"]

[[require]]
name = "{target_name}"
path = "{path_lit}"

[[lean_lib]]
name = "LpeExtract"

[[lean_exe]]
name = "lpe_extract"
root = "LpeExtract.Main"
supportInterpreter = true
"""
    (dest / "lakefile.toml").write_text(content, encoding="utf-8")


def _write_aggregator(dest: Path, modules: tuple[str, ...]) -> None:
    imports = "\n".join(f"import {m}" for m in modules)
    body = f"""/-
  Ephemeral import aggregator generated by LPE generic injection.
  Not written into the permanent target repository.
-/
{imports}
"""
    (dest / "LpeExtract" / "Aggregator.lean").write_text(body, encoding="utf-8")


def _normalize_protocol_payload(
    data: dict[str, Any],
    *,
    snapshot_fingerprint: str,
    toolchain_spec: str,
) -> LeanExtractionResultV2:
    """Validate/normalize Lean JSON; re-hash type_pretty to SHA-256 when needed."""
    data = dict(data)
    data.setdefault("schema_version", EXTRACTION_PROTOCOL_VERSION)
    data["snapshot_fingerprint"] = snapshot_fingerprint
    if toolchain_spec:
        data["toolchain_spec"] = toolchain_spec
    data.setdefault("extractor", GENERIC_EXTRACTOR_ID)
    # Normalize Lean hash strings to SHA-256 of type_pretty when not already hex.
    for item in data.get("declarations") or []:
        if not isinstance(item, dict):
            continue
        pretty = str(item.get("type_pretty") or "")
        existing = str(item.get("type_expr_hash") or "")
        hex_ok = len(existing) == 64 and all(c in "0123456789abcdef" for c in existing.lower())
        if pretty and (not existing or not hex_ok):
            item["type_expr_hash"] = sha256_text(pretty)
        value = item.get("value_expr_hash")
        if (
            value is not None
            and value != ""
            and (
                len(str(value)) != 64
                or any(c not in "0123456789abcdef" for c in str(value).lower())
            )
        ):
            # Value hash from Lean is not SHA-256; keep as opaque string only if hex.
            item["value_expr_hash"] = None
    return LeanExtractionResultV2.model_validate(data)


def run_generic_extract(
    repository: Path,
    *,
    snapshot_fingerprint: str,
    executor: LeanExecutor | None = None,
    tree_hash: str | None = None,
    timeout_seconds: int = 600,
    max_output_bytes: int = 4_000_000,
    environment_allowlist: list[str] | None = None,
    dry_run: bool = False,
    supported_prefixes: tuple[str, ...] | None = None,
) -> LeanExtractionResultV2:
    """Inject LpeExtract against ``repository`` and return protocol v2 JSON.

    When ``dry_run`` is True, prepare the ephemeral workspace and return a
    result describing discovery without invoking Lean/Lake.
    """
    repository = repository.resolve()
    toolchain_spec = read_toolchain_spec(repository)
    if tree_hash:
        snapshot_fingerprint = snapshot_fingerprint_for(
            tree_hash=tree_hash, toolchain_spec=toolchain_spec
        )

    if not toolchain_is_supported(toolchain_spec, prefixes=supported_prefixes):
        return empty_extraction_v2(
            snapshot_fingerprint=snapshot_fingerprint,
            toolchain_spec=toolchain_spec,
            errors=[
                ExtractionError(
                    code=UNSUPPORTED_TOOLCHAIN_CODE,
                    message=(
                        f"toolchain {toolchain_spec!r} is outside the supported "
                        "compatibility matrix"
                    ),
                    actionable=(
                        "Use a supported Lean 4.14.x (or matrix-listed) toolchain; "
                        "regex-stub must not be treated as elaborator success"
                    ),
                )
            ],
            notes=["generic injection refused: UNSUPPORTED_TOOLCHAIN"],
        )

    ws = discover_lake_workspace(repository)
    if isinstance(ws, ExtractionError):
        return empty_extraction_v2(
            snapshot_fingerprint=snapshot_fingerprint,
            toolchain_spec=toolchain_spec,
            errors=[ws],
        )

    discovery = discover_modules(repository, ws)
    if discovery.error is not None:
        return empty_extraction_v2(
            snapshot_fingerprint=snapshot_fingerprint,
            toolchain_spec=toolchain_spec,
            errors=[discovery.error],
            notes=[f"module discovery method={discovery.method}"],
        )
    if not discovery.modules:
        return empty_extraction_v2(
            snapshot_fingerprint=snapshot_fingerprint,
            toolchain_spec=toolchain_spec,
            errors=[
                ExtractionError(
                    code=MODULE_DISCOVERY_UNKNOWN_CODE,
                    message="module discovery returned no modules",
                    actionable="Check Lake lean_lib source layout",
                )
            ],
        )

    if dry_run:
        return LeanExtractionResultV2(
            snapshot_fingerprint=snapshot_fingerprint,
            toolchain_spec=toolchain_spec,
            extractor=GENERIC_EXTRACTOR_ID,
            notes=[
                "dry_run: ephemeral injector not executed",
                f"package={ws.package_name}",
                f"discovery={discovery.method}",
                f"modules={len(discovery.modules)}",
            ],
            completeness=ExtractionCompleteness(
                known_limitations=["dry_run — environment not loaded"],
            ),
        )

    allowlist = list(
        environment_allowlist or ["PATH", "HOME", "USER", "TMPDIR", "SYSTEMROOT", "LEAN_PATH"]
    )
    ephemeral = Path(tempfile.mkdtemp(prefix="lpe-extract-"))
    try:
        _copy_extractor_sources(ephemeral)
        (ephemeral / "lean-toolchain").write_text(toolchain_spec + "\n", encoding="utf-8")
        _write_ephemeral_lakefile(ephemeral, target_name=ws.package_name, target_path=repository)
        # Prefer importing library roots (faster); Aggregator lists all modules.
        _write_aggregator(ephemeral, discovery.modules)
        out_rel = ".lpe/lean-extraction-v2.json"
        out_path = ephemeral / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)

        roots_arg = ",".join(discovery.roots)
        modules_arg = ",".join(discovery.modules[:64])  # bound argv size
        # Build then run extract inside the same cwd (ephemeral package).
        build_cmd = ["lake", "build"]
        extract_cmd = [
            "lake",
            "exe",
            "lpe_extract",
            out_rel,
            roots_arg,
            snapshot_fingerprint,
            toolchain_spec,
            modules_arg,
        ]

        if executor is not None:
            from lpe.execution.allowlist import validate_build_command

            build_cmd = validate_build_command(build_cmd)
            extract_cmd = validate_build_command(extract_cmd)
            build_result = executor.verify_build(
                repository=ephemeral,
                command=build_cmd,
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
                environment_allowlist=allowlist,
            )
            if build_result.exit_code != 0:
                err = (build_result.stderr or build_result.stdout or "")[:800]
                return empty_extraction_v2(
                    snapshot_fingerprint=snapshot_fingerprint,
                    toolchain_spec=toolchain_spec,
                    errors=[
                        ExtractionError(
                            code="GENERIC_EXTRACT_BUILD_FAILED",
                            message=f"ephemeral lake build failed: {err}",
                            actionable="Inspect Lake/Lean errors in the sandboxed build log",
                        )
                    ],
                    notes=["generic injection build failed"],
                )
            extract_result = executor.verify_build(
                repository=ephemeral,
                command=extract_cmd,
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
                environment_allowlist=allowlist,
            )
            if extract_result.exit_code != 0:
                err = (extract_result.stderr or extract_result.stdout or "")[:800]
                return empty_extraction_v2(
                    snapshot_fingerprint=snapshot_fingerprint,
                    toolchain_spec=toolchain_spec,
                    errors=[
                        ExtractionError(
                            code="GENERIC_EXTRACT_RUN_FAILED",
                            message=(f"lpe_extract exit {extract_result.exit_code}: {err}"),
                            actionable=(
                                "Ensure target modules elaborate under the project toolchain"
                            ),
                        )
                    ],
                )
        else:
            lake = shutil.which("lake")
            if lake is None:
                return empty_extraction_v2(
                    snapshot_fingerprint=snapshot_fingerprint,
                    toolchain_spec=toolchain_spec,
                    errors=[
                        ExtractionError(
                            code="LAKE_UNAVAILABLE",
                            message="lake not on PATH and no executor provided",
                            actionable="Install elan/Lake or pass a sandbox executor",
                        )
                    ],
                )
            import subprocess

            build_proc = subprocess.run(
                [lake, "build"],
                cwd=ephemeral,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            if build_proc.returncode != 0:
                err = (build_proc.stderr or build_proc.stdout or "")[:800]
                return empty_extraction_v2(
                    snapshot_fingerprint=snapshot_fingerprint,
                    toolchain_spec=toolchain_spec,
                    errors=[
                        ExtractionError(
                            code="GENERIC_EXTRACT_BUILD_FAILED",
                            message=f"ephemeral lake build failed: {err}",
                            actionable="Inspect host Lake build errors",
                        )
                    ],
                )
            proc = subprocess.run(
                [lake, *extract_cmd[1:]],
                cwd=ephemeral,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "")[:800]
                return empty_extraction_v2(
                    snapshot_fingerprint=snapshot_fingerprint,
                    toolchain_spec=toolchain_spec,
                    errors=[
                        ExtractionError(
                            code="GENERIC_EXTRACT_RUN_FAILED",
                            message=f"lpe_extract exit {proc.returncode}: {err}",
                            actionable="Ensure target modules elaborate",
                        )
                    ],
                )

        if not out_path.is_file():
            return empty_extraction_v2(
                snapshot_fingerprint=snapshot_fingerprint,
                toolchain_spec=toolchain_spec,
                errors=[
                    ExtractionError(
                        code="GENERIC_EXTRACT_MISSING_ARTIFACT",
                        message="lpe_extract exited 0 but JSON artifact missing",
                        actionable="Check extractor Main.lean write path",
                    )
                ],
            )
        try:
            raw = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return empty_extraction_v2(
                snapshot_fingerprint=snapshot_fingerprint,
                toolchain_spec=toolchain_spec,
                errors=[
                    ExtractionError(
                        code="GENERIC_EXTRACT_INVALID_JSON",
                        message=f"invalid extraction JSON: {exc}",
                        actionable="Fix extractor JSON emission",
                    )
                ],
            )
        if not isinstance(raw, dict):
            return empty_extraction_v2(
                snapshot_fingerprint=snapshot_fingerprint,
                toolchain_spec=toolchain_spec,
                errors=[
                    ExtractionError(
                        code="GENERIC_EXTRACT_INVALID_JSON",
                        message="extraction JSON root must be an object",
                    )
                ],
            )
        extraction = _normalize_protocol_payload(
            raw,
            snapshot_fingerprint=snapshot_fingerprint,
            toolchain_spec=toolchain_spec,
        )
        notes = list(extraction.notes)
        notes.append(f"module_discovery={discovery.method}")
        notes.append(f"ephemeral_injector sha256_toolchain={sha256_text(toolchain_spec)}")
        if (repository / "lean-toolchain").is_file():
            notes.append(f"target_toolchain_file={sha256_file(repository / 'lean-toolchain')}")
        return extraction.model_copy(update={"notes": list(dict.fromkeys(notes))})
    finally:
        shutil.rmtree(ephemeral, ignore_errors=True)


def try_generic_extract(
    repository: Path,
    *,
    snapshot_fingerprint: str = "unknown",
    executor: LeanExecutor | None = None,
    tree_hash: str | None = None,
    dry_run: bool = False,
) -> LeanExtractionResultV2 | None:
    """Run generic extract; return None only when Lake workspace is absent."""
    ws = discover_lake_workspace(repository)
    if isinstance(ws, ExtractionError) and ws.code == MODULE_DISCOVERY_UNKNOWN_CODE:
        if (
            not (repository / "lakefile.toml").is_file()
            and not (repository / "lakefile.lean").is_file()
        ):
            return None
    return run_generic_extract(
        repository,
        snapshot_fingerprint=snapshot_fingerprint,
        executor=executor,
        tree_hash=tree_hash,
        dry_run=dry_run,
    )
