"""M3 fixture-excellence honesty: stub never PASS; FQN ambiguity; freshness."""

from __future__ import annotations

from pathlib import Path

from lpe.evidence.compiler import compile_evidence
from lpe.lean.extractor import (
    AdaptiveLeanExtractor,
    LeanExtractionResult,
    artifact_covers_lean_sources,
    list_lean_source_modules,
    resolve_changed_names_detailed,
)
from lpe.models import (
    CandidateDescriptor,
    ChangedDeclaration,
    FindingStatus,
    GeneratorProvenance,
)


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "lean_project"


def test_regex_stub_impact_and_axioms_never_pass(example_project: Path) -> None:
    candidate = CandidateDescriptor(
        candidate_id="cand-stub-honesty",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+def helper : Nat := 1\n",
        claimed_intent="stub",
        changed_paths=["Core.lean"],
        changed_declarations=[
            ChangedDeclaration(
                name="helper",
                kind="definition",
                path="Core.lean",
                signature_changed=True,
            )
        ],
        generator=GeneratorProvenance(generator_type="test", name="t", version="0"),
    )
    packet = compile_evidence(example_project, candidate, skip_build=True)
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    impact = next(f for f in packet.findings if f.check_id == "lean.impact_cone")
    assert axiom.status is not FindingStatus.PASS
    assert impact.status is not FindingStatus.PASS


def test_ambiguous_short_name_surfaces_warning() -> None:
    extraction = AdaptiveLeanExtractor()._regex.extract_repository(FIXTURE)
    decls = [
        ChangedDeclaration(
            name="twin", kind="definition", path="", signature_changed=True
        )
    ]
    _resolved, warnings = resolve_changed_names_detailed(decls, extraction)
    assert any("ambiguous" in w for w in warnings)


def test_list_lean_source_modules_covers_fixture_graph() -> None:
    modules = list_lean_source_modules(FIXTURE)
    assert "LpeFixture.LibA" in modules
    assert "LpeFixture.OpaqueLimits" in modules
    assert "LpeFixture.AmbiguousA" in modules


def test_stale_artifact_refuses_complete() -> None:
    result = LeanExtractionResult(
        declarations=[],
        extractor="lean.toolchain",
        complete=True,
        extraction_schema_version="1.1",
    )
    covers, missing = artifact_covers_lean_sources(result, FIXTURE)
    assert covers is False
    assert missing
