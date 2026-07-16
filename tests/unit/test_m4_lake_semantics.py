"""M4 Lake-backed semantic providers on lean_project fixtures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lpe.lean.extractor import lean_toolchain_available
from lpe.models import (
    CandidateDescriptor,
    FindingStatus,
    GeneratorProvenance,
)
from lpe.providers.semantic import (
    CounterexampleProvider,
    ExampleRunnerProvider,
    parse_signature_structure,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "lean_project"


def _candidate() -> CandidateDescriptor:
    return CandidateDescriptor(
        candidate_id="cand-m4-lake",
        project_id="lpe-fixture",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+--\n",
        claimed_intent="m4",
        changed_paths=["LpeFixture/Core.lean"],
        changed_declarations=[],
        generator=GeneratorProvenance(generator_type="test", name="m4", version="0"),
    )


@pytest.mark.lean
def test_example_runner_lake_pass_on_fixture() -> None:
    if not lean_toolchain_available(FIXTURE):
        pytest.skip("Lake required")
    findings = ExampleRunnerProvider().collect(FIXTURE, MagicMock(), _candidate())
    assert findings[0].status is FindingStatus.PASS
    assert findings[0].details.get("lake_attempted") is True


@pytest.mark.lean
def test_counterexample_lake_fail_on_fixture() -> None:
    if not lean_toolchain_available(FIXTURE):
        pytest.skip("Lake required")
    findings = CounterexampleProvider().collect(FIXTURE, MagicMock(), _candidate())
    assert findings[0].status is FindingStatus.FAIL
    assert findings[0].details.get("lake_attempted") is True


def test_parse_signature_structure_fields() -> None:
    parsed = parse_signature_structure(
        "theorem corePositive (n : Nat) : n ≥ 0 → True"
    )
    assert parsed["decl_name"] == "corePositive"
    assert parsed["conclusion"] is not None
