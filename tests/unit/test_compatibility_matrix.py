"""Compatibility matrix selection workflow + scale-gate honesty (§9.10–9.11)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs" / "closure" / "compatibility-matrix.yaml"
VALIDATE = ROOT / "scripts" / "validate_compatibility_matrix.py"
FIXTURE = ROOT / "tests" / "fixtures" / "lean_project"


def test_matrix_file_loads_and_fixture_supported() -> None:
    data = yaml.safe_load(MATRIX.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    projects = {p["id"]: p for p in data["projects"]}
    assert projects["fixture"]["status"] == "supported"
    assert (ROOT / projects["fixture"]["path"]).is_dir()
    assert data["unsupported_policy"]["code"] == "UNSUPPORTED_TOOLCHAIN"
    assert data["unsupported_policy"]["silent_regex_success"] == "forbidden"


def test_validate_compatibility_matrix_script_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(VALIDATE), "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["fixture_ready"] is True
    assert "fixture" in payload["projects_supported"]


def test_require_selected_fails_while_scale_pending() -> None:
    """Formal 0.2.0 scale completeness is not claimed while SHAs are pending."""
    proc = subprocess.run(
        [sys.executable, str(VALIDATE), "--require-selected"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2


def test_fixture_scale_gate_local() -> None:
    """In-repo fixture satisfies the fixture scale gate without network."""
    assert FIXTURE.is_dir()
    assert (FIXTURE / "lakefile.lean").is_file() or (FIXTURE / "lakefile.toml").is_file()
    from lpe.lean.extract_pair import extract_pair

    paired = extract_pair(
        base_path=FIXTURE,
        candidate_path=FIXTURE,
        base_tree_hash="fixture-base",
        candidate_tree_hash="fixture-head",
        dry_run=True,
    )
    assert paired.base_fingerprint.digest != paired.candidate_fingerprint.digest


@pytest.mark.slow
def test_external_scale_skips_without_pinned_sha_or_network() -> None:
    """External §9.11 projects skip unless a real SHA + network clone is configured."""
    data = yaml.safe_load(MATRIX.read_text(encoding="utf-8"))
    pending = [
        p
        for p in data["projects"]
        if p["id"] != "fixture"
        and str(p.get("commit_sha")) in {"pending_selection", "pending_live_validation"}
    ]
    if pending and not os.environ.get("LPE_SCALE_CLONE_ROOT"):
        pytest.skip(
            "external scale projects lack pinned SHAs / LPE_SCALE_CLONE_ROOT; "
            "not inventing network clones in default CI"
        )
    pytest.fail("scale clone configured but runner not implemented in this pass")
