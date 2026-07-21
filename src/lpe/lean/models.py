"""Lean extraction protocol v2 models (CLOSURE-007 / spec §9.5-9.7).

Dimension-specific completeness only - there is no global ``complete`` boolean.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from lpe.hashing import sha256_text
from lpe.models import StrictModel

EXTRACTION_SCHEMA_V2 = "2.0"
EXTRACTION_PROTOCOL_VERSION = "2.0"
GENERIC_EXTRACTOR_ID = "lean.generic-inject"
UNSUPPORTED_TOOLCHAIN_CODE = "UNSUPPORTED_TOOLCHAIN"
MODULE_DISCOVERY_AMBIGUOUS_CODE = "MODULE_DISCOVERY_AMBIGUOUS"
MODULE_DISCOVERY_UNKNOWN_CODE = "MODULE_DISCOVERY_UNKNOWN"

DeclarationKind = Literal[
    "axiom",
    "theorem",
    "opaque",
    "definition",
    "inductive",
    "constructor",
    "recursor",
    "instance",
    "abbrev",
    "structure",
    "class",
]

PublicVisibility = Literal["public", "protected", "private", "internal", "unknown"]


class ModuleRecord(StrictModel):
    name: str
    source_path: str | None = None
    imported: bool = True


class DeclarationEdge(StrictModel):
    """Dependency edge as ``(dependee, depender)`` — dependee is used by depender."""

    dependee: str
    depender: str


class ImportEdge(StrictModel):
    """Module import edge as ``(imported, importing)``."""

    imported: str
    importing: str


class PlaceholderRecord(StrictModel):
    token: str
    declaration: str | None = None
    module: str | None = None
    source_path: str | None = None
    line: int | None = None


class ExtractionError(StrictModel):
    code: str
    message: str
    actionable: str | None = None


class ExtractionCompleteness(StrictModel):
    """Per-dimension completeness — never collapse to a single global bool (§9.7)."""

    environment_loaded: bool = False
    all_project_modules_imported: bool = False
    declaration_types_complete: bool = False
    declaration_values_available_where_exposed: bool = False
    axiom_collection_complete_for_loaded_environment: bool = False
    source_positions_complete: bool = False
    known_limitations: list[str] = Field(default_factory=list)

    def any_dimension_complete(self) -> bool:
        return any(
            [
                self.environment_loaded,
                self.all_project_modules_imported,
                self.declaration_types_complete,
                self.declaration_values_available_where_exposed,
                self.axiom_collection_complete_for_loaded_environment,
                self.source_positions_complete,
            ]
        )


class DeclarationRecord(StrictModel):
    fqn: str
    kind: DeclarationKind
    module: str
    source_path: str | None = None
    source_start_line: int | None = None
    source_start_column: int | None = None
    public_visibility: PublicVisibility = "unknown"
    type_pretty: str = ""
    type_expr_hash: str = ""
    value_expr_hash: str | None = None
    universe_params: list[str] = Field(default_factory=list)
    attributes: list[str] = Field(default_factory=list)
    axioms_used: list[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if not self.type_expr_hash and self.type_pretty:
            object.__setattr__(self, "type_expr_hash", sha256_text(self.type_pretty))


class LeanExtractionResultV2(StrictModel):
    """Protocol v2 extraction artifact (§9.5)."""

    schema_version: Literal["2.0"] = "2.0"
    snapshot_fingerprint: str
    lean_version: str = ""
    lake_version: str = ""
    toolchain_spec: str = ""
    imported_modules: list[ModuleRecord] = Field(default_factory=list)
    declarations: list[DeclarationRecord] = Field(default_factory=list)
    declaration_dependency_edges: list[DeclarationEdge] = Field(default_factory=list)
    import_edges: list[ImportEdge] = Field(default_factory=list)
    axioms_by_declaration: dict[str, list[str]] = Field(default_factory=dict)
    placeholders: list[PlaceholderRecord] = Field(default_factory=list)
    errors: list[ExtractionError] = Field(default_factory=list)
    completeness: ExtractionCompleteness = Field(default_factory=ExtractionCompleteness)
    extractor: str = GENERIC_EXTRACTOR_ID
    extractor_version: str = "0.1.0"
    notes: list[str] = Field(default_factory=list)

    @property
    def has_blocking_errors(self) -> bool:
        return bool(self.errors)

    @property
    def is_unsupported_toolchain(self) -> bool:
        return any(e.code == UNSUPPORTED_TOOLCHAIN_CODE for e in self.errors)

    def declaration_map(self) -> dict[str, DeclarationRecord]:
        return {d.fqn: d for d in self.declarations}

    def effective_declaration_edges(self) -> list[tuple[str, str]]:
        return [(e.dependee, e.depender) for e in self.declaration_dependency_edges]

    def to_protocol_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_protocol_dict(cls, data: dict[str, Any]) -> LeanExtractionResultV2:
        return cls.model_validate(data)

    def incomplete_result(
        self,
        *,
        code: str,
        message: str,
        actionable: str | None = None,
    ) -> LeanExtractionResultV2:
        """Return a copy with an appended error and cleared false completeness claims."""
        errors = [
            *self.errors,
            ExtractionError(code=code, message=message, actionable=actionable),
        ]
        return self.model_copy(
            update={
                "errors": errors,
                "completeness": ExtractionCompleteness(
                    known_limitations=list(
                        dict.fromkeys(
                            [
                                *self.completeness.known_limitations,
                                f"incomplete due to {code}",
                            ]
                        )
                    )
                ),
            }
        )


def empty_extraction_v2(
    *,
    snapshot_fingerprint: str,
    toolchain_spec: str = "",
    errors: list[ExtractionError] | None = None,
    notes: list[str] | None = None,
    extractor: str = GENERIC_EXTRACTOR_ID,
) -> LeanExtractionResultV2:
    return LeanExtractionResultV2(
        snapshot_fingerprint=snapshot_fingerprint,
        toolchain_spec=toolchain_spec,
        errors=list(errors or []),
        notes=list(notes or []),
        extractor=extractor,
        completeness=ExtractionCompleteness(
            known_limitations=["no environment loaded"],
        ),
    )


def v2_to_legacy_extraction(result: LeanExtractionResultV2) -> Any:
    """Bridge protocol v2 → legacy ``LeanExtractionResult`` for compiler paths."""
    from lpe.lean.extractor import (
        TOOLCHAIN_EXTRACTOR,
        LeanDeclaration,
        LeanExtractionResult,
    )

    kind_map = {
        "definition": "def",
        "theorem": "theorem",
        "axiom": "axiom",
        "opaque": "opaque",
        "inductive": "structure",
        "constructor": "def",
        "recursor": "def",
        "instance": "instance",
        "abbrev": "abbrev",
        "structure": "structure",
        "class": "class",
    }
    decls: list[LeanDeclaration] = []
    for d in result.declarations:
        public = d.public_visibility not in {"private", "internal"}
        decls.append(
            LeanDeclaration(
                name=d.fqn,
                kind=kind_map.get(d.kind, "def"),
                path=d.source_path or "",
                line=d.source_start_line or 0,
                signature=d.type_pretty,
                signature_hash=d.type_expr_hash or sha256_text(d.type_pretty),
                is_axiom=d.kind == "axiom",
                public=public,
                imports=(),
                uses=(),
                placeholders=(),
            )
        )
    axioms = sorted(
        {ax for axs in result.axioms_by_declaration.values() for ax in axs}
        | {ax for d in result.declarations for ax in d.axioms_used}
    )
    env_ok = result.completeness.environment_loaded and not result.has_blocking_errors
    extractor = (
        GENERIC_EXTRACTOR_ID
        if result.extractor == GENERIC_EXTRACTOR_ID
        else (result.extractor or TOOLCHAIN_EXTRACTOR)
    )
    return LeanExtractionResult(
        declarations=decls,
        axioms_used=axioms,
        imports=[m.name for m in result.imported_modules],
        dependency_edges=result.effective_declaration_edges(),
        declaration_dependency_edges=result.effective_declaration_edges(),
        import_edges=[(e.imported, e.importing) for e in result.import_edges],
        placeholders=[p.token for p in result.placeholders],
        errors=[f"{e.code}: {e.message}" for e in result.errors],
        extractor=extractor,
        complete=env_ok and result.completeness.declaration_types_complete,
        toolchain_available=True,
        notes=list(result.notes),
        extraction_schema_version="1.1",
    )
