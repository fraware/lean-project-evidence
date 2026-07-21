"""Fixture and successor suite loaders (CLOSURE-013 / CLOSURE-014)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from lpe.models import FixtureSuite, SuccessorSuite

SuiteKind = Literal["examples", "counterexamples", "downstream"]


def contract_tests_root(project_path: Path) -> Path:
    return project_path / ".lean-project-contract" / "tests"


def _manifest_candidates(directory: Path, *, kind: SuiteKind) -> list[Path]:
    """Prefer explicit suite manifests over directory heuristics."""
    names = (
        f"{kind}.suite.yaml",
        f"{kind}.suite.yml",
        "suite.yaml",
        "suite.yml",
        "manifest.yaml",
        "manifest.yml",
    )
    found: list[Path] = []
    for name in names:
        path = directory / name
        if path.is_file():
            found.append(path)
    # Also accept any *.suite.yaml in the directory.
    for path in sorted(directory.glob("*.suite.yaml")) + sorted(directory.glob("*.suite.yml")):
        if path not in found:
            found.append(path)
    return found


def load_fixture_suite(
    project_path: Path,
    *,
    kind: Literal["examples", "counterexamples"],
) -> tuple[FixtureSuite | None, dict[str, Any]]:
    """Load a fixture suite manifest.

    Returns ``(suite, report)``. Missing/invalid manifests yield ``suite=None``
    with a fail-closed report (never invent a PASS suite from directory presence).
    """
    directory = contract_tests_root(project_path) / kind
    report: dict[str, Any] = {
        "kind": kind,
        "directory": str(directory),
        "attempted": True,
        "manifest_path": None,
        "error": None,
    }
    if not directory.is_dir():
        report["error"] = "directory_missing"
        return None, report

    candidates = _manifest_candidates(directory, kind=kind)
    if not candidates:
        report["error"] = "manifest_missing"
        report["note"] = (
            "Directory heuristics are not acceptance evidence; provide "
            f"{kind}.suite.yaml (CLOSURE-013)"
        )
        return None, report

    path = candidates[0]
    report["manifest_path"] = str(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        report["error"] = f"manifest_unreadable:{exc}"
        return None, report
    if not isinstance(raw, dict):
        report["error"] = "manifest_not_object"
        return None, report

    raw.setdefault("suite_kind", kind)
    try:
        suite = FixtureSuite.model_validate(raw)
    except ValidationError as exc:
        report["error"] = f"manifest_invalid:{exc.error_count()}"
        report["validation_errors"] = exc.errors()
        return None, report

    if suite.suite_kind != kind:
        report["error"] = f"suite_kind_mismatch:{suite.suite_kind}"
        return None, report
    return suite, report


def load_successor_suite(project_path: Path) -> tuple[SuccessorSuite | None, dict[str, Any]]:
    """Load downstream successor suite under ``tests/downstream/``."""
    directory = contract_tests_root(project_path) / "downstream"
    report: dict[str, Any] = {
        "kind": "downstream",
        "directory": str(directory),
        "attempted": True,
        "manifest_path": None,
        "error": None,
    }
    if not directory.is_dir():
        report["error"] = "directory_missing"
        return None, report

    candidates = _manifest_candidates(directory, kind="downstream")
    if not candidates:
        report["error"] = "manifest_missing"
        return None, report

    path = candidates[0]
    report["manifest_path"] = str(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        report["error"] = f"manifest_unreadable:{exc}"
        return None, report
    if not isinstance(raw, dict):
        report["error"] = "manifest_not_object"
        return None, report

    try:
        suite = SuccessorSuite.model_validate(raw)
    except ValidationError as exc:
        report["error"] = f"manifest_invalid:{exc.error_count()}"
        report["validation_errors"] = exc.errors()
        return None, report
    return suite, report
