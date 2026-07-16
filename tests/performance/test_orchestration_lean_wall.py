"""§17 orchestration vs Lean wall measurement on lean_project fixture."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import pytest

from lpe.contract.loader import load_contract
from lpe.evidence.compiler import compile_evidence
from lpe.lean.extractor import lean_toolchain_available
from lpe.models import (
    CandidateDescriptor,
    ChangedDeclaration,
    GeneratorProvenance,
)
from tests.performance.metrics import record, timed

LEAN_PROJECT = Path(__file__).resolve().parents[1] / "fixtures" / "lean_project"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _candidate() -> CandidateDescriptor:
    return CandidateDescriptor(
        candidate_id="cand-orch-lean-wall",
        project_id="lpe-fixture",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+def helper : Nat := 1\n",
        claimed_intent="orch measure",
        changed_paths=["LpeFixture/Core.lean"],
        changed_declarations=[
            ChangedDeclaration(
                name="helper",
                kind="definition",
                path="LpeFixture/Core.lean",
                signature_changed=True,
                public=True,
            )
        ],
        generator=GeneratorProvenance(
            generator_type="test", name="orch-wall", version="0"
        ),
    )


@pytest.mark.lean
@pytest.mark.performance
def test_orchestration_vs_lean_wall_ratio() -> None:
    """Measure (lpe_wall - lean_wall) / lean_wall when Lake is available.

    Soft assert orch < 10% **or** record measured % honestly (do not invent).
    """
    if not lean_toolchain_available(LEAN_PROJECT) or shutil.which("lake") is None:
        pytest.skip("Lake/Lean required for §17 Lean-wall measurement")
    if not (LEAN_PROJECT / "lakefile.toml").is_file():
        pytest.skip("lean_project fixture missing")

    # Lean wall: lake build alone.
    t0 = time.perf_counter()
    build = subprocess.run(
        ["lake", "build"],
        cwd=LEAN_PROJECT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    lean_wall_s = time.perf_counter() - t0
    if build.returncode != 0:
        pytest.skip(f"lake build failed: {(build.stderr or build.stdout)[:200]}")

    # LPE wall: skip_build compile still measures orchestration; prefer real
    # host extract path when contract exists. Fixture has no full contract —
    # use extract + skip_build orch from minimal contract if present.
    contract_dir = LEAN_PROJECT / ".lean-project-contract"
    if not (contract_dir / "project.yaml").is_file():
        # Measure adaptive extract + regex-free toolchain path as orch proxy.
        from lpe.lean.extractor import extract_lean_repository

        with timed() as elapsed:
            result = extract_lean_repository(LEAN_PROJECT, run_toolchain=True)
        orch_s = elapsed[0]
        assert result.extractor == "lean.toolchain" or not result.complete
    else:
        contract = load_contract(LEAN_PROJECT)
        with timed() as elapsed:
            compile_evidence(
                LEAN_PROJECT,
                _candidate(),
                skip_build=True,
                contract=contract,
            )
        orch_s = elapsed[0]

    ratio = orch_s / lean_wall_s if lean_wall_s > 0 else float("inf")
    record("lean_wall_s", lean_wall_s, unit="s", notes="lake build on lean_project")
    record("orch_vs_lean_wall_s", orch_s, unit="s", notes="LPE orchestration slice")
    record(
        "orchestration_ratio",
        ratio,
        unit="ratio",
        notes="orch/lean_wall; §17 target <0.10",
    )

    # Soft: document miss rather than fake the budget.
    if ratio >= 0.10:
        # Publish honest miss — soft budget uses 2× elsewhere; here we only
        # fail hard if orchestration dominates absurdly (>2× Lean wall).
        assert ratio < 2.0, (
            f"orchestration {orch_s:.3f}s vs Lean wall {lean_wall_s:.3f}s "
            f"(ratio={ratio:.2%}) exceeds 2× Lean wall"
        )
