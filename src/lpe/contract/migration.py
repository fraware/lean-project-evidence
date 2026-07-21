"""Contract schema_version detection and bump-path documentation (AUDIT-026)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from lpe.contract.loader import contract_directory
from lpe.models import (
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    validate_supported_schema_version,
)

CONTRACT_FILES = (
    "project.yaml",
    "terminology.yaml",
    "obligations.yaml",
    "policies.yaml",
    "review.yaml",
)

BUMP_PATH = (
    "See docs/18_CONTRACT_MIGRATION.md: bump SCHEMA_VERSION and "
    "SUPPORTED_SCHEMA_VERSIONS together, export schemas, migrate examples, "
    "then re-run pytest / lpe contract schema-check."
)

# Versioned rewrite handlers: (from_version, to_version) -> mutates raw dict in place.
# Register field transformers here when adding the next supported minor.
MigrationRewriter = Callable[[dict[str, Any], str, str], None]
MIGRATION_REWRITERS: dict[tuple[str, str], MigrationRewriter] = {}


def _rewrite_schema_version_field(raw: dict[str, Any], _from_version: str, to_version: str) -> None:
    """Default productized rewrite: set schema_version only (identity fields)."""
    raw["schema_version"] = to_version


def register_migration_rewriter(
    from_version: str,
    to_version: str,
    rewriter: MigrationRewriter,
) -> None:
    """Register a field-level rewriter for a supported version pair."""
    MIGRATION_REWRITERS[(from_version, to_version)] = rewriter


def check_contract_schema_versions(project_path: Path) -> dict[str, Any]:
    """Scan contract YAML files; refuse unknown ``schema_version`` values.

    Returns a report of detected versions. Does not mutate files — migration
    remains a documented bump (see ``docs/18_CONTRACT_MIGRATION.md``).
    """
    directory = contract_directory(project_path.resolve())
    versions: dict[str, str] = {}
    for filename in CONTRACT_FILES:
        path = directory / filename
        if not path.is_file():
            raise ValueError(f"missing contract file: {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"invalid contract YAML object in {path}")
        version = raw.get("schema_version")
        if not isinstance(version, str):
            raise ValueError(f"missing or non-string schema_version in {path}")
        try:
            validate_supported_schema_version(version)
        except ValueError as exc:
            supported = ", ".join(sorted(SUPPORTED_SCHEMA_VERSIONS))
            raise ValueError(
                f"unsupported schema_version {version!r} in {path.name}; "
                f"supported: {supported}. "
                "Bump path: update SCHEMA_VERSION + SUPPORTED_SCHEMA_VERSIONS in "
                "src/lpe/models.py, export schemas, migrate examples "
                "(docs/18_CONTRACT_MIGRATION.md)."
            ) from exc
        versions[filename] = version
    return {"directory": str(directory), "versions": versions}


def dry_run_contract_migration(
    project_path: Path,
    *,
    target_version: str | None = None,
) -> dict[str, Any]:
    """Plan a schema_version rewrite without mutating any files.

    - If ``target_version`` is unsupported → ``would_refuse`` (fail-closed).
    - If every contract file already matches the target → ``no_op``.
    - Otherwise → ``would_rewrite`` listing files that would change.

    Never writes YAML. Real migration still requires listing the version in
    ``SUPPORTED_SCHEMA_VERSIONS`` and following ``docs/18_CONTRACT_MIGRATION.md``.
    """
    target = (target_version or SCHEMA_VERSION).strip()
    if not target:
        raise ValueError("target_version must be non-empty")

    directory = contract_directory(project_path.resolve())
    current: dict[str, str] = {}
    for filename in CONTRACT_FILES:
        path = directory / filename
        if not path.is_file():
            raise ValueError(f"missing contract file: {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"invalid contract YAML object in {path}")
        version = raw.get("schema_version")
        if not isinstance(version, str):
            raise ValueError(f"missing or non-string schema_version in {path}")
        current[filename] = version

    supported = sorted(SUPPORTED_SCHEMA_VERSIONS)
    files_to_rewrite = [name for name, ver in current.items() if ver != target]

    if target not in SUPPORTED_SCHEMA_VERSIONS:
        return {
            "ok": False,
            "action": "would_refuse",
            "mutated": False,
            "directory": str(directory),
            "current_versions": current,
            "target_version": target,
            "files_to_rewrite": files_to_rewrite,
            "supported": supported,
            "bump_path": BUMP_PATH,
            "message": (
                f"target schema_version {target!r} is not in "
                f"SUPPORTED_SCHEMA_VERSIONS ({', '.join(supported)}); "
                "refuse until the bump path is completed"
            ),
        }

    if not files_to_rewrite:
        return {
            "ok": True,
            "action": "no_op",
            "mutated": False,
            "directory": str(directory),
            "current_versions": current,
            "target_version": target,
            "files_to_rewrite": [],
            "supported": supported,
            "bump_path": BUMP_PATH,
            "message": f"all contract files already at schema_version {target}",
        }

    return {
        "ok": True,
        "action": "would_rewrite",
        "mutated": False,
        "directory": str(directory),
        "current_versions": current,
        "target_version": target,
        "files_to_rewrite": files_to_rewrite,
        "supported": supported,
        "bump_path": BUMP_PATH,
        "message": (
            f"dry-run only: would set schema_version={target} on "
            f"{len(files_to_rewrite)} file(s); no files written"
        ),
    }


def apply_contract_migration(
    project_path: Path,
    *,
    target_version: str | None = None,
    write: bool = False,
) -> dict[str, Any]:
    """Apply a versioned schema rewrite when ``write=True``.

    Refuse-unknown: unsupported targets never write. When writing, uses a
    registered ``MIGRATION_REWRITERS`` pair if present; otherwise the default
    schema_version field rewrite for any supported→supported bump.
    """
    plan = dry_run_contract_migration(project_path, target_version=target_version)
    if not write:
        return {**plan, "written": False, "written_files": []}
    if not plan.get("ok") or plan.get("action") == "would_refuse":
        return {**plan, "written": False, "written_files": []}
    if plan.get("action") == "no_op":
        return {
            **plan,
            "written": False,
            "written_files": [],
            "message": plan["message"],
        }

    directory = Path(plan["directory"])
    target = str(plan["target_version"])
    written: list[str] = []
    for filename in plan["files_to_rewrite"]:
        path = directory / filename
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"invalid contract YAML object in {path}")
        from_version = str(raw.get("schema_version") or "")
        rewriter = MIGRATION_REWRITERS.get((from_version, target))
        if rewriter is None:
            rewriter = _rewrite_schema_version_field
        rewriter(raw, from_version, target)
        path.write_text(
            yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        written.append(filename)

    return {
        **plan,
        "action": "rewrote",
        "mutated": True,
        "written": True,
        "written_files": written,
        "message": (
            f"wrote schema_version={target} on {len(written)} file(s); "
            "re-run lpe contract validate / schema-check"
        ),
    }
