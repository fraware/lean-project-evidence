"""Risk classification from elaborated diffs and lexical fallback (CLOSURE-009)."""

from __future__ import annotations

from lpe.evidence.risk import (
    classify_risk,
    classify_risk_detailed,
    classify_risk_from_diff,
    classify_risk_lexical,
)
from lpe.lean.declaration_diff import DeclarationDiff, diff_extractions
from lpe.lean.models import (
    DeclarationRecord,
    ExtractionCompleteness,
    LeanExtractionResultV2,
)
from lpe.models import (
    ArtifactType,
    CandidateDescriptor,
    ChangedDeclaration,
    GeneratorProvenance,
    RiskClass,
)


def make_candidate(
    declaration: ChangedDeclaration | None = None,
    *,
    paths: list[str] | None = None,
) -> CandidateDescriptor:
    decls = [declaration] if declaration is not None else []
    return CandidateDescriptor(
        candidate_id="candidate-risk-test",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="base",
        patch_text="+example",
        claimed_intent="Test risk",
        changed_paths=paths or ([declaration.path] if declaration else ["README.md"]),
        changed_declarations=decls,
        generator=GeneratorProvenance(generator_type="human", name="test"),
    )


def _decl(
    fqn: str,
    *,
    kind: str = "theorem",
    type_hash: str = "t" * 64,
    value_hash: str | None = "v" * 64,
    visibility: str = "public",
) -> DeclarationRecord:
    return DeclarationRecord(
        fqn=fqn,
        kind=kind,  # type: ignore[arg-type]
        module="M",
        type_pretty="T",
        type_expr_hash=type_hash,
        value_expr_hash=value_hash,
        public_visibility=visibility,  # type: ignore[arg-type]
    )


def _ext(*decls: DeclarationRecord, fp: str = "x") -> LeanExtractionResultV2:
    return LeanExtractionResultV2(
        snapshot_fingerprint=fp,
        declarations=list(decls),
        completeness=ExtractionCompleteness(environment_loaded=True),
    )


def test_public_definition_signature_change_is_r3() -> None:
    candidate = make_candidate(
        ChangedDeclaration(
            name="Example.x",
            kind=ArtifactType.DEFINITION,
            path="Example/Public.lean",
            signature_changed=True,
            public=True,
        )
    )
    assert classify_risk(candidate) is RiskClass.R3


def test_foundational_change_is_r4() -> None:
    candidate = make_candidate(
        ChangedDeclaration(
            name="Example.Foundation",
            kind=ArtifactType.STRUCTURE,
            path="Example/Foundation.lean",
            signature_changed=True,
            public=True,
            foundational=True,
        )
    )
    assert classify_risk(candidate) is RiskClass.R4


def test_private_helper_is_r1() -> None:
    candidate = make_candidate(
        ChangedDeclaration(
            name="Example.helper",
            kind=ArtifactType.THEOREM,
            path="Example/Internal.lean",
            signature_changed=False,
            public=False,
        )
    )
    assert classify_risk(candidate) is RiskClass.R1


def test_lexical_fallback_never_returns_r0() -> None:
    candidate = make_candidate(paths=["docs/README.md"])
    result = classify_risk_lexical(candidate)
    assert result.risk_class is not RiskClass.R0
    assert result.source == "lexical_fallback"
    assert result.blocks_auto_accept is True
    assert classify_risk(candidate) is RiskClass.R1


def test_body_only_theorem_is_r0_from_diff() -> None:
    base = _ext(_decl("M.t", value_hash="a" * 64), fp="b")
    head = _ext(_decl("M.t", value_hash="b" * 64), fp="h")
    diff = diff_extractions(base, head)
    assert diff.body_only == ["M.t"]
    classified = classify_risk_from_diff(diff)
    assert classified.risk_class is RiskClass.R0
    assert classified.source == "elaborated_diff"
    assert classified.blocks_auto_accept is False


def test_type_change_is_r3_from_diff() -> None:
    base = _ext(_decl("M.t", type_hash="a" * 64), fp="b")
    head = _ext(_decl("M.t", type_hash="b" * 64), fp="h")
    diff = diff_extractions(base, head)
    assert classify_risk_from_diff(diff).risk_class is RiskClass.R3


def test_removed_public_is_r4() -> None:
    base = _ext(_decl("M.pub", visibility="public"), fp="b")
    head = _ext(fp="h")
    diff = diff_extractions(base, head)
    assert classify_risk_from_diff(diff).risk_class is RiskClass.R4


def test_added_public_theorem_is_r2() -> None:
    base = _ext(fp="b")
    head = _ext(_decl("M.new", kind="theorem", visibility="public"), fp="h")
    diff = diff_extractions(base, head)
    assert classify_risk_from_diff(diff).risk_class is RiskClass.R2


def test_private_helper_add_is_r1() -> None:
    base = _ext(fp="b")
    head = _ext(_decl("M.helper", kind="definition", visibility="private"), fp="h")
    diff = diff_extractions(base, head)
    assert classify_risk_from_diff(diff).risk_class is RiskClass.R1


def test_toolchain_path_is_r4() -> None:
    empty = DeclarationDiff(
        base_snapshot_fingerprint="b",
        candidate_snapshot_fingerprint="h",
    )
    classified = classify_risk_from_diff(empty, changed_paths=["lean-toolchain"])
    assert classified.risk_class is RiskClass.R4


def test_detailed_prefers_elaborated_diff() -> None:
    base = _ext(_decl("M.t", value_hash="a" * 64), fp="b")
    head = _ext(_decl("M.t", value_hash="b" * 64), fp="h")
    diff = diff_extractions(base, head)
    candidate = make_candidate(
        ChangedDeclaration(
            name="M.t",
            kind=ArtifactType.THEOREM,
            path="M.lean",
            signature_changed=True,
            public=True,
        )
    )
    # Lexical alone would be R3 (signature_changed theorem); elaborated body-only → R0.
    detailed = classify_risk_detailed(candidate, declaration_diff=diff)
    assert detailed.risk_class is RiskClass.R0
    assert detailed.source == "elaborated_diff"
