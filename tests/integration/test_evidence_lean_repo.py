"""Week 2: Lean toolchain JSON ingest + regex-stub honesty (no Lake required)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from lpe.evidence.compiler import compile_evidence
from lpe.hashing import sha256_text
from lpe.lean.extractor import (
    REGEX_STUB_EXTRACTOR,
    TOOLCHAIN_EXTRACTOR,
    RegexLeanExtractor,
    build_dependency_graph,
    extract_lean_repository,
    impact_cone,
)
from lpe.models import CandidateDescriptor, FindingStatus, GeneratorProvenance, Recommendation


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "lean"
TOOLCHAIN_PROJECT = FIXTURES / "toolchain_project"


def _generator() -> GeneratorProvenance:
    return GeneratorProvenance(generator_type="test", name="week2-lean", version="0")


def _seed_example_with_toolchain(
    dest: Path, example_project: Path, *, extraction: dict | None = None
) -> Path:
    shutil.copytree(example_project, dest)
    lean_src = TOOLCHAIN_PROJECT / "Example" / "Public" / "Comparison.lean"
    target_lean = dest / "Example" / "Public" / "Comparison.lean"
    target_lean.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(lean_src, target_lean)
    lpe_dir = dest / ".lpe"
    lpe_dir.mkdir(parents=True, exist_ok=True)
    payload = extraction
    if payload is None:
        payload = json.loads(
            (TOOLCHAIN_PROJECT / ".lpe" / "lean-extraction.json").read_text(encoding="utf-8")
        )
    (lpe_dir / "lean-extraction.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest


def _candidate_for_comparison() -> CandidateDescriptor:
    return CandidateDescriptor(
        candidate_id="cand-toolchain-week2",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+def comparisonFunctor : Nat := 1\n",
        claimed_intent="toolchain fixture",
        changed_paths=["Example/Public/Comparison.lean"],
        changed_declarations=[
            {
                "name": "Example.Public.Comparison.comparisonFunctor",
                "kind": "definition",
                "path": "Example/Public/Comparison.lean",
                "signature_changed": True,
                "public": True,
            }
        ],
        generator=_generator(),
    )


def test_committed_toolchain_json_extracts_as_complete() -> None:
    result = extract_lean_repository(TOOLCHAIN_PROJECT)
    assert result.extractor == TOOLCHAIN_EXTRACTOR
    assert result.complete is True
    assert result.errors == []
    names = {d.name for d in result.declarations}
    assert "Example.Public.Comparison.comparisonFunctor" in names
    assert "Example.Public.Comparison.helper" in names


def test_removing_toolchain_json_falls_back_to_regex_stub(tmp_path: Path) -> None:
    dest = tmp_path / "regex-only"
    shutil.copytree(TOOLCHAIN_PROJECT, dest)
    (dest / ".lpe" / "lean-extraction.json").unlink()
    result = extract_lean_repository(dest)
    assert result.extractor == REGEX_STUB_EXTRACTOR
    assert result.complete is False


def test_compile_toolchain_json_allows_axiom_pass(example_project: Path, tmp_path: Path) -> None:
    project = _seed_example_with_toolchain(tmp_path / "proj", example_project)
    packet = compile_evidence(project, _candidate_for_comparison(), skip_build=True)
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is FindingStatus.PASS
    assert axiom.details.get("extractor") == TOOLCHAIN_EXTRACTOR

    impact = next(f for f in packet.findings if f.check_id == "lean.impact_cone")
    assert impact.status is FindingStatus.PASS
    assert impact.details.get("extractor") == TOOLCHAIN_EXTRACTOR
    assert impact.details.get("complete") is True
    assert "Example.Public.Comparison.helper" in impact.details.get("impact_cone", [])


def test_compile_regex_stub_never_axiom_pass(example_project: Path, tmp_path: Path) -> None:
    """Honesty: same Lean sources without toolchain JSON → axiom UNKNOWN, never PASS."""
    project = tmp_path / "proj"
    shutil.copytree(example_project, project)
    lean_src = TOOLCHAIN_PROJECT / "Example" / "Public" / "Comparison.lean"
    target = project / "Example" / "Public" / "Comparison.lean"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(lean_src, target)

    packet = compile_evidence(project, _candidate_for_comparison(), skip_build=True)
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is FindingStatus.UNKNOWN
    assert axiom.status is not FindingStatus.PASS
    assert packet.hard_gate_passed is False
    assert packet.recommendation is Recommendation.ESCALATE

    impact = next(f for f in packet.findings if f.check_id == "lean.impact_cone")
    assert impact.status is FindingStatus.UNKNOWN
    assert impact.details.get("extractor") == REGEX_STUB_EXTRACTOR


def test_toolchain_incomplete_flag_never_pass(example_project: Path, tmp_path: Path) -> None:
    incomplete = json.loads(
        (TOOLCHAIN_PROJECT / ".lpe" / "lean-extraction.json").read_text(encoding="utf-8")
    )
    incomplete["complete"] = False
    project = _seed_example_with_toolchain(
        tmp_path / "proj", example_project, extraction=incomplete
    )
    packet = compile_evidence(project, _candidate_for_comparison(), skip_build=True)
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is FindingStatus.UNKNOWN
    assert axiom.status is not FindingStatus.PASS
    impact = next(f for f in packet.findings if f.check_id == "lean.impact_cone")
    assert impact.status is FindingStatus.UNKNOWN
    assert impact.details.get("complete") is False


def test_toolchain_with_prohibited_axiom_fails(example_project: Path, tmp_path: Path) -> None:
    payload = {
        "declarations": [
            {
                "name": "Example.bad",
                "kind": "axiom",
                "path": "Example/Public/Comparison.lean",
                "line": 1,
                "signature": "axiom bad : False",
                "signature_hash": sha256_text("axiom bad : False"),
                "is_axiom": True,
            }
        ],
        "axioms_used": ["Definitely.Prohibited.Axiom"],
        "imports": [],
        "dependency_edges": [],
        "extractor": TOOLCHAIN_EXTRACTOR,
        "complete": True,
        "errors": [],
    }
    project = _seed_example_with_toolchain(tmp_path / "proj", example_project, extraction=payload)
    packet = compile_evidence(project, _candidate_for_comparison(), skip_build=True)
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is FindingStatus.FAIL
    assert packet.recommendation is Recommendation.REJECT


def test_impact_cone_expectations_json_hand_audited() -> None:
    """Expand AUDIT-012 coverage using committed expectations.json + GrandConsumer."""
    expectations = json.loads(
        (FIXTURES / "impact_cone" / "expectations.json").read_text(encoding="utf-8")
    )
    root = FIXTURES / "impact_cone"
    result = extract_lean_repository(root)
    assert result.extractor == REGEX_STUB_EXTRACTOR
    graph = build_dependency_graph(result)
    cone = impact_cone(graph, changed=set(expectations["changed"]))
    for name in expectations["must_include"]:
        assert name in cone, f"expected {name} in cone, got {sorted(cone)}"
    for name in expectations["must_exclude"]:
        assert name not in cone, f"unexpected {name} in cone"


def test_axiom_fixtures_clean_vs_prohibited() -> None:
    prohibited = extract_lean_repository(FIXTURES / "axioms")
    assert any("prohibitedChoice" in a for a in prohibited.axioms_used)

    clean_text = (FIXTURES / "axioms" / "Clean.lean").read_text(encoding="utf-8")
    clean_result = RegexLeanExtractor().extract_text(clean_text, path="Clean.lean")
    assert not any("prohibitedChoice" in a for a in clean_result.axioms_used)
    assert clean_result.extractor == REGEX_STUB_EXTRACTOR
    assert clean_result.complete is False
