#!/usr/bin/env python3
"""Validate and summarize the Lean compatibility matrix (spec 9.10-9.11).

Exit codes:
  0 — schema OK; reports selection status honestly
  1 — matrix file missing / invalid YAML structure
  2 — --require-selected and any required scale gate still pending_selection

Usage:
  python scripts/validate_compatibility_matrix.py
  python scripts/validate_compatibility_matrix.py --require-selected
  python scripts/validate_compatibility_matrix.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REQUIRED_TOP = ("schema_version", "toolchains", "projects", "scale_gates", "unsupported_policy")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_matrix(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("matrix root must be a mapping")
    for key in REQUIRED_TOP:
        if key not in data:
            raise ValueError(f"missing top-level key: {key}")
    return data


def summarize(matrix: dict[str, Any]) -> dict[str, Any]:
    projects = list(matrix.get("projects") or [])
    toolchains = list(matrix.get("toolchains") or [])
    gates = list(matrix.get("scale_gates") or [])
    by_id = {p.get("id"): p for p in projects if isinstance(p, dict)}

    selected: list[str] = []
    pending: list[str] = []
    supported: list[str] = []
    for proj in projects:
        if not isinstance(proj, dict):
            continue
        pid = str(proj.get("id"))
        status = str(proj.get("status", ""))
        sha = str(proj.get("commit_sha", ""))
        if status == "supported":
            supported.append(pid)
            selected.append(pid)
        elif status in {"selected", "selected_candidate", "candidate"}:
            selected.append(pid)
            if sha in {"", "pending_selection", "pending_live_validation"}:
                pending.append(pid)
        elif status == "pending_selection":
            pending.append(pid)

    incomplete_gates: list[str] = []
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        if str(gate.get("status")) == "satisfied_by_fixture":
            continue
        ref = gate.get("project_ref")
        proj = by_id.get(ref) if ref else None
        if proj is None:
            incomplete_gates.append(str(gate.get("id") or ref))
            continue
        sha = str(proj.get("commit_sha", ""))
        if (
            str(proj.get("status")) == "pending_selection"
            or sha in {"", "pending_selection", "pending_live_validation"}
            or str(gate.get("status")) == "pending_live_validation"
        ):
            incomplete_gates.append(str(gate.get("id") or ref))

    tc_pending = [
        str(t.get("id"))
        for t in toolchains
        if isinstance(t, dict)
        and str(t.get("status")) in {"pending_selection", "candidate"}
        and str((t.get("project") or {}).get("commit_sha", "pending_live_validation"))
        in {"", "pending_selection", "pending_live_validation"}
    ]

    return {
        "status": matrix.get("status"),
        "schema_version": matrix.get("schema_version"),
        "projects_supported": supported,
        "projects_selected": selected,
        "projects_pending": pending,
        "toolchains_pending": tc_pending,
        "incomplete_scale_gates": incomplete_gates,
        "fixture_ready": "fixture" in supported,
        "release_0_2_0_scale_complete": len(incomplete_gates) == 0 and not tc_pending,
        "unsupported_policy": matrix.get("unsupported_policy"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Matrix YAML (default: docs/closure/compatibility-matrix.yaml)",
    )
    parser.add_argument(
        "--require-selected",
        action="store_true",
        help="Fail if any 0.2.0 scale gate project is still pending_selection",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args(argv)
    path = args.path or (_repo_root() / "docs" / "closure" / "compatibility-matrix.yaml")
    if not path.is_file():
        print(f"missing matrix: {path}", file=sys.stderr)
        return 1
    try:
        matrix = load_matrix(path)
        summary = summarize(matrix)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"invalid matrix: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"compatibility matrix: {path}")
        print(f"  matrix_status: {summary['status']}")
        print(f"  fixture_ready: {summary['fixture_ready']}")
        print(f"  supported: {summary['projects_supported']}")
        print(f"  pending: {summary['projects_pending']}")
        print(f"  incomplete_scale_gates: {summary['incomplete_scale_gates']}")
        print(f"  toolchains_pending: {summary['toolchains_pending']}")
        print(f"  release_0_2_0_scale_complete: {summary['release_0_2_0_scale_complete']}")

    if args.require_selected and not summary["release_0_2_0_scale_complete"]:
        print(
            "FAIL: --require-selected but scale gates / toolchains still pending",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
