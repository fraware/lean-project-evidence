"""Elaborator IR honesty: opaque / axiom body-visibility limitations.

These tests document that schema 1.1 cones only see what
``ConstantInfo.getUsedConstantsAsSet`` exposes — opaque/axiom internals that
Lean does not store as used constants are **not** inventable as impact edges.
"""

from __future__ import annotations

from lpe.hashing import sha256_text
from lpe.lean.extractor import (
    EXTRACTION_SCHEMA_V1_1,
    TOOLCHAIN_EXTRACTOR,
    LeanDeclaration,
    LeanExtractionResult,
    build_dependency_graph,
    impact_cone,
)


def _decl(name: str, kind: str, *, is_axiom: bool = False) -> LeanDeclaration:
    sig = f"{kind} {name.split('.')[-1]}"
    return LeanDeclaration(
        name=name,
        kind=kind,
        path="LpeFixture/OpaqueLimits.lean",
        line=1,
        signature=sig,
        signature_hash=sha256_text(sig),
        is_axiom=is_axiom,
        public=True,
    )


def test_opaque_hidden_internal_not_in_cone_without_edge() -> None:
    """Opaque body helper is invisible unless Lean emits a decl edge to it."""
    result = LeanExtractionResult(
        extraction_schema_version=EXTRACTION_SCHEMA_V1_1,
        declarations=[
            _decl("LpeFixture.OpaqueLimits.hiddenHelper", "def"),
            _decl("LpeFixture.OpaqueLimits.secretOpaque", "opaque"),
            _decl("LpeFixture.OpaqueLimits.usesOpaque", "def"),
        ],
        # Honest IR: consumer depends on opaque; opaque does NOT edge to hiddenHelper
        # (body not unfolded beyond Lean's stored value/type constants).
        declaration_dependency_edges=[
            ("LpeFixture.OpaqueLimits.secretOpaque", "LpeFixture.OpaqueLimits.usesOpaque"),
        ],
        dependency_edges=[
            ("LpeFixture.OpaqueLimits.secretOpaque", "LpeFixture.OpaqueLimits.usesOpaque"),
        ],
        axioms_used=[],
        extractor=TOOLCHAIN_EXTRACTOR,
        complete=True,
        toolchain_available=True,
        notes=[
            "limitations: tactic-erased consts; opaque/axiom body visibility; "
            "no per-decl import provenance"
        ],
    )
    assert any("opaque/axiom" in n for n in result.notes)
    graph = build_dependency_graph(result)
    cone = impact_cone(graph, changed={"LpeFixture.OpaqueLimits.secretOpaque"})
    assert "LpeFixture.OpaqueLimits.usesOpaque" in cone
    assert "LpeFixture.OpaqueLimits.hiddenHelper" not in cone


def test_axiom_kind_flagged_and_appears_in_axioms_used() -> None:
    result = LeanExtractionResult(
        extraction_schema_version=EXTRACTION_SCHEMA_V1_1,
        declarations=[
            _decl("LpeFixture.OpaqueLimits.seedAxiom", "axiom", is_axiom=True),
            _decl("LpeFixture.OpaqueLimits.usesAxiom", "theorem"),
        ],
        declaration_dependency_edges=[
            ("LpeFixture.OpaqueLimits.seedAxiom", "LpeFixture.OpaqueLimits.usesAxiom"),
        ],
        dependency_edges=[
            ("LpeFixture.OpaqueLimits.seedAxiom", "LpeFixture.OpaqueLimits.usesAxiom"),
        ],
        axioms_used=["LpeFixture.OpaqueLimits.seedAxiom"],
        extractor=TOOLCHAIN_EXTRACTOR,
        complete=True,
        toolchain_available=True,
        notes=["limitations: opaque/axiom body visibility"],
    )
    axioms = [d for d in result.declarations if d.is_axiom]
    assert len(axioms) == 1
    assert axioms[0].kind == "axiom"
    assert "LpeFixture.OpaqueLimits.seedAxiom" in result.axioms_used
    cone = impact_cone(
        build_dependency_graph(result),
        changed={"LpeFixture.OpaqueLimits.seedAxiom"},
    )
    assert "LpeFixture.OpaqueLimits.usesAxiom" in cone


def test_effective_edges_prefer_declaration_dependency_edges() -> None:
    result = LeanExtractionResult(
        extraction_schema_version=EXTRACTION_SCHEMA_V1_1,
        declarations=[
            _decl("A", "def"),
            _decl("B", "opaque"),
        ],
        declaration_dependency_edges=[("A", "B")],
        dependency_edges=[("legacy", "noise")],
        extractor=TOOLCHAIN_EXTRACTOR,
        complete=True,
    )
    assert result.effective_declaration_edges() == [("A", "B")]
