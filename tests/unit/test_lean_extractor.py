from __future__ import annotations

import json
from pathlib import Path

from lpe.hashing import sha256_text
from lpe.lean.extractor import (
    REGEX_STUB_EXTRACTOR,
    TOOLCHAIN_EXTRACTOR,
    RegexLeanExtractor,
    build_dependency_graph,
    extract_lean_repository,
    impact_cone,
    import_expansion,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "lean"


def test_extract_declarations_signature_hashes() -> None:
    extractor = RegexLeanExtractor()
    text = """
import Mathlib.Data.Nat

theorem sampleTheorem : True := by trivial
def sampleDef : Nat := 1
axiom badAxiom : False
"""
    result = extractor.extract_text(text, path="Sample.lean")
    assert result.extractor == REGEX_STUB_EXTRACTOR
    assert result.complete is False
    names = [d.name for d in result.declarations]
    assert any("sampleTheorem" in n for n in names)
    assert any("badAxiom" in a for a in result.axioms_used)
    for decl in result.declarations:
        assert decl.signature_hash == sha256_text(decl.signature)
        assert decl.signature_hash


def test_regex_stub_never_claims_toolchain() -> None:
    result = RegexLeanExtractor().extract_text("def x : Nat := 1\n", path="X.lean")
    assert result.extractor == REGEX_STUB_EXTRACTOR
    assert result.complete is False
    payload = result.to_dict()
    assert payload["extractor"] == REGEX_STUB_EXTRACTOR
    from lpe.lean.extractor import LeanExtractionResult

    roundtrip = LeanExtractionResult.from_dict(payload)
    assert roundtrip.extractor == REGEX_STUB_EXTRACTOR


def test_impact_cone_hand_audited_membership() -> None:
    """AUDIT-012 / ISSUE-026: cone is downstream dependents, not upstream imports."""
    root = FIXTURES / "impact_cone"
    result = extract_lean_repository(root)
    assert result.extractor == REGEX_STUB_EXTRACTOR

    names = {d.name for d in result.declarations}
    assert "Impact.Core.coreVal" in names
    assert "Impact.Consumer.usesCore" in names
    assert "Impact.GrandConsumer.usesUsesCore" in names
    assert "Impact.Unrelated.other" in names

    graph = build_dependency_graph(result)
    cone = impact_cone(graph, changed={"Impact.Core.coreVal"})

    assert "Impact.Core.helper" in cone
    assert "Impact.Consumer.usesCore" in cone
    assert "Impact.Consumer.aboutCore" in cone
    assert "Impact.GrandConsumer.usesUsesCore" in cone
    assert "Impact.Unrelated.other" not in cone


def test_impact_cone_same_file_uses() -> None:
    text = """
def coreVal : Nat := 1
def usesCore : Nat := coreVal + 1
def unrelated : Nat := 9
"""
    result = RegexLeanExtractor().extract_text(text, path="Local.lean")
    graph = build_dependency_graph(result)
    cone = impact_cone(graph, changed={"Local.coreVal"})
    assert "Local.usesCore" in cone
    assert "Local.unrelated" not in cone


def test_import_expansion_added_removed() -> None:
    diff = import_expansion(["A", "B"], ["B", "C"])
    assert diff["added"] == ["C"]
    assert diff["removed"] == ["A"]


def test_schema_1_1_decl_edges_drive_impact_cone() -> None:
    """Impact cone prefers declaration_dependency_edges over mixed legacy edges."""
    from lpe.lean.extractor import LeanDeclaration, LeanExtractionResult

    result = LeanExtractionResult(
        declarations=[
            LeanDeclaration(
                name="M.a",
                kind="def",
                path="M.lean",
                line=1,
                signature="def a : Nat",
                signature_hash="x",
            ),
            LeanDeclaration(
                name="M.b",
                kind="def",
                path="M.lean",
                line=2,
                signature="def b : Nat",
                signature_hash="y",
            ),
            LeanDeclaration(
                name="M.c",
                kind="def",
                path="M.lean",
                line=3,
                signature="def c : Nat",
                signature_hash="z",
            ),
        ],
        # Spurious legacy edge that should not alone define the cone when
        # declaration_dependency_edges are authoritative.
        dependency_edges=[("Other.Mod", "M.c")],
        declaration_dependency_edges=[("M.a", "M.b"), ("M.b", "M.c")],
        import_edges=[("Other.Mod", "M")],
        extraction_schema_version="1.1",
        extractor=TOOLCHAIN_EXTRACTOR,
        complete=True,
    )
    graph = build_dependency_graph(result)
    cone = impact_cone(graph, changed={"M.a"})
    assert cone == {"M.b", "M.c"}
    payload = result.to_dict()
    assert payload["extraction_schema_version"] == "1.1"
    assert payload["declaration_dependency_edges"] == [["M.a", "M.b"], ["M.b", "M.c"]]
    assert payload["import_edges"] == [["Other.Mod", "M"]]
    roundtrip = LeanExtractionResult.from_dict(payload)
    assert roundtrip.declaration_dependency_edges == result.declaration_dependency_edges
    assert roundtrip.import_edges == result.import_edges


def test_schema_1_0_artifact_still_loads() -> None:
    """Backward compatible: old JSON without schema 1.1 fields still parses."""
    from lpe.lean.extractor import LeanExtractionResult

    data = {
        "declarations": [
            {
                "name": "M.foo",
                "kind": "def",
                "path": "M.lean",
                "line": 1,
                "signature": "def foo : Nat",
                "signature_hash": "abc",
            },
            {
                "name": "M.bar",
                "kind": "def",
                "path": "M.lean",
                "line": 2,
                "signature": "def bar : Nat",
                "signature_hash": "def",
            },
        ],
        "dependency_edges": [["M.foo", "M.bar"]],
        "extractor": TOOLCHAIN_EXTRACTOR,
        "complete": True,
    }
    result = LeanExtractionResult.from_dict(data)
    assert result.extraction_schema_version == "1.0"
    assert result.effective_declaration_edges() == [("M.foo", "M.bar")]
    graph = build_dependency_graph(result)
    assert impact_cone(graph, changed={"M.foo"}) == {"M.bar"}


def test_resolve_changed_names_short_to_fqn() -> None:
    """Git short names map to module FQNs when extraction is available."""
    from types import SimpleNamespace

    from lpe.lean.extractor import LeanDeclaration, LeanExtractionResult, resolve_changed_names_for_cone

    extraction = LeanExtractionResult(
        declarations=[
            LeanDeclaration(
                name="LpeFixture.Core.helper",
                kind="def",
                path="LpeFixture/Core.lean",
                line=5,
                signature="def helper : Nat",
                signature_hash="h",
            ),
            LeanDeclaration(
                name="LpeFixture.Consumer.usesCore",
                kind="def",
                path="LpeFixture/Consumer.lean",
                line=3,
                signature="def usesCore : Nat",
                signature_hash="u",
            ),
        ],
        declaration_dependency_edges=[
            ("LpeFixture.Core.helper", "LpeFixture.Consumer.usesCore"),
        ],
        extraction_schema_version="1.1",
        extractor=TOOLCHAIN_EXTRACTOR,
        complete=True,
    )
    decls = [
        SimpleNamespace(name="helper", path="LpeFixture/Core.lean"),
    ]
    resolved = resolve_changed_names_for_cone(decls, extraction)
    assert resolved == {"LpeFixture.Core.helper"}
    cone = impact_cone(
        build_dependency_graph(extraction),
        changed=resolved,
    )
    assert "LpeFixture.Consumer.usesCore" in cone


def test_resolve_changed_names_keeps_existing_fqn() -> None:
    from types import SimpleNamespace

    from lpe.lean.extractor import LeanDeclaration, LeanExtractionResult, resolve_changed_names_for_cone

    extraction = LeanExtractionResult(
        declarations=[
            LeanDeclaration(
                name="LpeFixture.Core.helper",
                kind="def",
                path="LpeFixture/Core.lean",
                line=5,
                signature="def helper : Nat",
                signature_hash="h",
            ),
        ],
        extractor=TOOLCHAIN_EXTRACTOR,
        complete=True,
    )
    decls = [
        SimpleNamespace(name="LpeFixture.Core.helper", path="LpeFixture/Core.lean"),
    ]
    assert resolve_changed_names_for_cone(decls, extraction) == {
        "LpeFixture.Core.helper"
    }


def test_placeholders_extracted_from_body() -> None:
    text = """
theorem unfinished : True := by
  sorry
"""
    result = RegexLeanExtractor().extract_text(text, path="P.lean")
    assert "sorry" in result.placeholders


def test_adaptive_loads_toolchain_json(tmp_path: Path) -> None:
    artifact = tmp_path / ".lpe" / "lean-extraction.json"
    artifact.parent.mkdir(parents=True)
    payload = {
        "declarations": [
            {
                "name": "M.foo",
                "kind": "def",
                "path": "M.lean",
                "line": 1,
                "signature": "def foo : Nat",
                "signature_hash": sha256_text("def foo : Nat"),
                "is_axiom": False,
            }
        ],
        "axioms_used": [],
        "imports": [],
        "dependency_edges": [],
        "extractor": TOOLCHAIN_EXTRACTOR,
        "complete": True,
    }
    artifact.write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "M.lean").write_text("def foo : Nat := 1\n", encoding="utf-8")
    result = extract_lean_repository(tmp_path)
    assert result.extractor == TOOLCHAIN_EXTRACTOR
    assert result.complete is True
    assert any(d.name == "M.foo" for d in result.declarations)


def test_prohibited_axiom_fixture_detected() -> None:
    result = extract_lean_repository(FIXTURES / "axioms")
    assert result.extractor == REGEX_STUB_EXTRACTOR
    assert any("prohibitedChoice" in a for a in result.axioms_used)
