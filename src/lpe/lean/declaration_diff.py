"""Elaborated declaration diff between base and candidate extractions (CLOSURE-009)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from lpe.lean.models import (
    DeclarationEdge,
    DeclarationRecord,
    ImportEdge,
    LeanExtractionResultV2,
)
from lpe.models import StrictModel

DiffKind = Literal[
    "added",
    "removed",
    "renamed",
    "type_changed",
    "body_only",
    "visibility_changed",
    "attribute_changed",
    "axiom_changed",
    "dependency_changed",
    "import_changed",
]


class DeclarationChange(StrictModel):
    kind: DiffKind
    fqn: str
    other_fqn: str | None = None
    base: DeclarationRecord | None = None
    candidate: DeclarationRecord | None = None
    detail: str = ""


class DeclarationDiff(StrictModel):
    """Structured base→candidate declaration comparison (§9.8)."""

    schema_version: Literal["2.0"] = "2.0"
    base_snapshot_fingerprint: str
    candidate_snapshot_fingerprint: str
    authoritative: bool = True
    changes: list[DeclarationChange] = Field(default_factory=list)
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    renamed: list[tuple[str, str]] = Field(default_factory=list)
    type_changed: list[str] = Field(default_factory=list)
    body_only: list[str] = Field(default_factory=list)
    visibility_changed: list[str] = Field(default_factory=list)
    attribute_changed: list[str] = Field(default_factory=list)
    axiom_changed: list[str] = Field(default_factory=list)
    dependency_changed: list[str] = Field(default_factory=list)
    import_changed: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def is_authoritative(self) -> bool:
        return self.authoritative

    def impact_cone_seeds(self) -> set[str]:
        seeds: set[str] = set()
        seeds.update(self.added)
        seeds.update(self.removed)
        seeds.update(self.type_changed)
        seeds.update(self.body_only)
        seeds.update(self.visibility_changed)
        seeds.update(self.attribute_changed)
        seeds.update(self.axiom_changed)
        for old, new in self.renamed:
            seeds.add(old)
            seeds.add(new)
        return seeds


def _rename_candidates(
    removed: dict[str, DeclarationRecord],
    added: dict[str, DeclarationRecord],
) -> list[tuple[str, str]]:
    """Pair removed/added decls with identical type hash and kind (rename heuristic)."""
    pairs: list[tuple[str, str]] = []
    used_added: set[str] = set()
    for old_fqn, old in sorted(removed.items()):
        matches = [
            new_fqn
            for new_fqn, new in added.items()
            if new_fqn not in used_added
            and new.kind == old.kind
            and new.type_expr_hash
            and new.type_expr_hash == old.type_expr_hash
            and new.fqn != old.fqn
        ]
        if len(matches) == 1:
            pairs.append((old_fqn, matches[0]))
            used_added.add(matches[0])
    return pairs


def _edge_set(edges: list[DeclarationEdge]) -> set[tuple[str, str]]:
    return {(e.dependee, e.depender) for e in edges}


def _import_set(edges: list[ImportEdge]) -> set[tuple[str, str]]:
    return {(e.imported, e.importing) for e in edges}


def diff_extractions(
    base: LeanExtractionResultV2,
    candidate: LeanExtractionResultV2,
    *,
    authoritative: bool = True,
) -> DeclarationDiff:
    """Compare two protocol-v2 extractions and classify declaration changes."""
    base_map = base.declaration_map()
    cand_map = candidate.declaration_map()
    base_names = set(base_map)
    cand_names = set(cand_map)

    removed_map = {n: base_map[n] for n in sorted(base_names - cand_names)}
    added_map = {n: cand_map[n] for n in sorted(cand_names - base_names)}
    renames = _rename_candidates(removed_map, added_map)
    renamed_old = {a for a, _ in renames}
    renamed_new = {b for _, b in renames}

    added = sorted(n for n in added_map if n not in renamed_new)
    removed = sorted(n for n in removed_map if n not in renamed_old)

    changes: list[DeclarationChange] = []
    type_changed: list[str] = []
    body_only: list[str] = []
    visibility_changed: list[str] = []
    attribute_changed: list[str] = []
    axiom_changed: list[str] = []

    for old, new in renames:
        changes.append(
            DeclarationChange(
                kind="renamed",
                fqn=old,
                other_fqn=new,
                base=base_map[old],
                candidate=cand_map[new],
                detail="type_expr_hash+kind match",
            )
        )

    for name in added:
        changes.append(
            DeclarationChange(
                kind="added",
                fqn=name,
                candidate=cand_map[name],
            )
        )
    for name in removed:
        changes.append(
            DeclarationChange(
                kind="removed",
                fqn=name,
                base=base_map[name],
            )
        )

    shared = sorted((base_names & cand_names) - renamed_old - renamed_new)
    for name in shared:
        b = base_map[name]
        c = cand_map[name]
        if b.type_expr_hash != c.type_expr_hash or b.type_pretty != c.type_pretty:
            type_changed.append(name)
            changes.append(
                DeclarationChange(
                    kind="type_changed",
                    fqn=name,
                    base=b,
                    candidate=c,
                    detail="type_expr_hash or type_pretty differs",
                )
            )
        elif (b.value_expr_hash or "") != (c.value_expr_hash or ""):
            body_only.append(name)
            changes.append(
                DeclarationChange(
                    kind="body_only",
                    fqn=name,
                    base=b,
                    candidate=c,
                    detail="value_expr_hash differs; type unchanged",
                )
            )
        if b.public_visibility != c.public_visibility:
            visibility_changed.append(name)
            changes.append(
                DeclarationChange(
                    kind="visibility_changed",
                    fqn=name,
                    base=b,
                    candidate=c,
                    detail=f"{b.public_visibility} -> {c.public_visibility}",
                )
            )
        if list(b.attributes) != list(c.attributes):
            attribute_changed.append(name)
            changes.append(
                DeclarationChange(
                    kind="attribute_changed",
                    fqn=name,
                    base=b,
                    candidate=c,
                )
            )
        base_ax = list(b.axioms_used) or list(base.axioms_by_declaration.get(name) or [])
        cand_ax = list(c.axioms_used) or list(candidate.axioms_by_declaration.get(name) or [])
        if sorted(base_ax) != sorted(cand_ax):
            axiom_changed.append(name)
            changes.append(
                DeclarationChange(
                    kind="axiom_changed",
                    fqn=name,
                    base=b,
                    candidate=c,
                    detail="axiom set differs",
                )
            )

    base_edges = _edge_set(base.declaration_dependency_edges)
    cand_edges = _edge_set(candidate.declaration_dependency_edges)
    dep_changed_names: set[str] = set()
    for dependee, depender in base_edges.symmetric_difference(cand_edges):
        dep_changed_names.add(dependee)
        dep_changed_names.add(depender)
        changes.append(
            DeclarationChange(
                kind="dependency_changed",
                fqn=depender,
                other_fqn=dependee,
                detail=f"edge ({dependee}, {depender})",
            )
        )
    dependency_changed = sorted(dep_changed_names)

    base_imports = _import_set(base.import_edges)
    cand_imports = _import_set(candidate.import_edges)
    import_changed_names: set[str] = set()
    for imported, importing in base_imports.symmetric_difference(cand_imports):
        import_changed_names.add(imported)
        import_changed_names.add(importing)
        changes.append(
            DeclarationChange(
                kind="import_changed",
                fqn=importing,
                other_fqn=imported,
                detail=f"import ({imported}, {importing})",
            )
        )
    import_changed = sorted(import_changed_names)

    return DeclarationDiff(
        base_snapshot_fingerprint=base.snapshot_fingerprint,
        candidate_snapshot_fingerprint=candidate.snapshot_fingerprint,
        authoritative=authoritative,
        changes=changes,
        added=added,
        removed=removed,
        renamed=renames,
        type_changed=type_changed,
        body_only=body_only,
        visibility_changed=visibility_changed,
        attribute_changed=attribute_changed,
        axiom_changed=axiom_changed,
        dependency_changed=dependency_changed,
        import_changed=import_changed,
    )
