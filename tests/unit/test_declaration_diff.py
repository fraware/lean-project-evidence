"""Golden cases for elaborated declaration diff (CLOSURE-009)."""

from __future__ import annotations

from lpe.lean.declaration_diff import diff_extractions
from lpe.lean.models import (
    DeclarationEdge,
    DeclarationRecord,
    ExtractionCompleteness,
    ImportEdge,
    LeanExtractionResultV2,
)


def _decl(
    fqn: str,
    *,
    kind: str = "theorem",
    type_hash: str = "t" * 64,
    value_hash: str | None = "v" * 64,
    visibility: str = "public",
    attributes: list[str] | None = None,
    axioms: list[str] | None = None,
) -> DeclarationRecord:
    return DeclarationRecord(
        fqn=fqn,
        kind=kind,  # type: ignore[arg-type]
        module=fqn.rsplit(".", 1)[0],
        type_pretty=f"ty:{type_hash[:8]}",
        type_expr_hash=type_hash,
        value_expr_hash=value_hash,
        public_visibility=visibility,  # type: ignore[arg-type]
        attributes=list(attributes or []),
        axioms_used=list(axioms or []),
    )


def _ext(
    *decls: DeclarationRecord,
    fingerprint: str = "base",
    edges: list[DeclarationEdge] | None = None,
    imports: list[ImportEdge] | None = None,
) -> LeanExtractionResultV2:
    return LeanExtractionResultV2(
        snapshot_fingerprint=fingerprint,
        declarations=list(decls),
        declaration_dependency_edges=list(edges or []),
        import_edges=list(imports or []),
        completeness=ExtractionCompleteness(environment_loaded=True),
    )


def test_added_removed() -> None:
    base = _ext(
        _decl("M.a", type_hash="a" * 64),
        _decl("M.b", type_hash="b" * 64),
        fingerprint="b",
    )
    head = _ext(
        _decl("M.a", type_hash="a" * 64),
        _decl("M.c", type_hash="c" * 64),
        fingerprint="h",
    )
    diff = diff_extractions(base, head)
    assert diff.removed == ["M.b"]
    assert diff.added == ["M.c"]


def test_rename_candidate_by_type_hash() -> None:
    base = _ext(_decl("M.old", type_hash="same" + "0" * 60), fingerprint="b")
    head = _ext(_decl("M.new", type_hash="same" + "0" * 60), fingerprint="h")
    diff = diff_extractions(base, head)
    assert diff.renamed == [("M.old", "M.new")]
    assert diff.added == []
    assert diff.removed == []


def test_type_vs_body_only() -> None:
    base = _ext(
        _decl("M.t", type_hash="typeAAAA" + "0" * 56, value_hash="body1111" + "0" * 56),
        fingerprint="b",
    )
    head_type = _ext(
        _decl("M.t", type_hash="typeBBBB" + "0" * 56, value_hash="body1111" + "0" * 56),
        fingerprint="h",
    )
    head_body = _ext(
        _decl("M.t", type_hash="typeAAAA" + "0" * 56, value_hash="body2222" + "0" * 56),
        fingerprint="h2",
    )
    assert diff_extractions(base, head_type).type_changed == ["M.t"]
    assert diff_extractions(base, head_body).body_only == ["M.t"]


def test_visibility_attribute_axiom() -> None:
    base = _ext(
        _decl("M.t", visibility="private", attributes=["simp"], axioms=["propext"]),
        fingerprint="b",
    )
    head = _ext(
        _decl("M.t", visibility="public", attributes=["simp", "inline"], axioms=[]),
        fingerprint="h",
    )
    diff = diff_extractions(base, head)
    assert "M.t" in diff.visibility_changed
    assert "M.t" in diff.attribute_changed
    assert "M.t" in diff.axiom_changed


def test_dependency_and_import_changes() -> None:
    base = _ext(
        _decl("M.a"),
        _decl("M.b"),
        fingerprint="b",
        edges=[DeclarationEdge(dependee="M.a", depender="M.b")],
        imports=[ImportEdge(imported="Init", importing="M")],
    )
    head = _ext(
        _decl("M.a"),
        _decl("M.b"),
        fingerprint="h",
        edges=[DeclarationEdge(dependee="M.b", depender="M.a")],
        imports=[ImportEdge(imported="Std", importing="M")],
    )
    diff = diff_extractions(base, head)
    assert diff.dependency_changed
    assert diff.import_changed
