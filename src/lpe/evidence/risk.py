"""Risk classification from elaborated declaration diffs (CLOSURE-009 / §9.9).

Elaborated diffs may produce ``R0`` (body-only proof under identical type).
The lexical Git classifier is fallback-only and **never** returns ``R0``
(cannot produce R0 automatic acceptance).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from lpe.lean.declaration_diff import DeclarationDiff
from lpe.models import ArtifactType, CandidateDescriptor, RiskClass

RiskSource = Literal["elaborated_diff", "lexical_fallback"]

_RANK = {
    RiskClass.R0: 0,
    RiskClass.R1: 1,
    RiskClass.R2: 2,
    RiskClass.R3: 3,
    RiskClass.R4: 4,
}

_PUBLIC_TYPE_KINDS = frozenset(
    {
        "definition",
        "instance",
        "structure",
        "class",
        "abbrev",
        "axiom",
        "inductive",
        "opaque",
    }
)

_FOUNDATIONAL_HINTS = frozenset(
    {
        "foundation",
        "foundational",
        "prelude",
        "kernel",
        "axioms",
    }
)


@dataclass(frozen=True)
class RiskClassification:
    risk_class: RiskClass
    source: RiskSource
    reasons: tuple[str, ...] = ()

    @property
    def blocks_auto_accept(self) -> bool:
        """Lexical fallback must never enable R0 auto-accept."""
        return self.source == "lexical_fallback" or self.risk_class in {
            RiskClass.R3,
            RiskClass.R4,
        }


def _max_risk(current: RiskClass, candidate: RiskClass) -> RiskClass:
    return candidate if _RANK[candidate] > _RANK[current] else current


def _is_foundational(fqn: str, *, foundational_names: set[str] | None) -> bool:
    if foundational_names and fqn in foundational_names:
        return True
    lower = fqn.lower()
    return any(hint in lower for hint in _FOUNDATIONAL_HINTS)


def classify_risk_from_diff(
    diff: DeclarationDiff,
    *,
    changed_paths: list[str] | None = None,
    impact_cone_size: int = 0,
    impact_cone_threshold: int = 50,
    foundational_names: set[str] | None = None,
) -> RiskClassification:
    """Classify risk from an elaborated base/head declaration diff (§9.9)."""
    reasons: list[str] = []
    risk = RiskClass.R0
    paths = list(changed_paths or [])

    if any(
        path.endswith(("lakefile.lean", "lakefile.toml", "lake-manifest.json", "lean-toolchain"))
        for path in paths
    ):
        return RiskClassification(
            risk_class=RiskClass.R4,
            source="elaborated_diff",
            reasons=("toolchain or Lake manifest change",),
        )

    if impact_cone_size > impact_cone_threshold:
        return RiskClassification(
            risk_class=RiskClass.R4,
            source="elaborated_diff",
            reasons=(
                f"impact cone size {impact_cone_size} exceeds threshold {impact_cone_threshold}",
            ),
        )

    if diff.import_changed and len(diff.import_changed) >= 8:
        risk = _max_risk(risk, RiskClass.R4)
        reasons.append("broad import architecture change")

    for fqn in diff.removed:
        decl = next((c.base for c in diff.changes if c.fqn == fqn and c.base), None)
        if _is_foundational(fqn, foundational_names=foundational_names):
            risk = _max_risk(risk, RiskClass.R4)
            reasons.append(f"removed foundational {fqn}")
        elif decl is not None and decl.public_visibility in {"public", "protected", "unknown"}:
            risk = _max_risk(risk, RiskClass.R4)
            reasons.append(f"removed public declaration {fqn}")
        else:
            risk = _max_risk(risk, RiskClass.R2)
            reasons.append(f"removed declaration {fqn}")

    for fqn in diff.type_changed + diff.axiom_changed:
        decl = next(
            (c.candidate or c.base for c in diff.changes if c.fqn == fqn),
            None,
        )
        if _is_foundational(fqn, foundational_names=foundational_names):
            risk = _max_risk(risk, RiskClass.R4)
            reasons.append(f"foundational type/axiom change {fqn}")
            continue
        kind = decl.kind if decl is not None else ""
        if kind in _PUBLIC_TYPE_KINDS or kind == "theorem":
            risk = _max_risk(risk, RiskClass.R3)
            reasons.append(f"type or axiom set change {fqn}")
        else:
            risk = _max_risk(risk, RiskClass.R3)
            reasons.append(f"type/axiom change {fqn}")

    for fqn in diff.visibility_changed + diff.attribute_changed:
        risk = _max_risk(risk, RiskClass.R3)
        reasons.append(f"visibility/attribute change {fqn}")

    for fqn in diff.added:
        decl = next((c.candidate for c in diff.changes if c.fqn == fqn and c.candidate), None)
        if decl is None:
            risk = _max_risk(risk, RiskClass.R2)
            continue
        if _is_foundational(fqn, foundational_names=foundational_names):
            risk = _max_risk(risk, RiskClass.R4)
            reasons.append(f"added foundational {fqn}")
        elif decl.kind in _PUBLIC_TYPE_KINDS and decl.public_visibility != "private":
            risk = _max_risk(risk, RiskClass.R3)
            reasons.append(f"added public {decl.kind} {fqn}")
        elif decl.kind == "theorem" and decl.public_visibility != "private":
            # Public theorem addition with no changed existing type → R2
            risk = _max_risk(risk, RiskClass.R2)
            reasons.append(f"added public theorem {fqn}")
        elif decl.public_visibility == "private":
            risk = _max_risk(risk, RiskClass.R1)
            reasons.append(f"added private helper {fqn}")
        else:
            risk = _max_risk(risk, RiskClass.R2)
            reasons.append(f"added declaration {fqn}")

    for fqn in diff.body_only:
        decl = next(
            (c.candidate or c.base for c in diff.changes if c.fqn == fqn),
            None,
        )
        if decl is not None and decl.public_visibility == "private":
            risk = _max_risk(risk, RiskClass.R1)
            reasons.append(f"private body change {fqn}")
        elif decl is not None and decl.kind == "theorem":
            # body-only proof change under identical theorem type → R0
            risk = _max_risk(risk, RiskClass.R0)
            reasons.append(f"body-only theorem proof change {fqn}")
        else:
            risk = _max_risk(risk, RiskClass.R1)
            reasons.append(f"body-only change {fqn}")

    for _old, new in diff.renamed:
        risk = _max_risk(risk, RiskClass.R2)
        reasons.append(f"rename involving {new}")

    if not reasons and not diff.changes:
        reasons.append("no elaborated declaration changes")

    return RiskClassification(
        risk_class=risk,
        source="elaborated_diff",
        reasons=tuple(reasons),
    )


def classify_risk_lexical(candidate: CandidateDescriptor) -> RiskClassification:
    """Lexical Git-path classifier — fallback only; never returns R0."""
    reasons: list[str] = []
    if not candidate.changed_declarations:
        if any(
            path.endswith((".lean", "lakefile.lean", "lakefile.toml", "lake-manifest.json"))
            for path in candidate.changed_paths
        ):
            return RiskClassification(
                risk_class=RiskClass.R4,
                source="lexical_fallback",
                reasons=("lean/Lake path change without declaration metadata",),
            )
        # Lexical path must not produce R0 auto-accept.
        return RiskClassification(
            risk_class=RiskClass.R1,
            source="lexical_fallback",
            reasons=("lexical fallback floor R1 (no R0 auto-accept)",),
        )

    risk = RiskClass.R1  # floor — never R0 on lexical path
    reasons.append("lexical fallback (elaborated extraction unavailable)")

    for declaration in candidate.changed_declarations:
        if declaration.foundational:
            candidate_risk = RiskClass.R4
            reasons.append(f"foundational {declaration.name}")
        elif declaration.kind in {
            ArtifactType.DEFINITION,
            ArtifactType.STRUCTURE,
            ArtifactType.CLASS,
            ArtifactType.INSTANCE,
            ArtifactType.ABBREV,
        } and (declaration.signature_changed or declaration.public):
            candidate_risk = RiskClass.R3
            reasons.append(f"public/signature {declaration.kind} {declaration.name}")
        elif declaration.kind is ArtifactType.THEOREM and declaration.signature_changed:
            candidate_risk = RiskClass.R3
            reasons.append(f"theorem signature change {declaration.name}")
        elif declaration.public:
            candidate_risk = RiskClass.R2
            reasons.append(f"public declaration {declaration.name}")
        else:
            candidate_risk = RiskClass.R1
            reasons.append(f"private/helper {declaration.name}")
        risk = _max_risk(risk, candidate_risk)

    if any(
        path.endswith(("lakefile.lean", "lakefile.toml", "lake-manifest.json", "lean-toolchain"))
        for path in candidate.changed_paths
    ):
        risk = RiskClass.R4
        reasons.append("toolchain or Lake manifest path change")

    if risk == RiskClass.R0:
        risk = RiskClass.R1
        reasons.append("lexical fallback coerced R0→R1")

    return RiskClassification(
        risk_class=risk,
        source="lexical_fallback",
        reasons=tuple(reasons),
    )


def classify_risk_detailed(
    candidate: CandidateDescriptor,
    *,
    declaration_diff: DeclarationDiff | None = None,
    impact_cone_size: int = 0,
    impact_cone_threshold: int = 50,
    foundational_names: set[str] | None = None,
) -> RiskClassification:
    """Prefer elaborated diff; fall back to lexical (non-R0) classification."""
    if declaration_diff is not None and declaration_diff.is_authoritative:
        return classify_risk_from_diff(
            declaration_diff,
            changed_paths=list(candidate.changed_paths),
            impact_cone_size=impact_cone_size,
            impact_cone_threshold=impact_cone_threshold,
            foundational_names=foundational_names,
        )
    return classify_risk_lexical(candidate)


def classify_risk(
    candidate: CandidateDescriptor,
    *,
    declaration_diff: DeclarationDiff | None = None,
    impact_cone_size: int = 0,
    impact_cone_threshold: int = 50,
    foundational_names: set[str] | None = None,
) -> RiskClass:
    """Backward-compatible RiskClass entrypoint used by the evidence compiler."""
    return classify_risk_detailed(
        candidate,
        declaration_diff=declaration_diff,
        impact_cone_size=impact_cone_size,
        impact_cone_threshold=impact_cone_threshold,
        foundational_names=foundational_names,
    ).risk_class
