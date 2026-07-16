"""Lean extraction adapter (kernel truth surface).

Graph semantics (AUDIT-012)
---------------------------
Dependency edges are stored as ``(dependee, depender)``:

- ``dependee`` is a declaration (or module) that is *used*
- ``depender`` is a declaration that *depends on* that use

Walking the adjacency list ``graph[dependee] -> [depender, ...]`` therefore
yields the **downstream impact cone**: declarations that may break when a
changed declaration changes. This is the opposite of walking upstream
imports.

Schema 1.1 (toolchain elaborator IR)
------------------------------------
- ``declaration_dependency_edges``: Environment constant deps
  (``ConstantInfo.getUsedConstantsAsSet``), suitable for impact cones.
- ``import_edges``: module→module ``(imported, importing)`` from ModuleData.
- ``dependency_edges``: backward-compatible; toolchain emits decl edges only.
  Regex-stub may still mix ``(module, decl)`` import provenance edges.

Import expansion (ISSUE-027)
----------------------------
``import_diff`` / ``import_expansion(before, after)`` report modules newly
present or removed between baselines. Toolchain ``imports`` lists fixture
modules observed as imports of other fixture modules (not Init/stdlib).

Extractor honesty (AUDIT-011 / AUDIT-003)
-----------------------------------------
- ``extractor == "lean.toolchain"`` only when a Lean/Lake toolchain extraction
  result is successfully loaded or produced. Never claim toolchain completeness
  without invoking Lean/Lake (or ingesting its JSON output).
- ``extractor == "regex-stub"`` for the AST-lite / regex path. Findings that
  require elaborator axiom closure must remain UNKNOWN, never PASS.

Residual elaborator limitations
-------------------------------
Even with schema 1.1 toolchain IR: tactic proofs may erase intermediate
constants; opaque/axiom bodies expose only what Lean stores; import edges are
module-level, not per-declaration import provenance.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from lpe.hashing import sha256_text

# Canonical incomplete extractor id — compiler must treat as non-authoritative.
REGEX_STUB_EXTRACTOR = "regex-stub"
TOOLCHAIN_EXTRACTOR = "lean.toolchain"

DECL_PATTERN = re.compile(
    r"^\s*(?P<attrs>(?:@\[[^\]]*\]\s*)*)"
    r"(?P<vis>private\s+|protected\s+)?"
    r"(?P<kind>theorem|lemma|def|abbrev|instance|structure|class|axiom|opaque)\s+"
    r"(?P<name>[A-Za-z0-9_.'«»]+)"
)
IMPORT_PATTERN = re.compile(r"^\s*import\s+(?P<module>[A-Za-z0-9_.]+)")
OPEN_PATTERN = re.compile(r"^\s*open\s+(?P<modules>.+)")
# Identifiers that may appear as uses (exclude keywords).
IDENT_PATTERN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)\b")
PLACEHOLDER_TOKENS = ("sorry", "admit", "stop", "unsafe")
LEAN_KEYWORDS = frozenset(
    {
        "theorem",
        "lemma",
        "def",
        "abbrev",
        "instance",
        "structure",
        "class",
        "axiom",
        "opaque",
        "import",
        "open",
        "namespace",
        "section",
        "end",
        "variable",
        "variables",
        "universe",
        "universes",
        "noncomputable",
        "partial",
        "private",
        "protected",
        "where",
        "by",
        "exact",
        "have",
        "show",
        "let",
        "if",
        "then",
        "else",
        "match",
        "with",
        "fun",
        "do",
        "return",
        "pure",
        "True",
        "False",
        "Nat",
        "Int",
        "Bool",
        "Prop",
        "Type",
        "Sort",
        "Unit",
        "And",
        "Or",
        "Not",
        "Eq",
        "HEq",
        "Iff",
        "Exists",
        "Forall",
    }
)

# Optional artifact relative to a Lean project root.
TOOLCHAIN_RESULT_CANDIDATES = (
    ".lpe/lean-extraction.json",
    ".lean-project-contract/lean-extraction.json",
)

# Extraction JSON schema versions (toolchain helper / committed artifacts).
EXTRACTION_SCHEMA_V1_0 = "1.0"
EXTRACTION_SCHEMA_V1_1 = "1.1"
CURRENT_EXTRACTION_SCHEMA = EXTRACTION_SCHEMA_V1_1


@dataclass(frozen=True)
class LeanDeclaration:
    """Declaration metadata with content-addressed signature hash (ISSUE-023)."""

    name: str
    kind: str
    path: str
    line: int
    signature: str
    signature_hash: str
    is_axiom: bool = False
    public: bool = True
    imports: tuple[str, ...] = ()
    uses: tuple[str, ...] = ()
    placeholders: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _coerce_edges(raw: Any) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for item in raw or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            edges.append((str(item[0]), str(item[1])))
    return edges


@dataclass
class LeanExtractionResult:
    """JSON-serializable extraction protocol result.

    Fields cover ISSUE-023–027 surfaces. ``complete`` is True only for
    toolchain-backed extractions axiom/dependency closure.

    Schema 1.1 adds ``declaration_dependency_edges`` and ``import_edges``.
    Older artifacts (implicit 1.0) remain loadable via ``dependency_edges``.
    """

    declarations: list[LeanDeclaration] = field(default_factory=list)
    axioms_used: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    # Edges: (dependee, depender) — see module docstring.
    dependency_edges: list[tuple[str, str]] = field(default_factory=list)
    # Schema 1.1: Environment-based decl→decl edges (prefer for impact cones).
    declaration_dependency_edges: list[tuple[str, str]] = field(default_factory=list)
    # Schema 1.1: module→module (imported, importing).
    import_edges: list[tuple[str, str]] = field(default_factory=list)
    placeholders: list[str] = field(default_factory=list)
    import_diff: dict[str, list[str]] = field(
        default_factory=lambda: {"added": [], "removed": []}
    )
    errors: list[str] = field(default_factory=list)
    extractor: str = REGEX_STUB_EXTRACTOR
    complete: bool = False
    toolchain_available: bool = False
    notes: list[str] = field(default_factory=list)
    extraction_schema_version: str = EXTRACTION_SCHEMA_V1_0

    def effective_declaration_edges(self) -> list[tuple[str, str]]:
        """Decl-decl edges for impact cones (schema 1.1 preferred)."""
        if self.declaration_dependency_edges:
            return list(self.declaration_dependency_edges)
        decl_names = {d.name for d in self.declarations}
        return [
            (a, b)
            for a, b in self.dependency_edges
            if a in decl_names and b in decl_names
        ]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "extraction_schema_version": self.extraction_schema_version,
            "declarations": [d.to_dict() for d in self.declarations],
            "axioms_used": list(self.axioms_used),
            "imports": list(self.imports),
            "dependency_edges": [list(edge) for edge in self.dependency_edges],
            "placeholders": list(self.placeholders),
            "import_diff": {
                "added": list(self.import_diff.get("added", [])),
                "removed": list(self.import_diff.get("removed", [])),
            },
            "errors": list(self.errors),
            "extractor": self.extractor,
            "complete": self.complete,
            "toolchain_available": self.toolchain_available,
            "notes": list(self.notes),
        }
        # Always emit 1.1 fields when present or when claiming current schema.
        if (
            self.declaration_dependency_edges
            or self.import_edges
            or self.extraction_schema_version >= EXTRACTION_SCHEMA_V1_1
        ):
            payload["declaration_dependency_edges"] = [
                list(edge) for edge in self.declaration_dependency_edges
            ]
            payload["import_edges"] = [list(edge) for edge in self.import_edges]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LeanExtractionResult:
        decls = [
            LeanDeclaration(
                name=str(item["name"]),
                kind=str(item.get("kind", "def")),
                path=str(item.get("path", "")),
                line=int(item.get("line", 0)),
                signature=str(item.get("signature", "")),
                signature_hash=str(
                    item.get("signature_hash") or sha256_text(str(item.get("signature", "")))
                ),
                is_axiom=bool(item.get("is_axiom", False)),
                public=bool(item.get("public", True)),
                imports=tuple(item.get("imports") or ()),
                uses=tuple(item.get("uses") or ()),
                placeholders=tuple(item.get("placeholders") or ()),
            )
            for item in data.get("declarations") or []
        ]
        edges = _coerce_edges(data.get("dependency_edges"))
        decl_edges = _coerce_edges(data.get("declaration_dependency_edges"))
        import_edges = _coerce_edges(data.get("import_edges"))
        has_v11_fields = (
            "declaration_dependency_edges" in data or "import_edges" in data
        )
        schema = str(
            data.get("extraction_schema_version")
            or (EXTRACTION_SCHEMA_V1_1 if has_v11_fields else EXTRACTION_SCHEMA_V1_0)
        )
        if not decl_edges and edges:
            decl_names = {d.name for d in decls}
            decl_edges = [(a, b) for a, b in edges if a in decl_names and b in decl_names]
        import_diff = data.get("import_diff") or {}
        return cls(
            declarations=decls,
            axioms_used=[str(x) for x in data.get("axioms_used") or []],
            imports=[str(x) for x in data.get("imports") or []],
            dependency_edges=edges,
            declaration_dependency_edges=decl_edges,
            import_edges=import_edges,
            placeholders=[str(x) for x in data.get("placeholders") or []],
            import_diff={
                "added": [str(x) for x in import_diff.get("added") or []],
                "removed": [str(x) for x in import_diff.get("removed") or []],
            },
            errors=[str(x) for x in data.get("errors") or []],
            extractor=str(data.get("extractor") or REGEX_STUB_EXTRACTOR),
            complete=bool(data.get("complete", False)),
            toolchain_available=bool(data.get("toolchain_available", False)),
            notes=[str(x) for x in data.get("notes") or []],
            extraction_schema_version=schema,
        )


@runtime_checkable
class LeanExtractor(Protocol):
    """Protocol for Lean extraction adapters."""

    provider_id: str
    provider_version: str

    def extract_file(self, path: Path) -> LeanExtractionResult: ...

    def extract_text(self, text: str, *, path: str = "<inline>") -> LeanExtractionResult: ...

    def extract_repository(
        self,
        repository: Path,
        *,
        lean_paths: list[str] | None = None,
    ) -> LeanExtractionResult: ...


def lean_toolchain_available(repository: Path | None = None) -> bool:
    """Return True when ``lake`` or ``lean`` is on PATH (optional toolchain path)."""
    del repository  # reserved for future lakefile-aware detection
    return shutil.which("lake") is not None or shutil.which("lean") is not None


def _module_name_from_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized.removesuffix(".lean").replace("/", ".")


def signature_for_hash(line: str) -> str:
    """Normalize a declaration header line for hashing (strip proof body hints)."""
    stripped = line.strip()
    for sep in (":=", " where", " by"):
        idx = stripped.find(sep)
        if idx > 0:
            return stripped[:idx].rstrip()
    return stripped


def _signature_from_header(line: str) -> str:
    return signature_for_hash(line)


def _find_placeholders(text: str) -> list[str]:
    found: list[str] = []
    for token in PLACEHOLDER_TOKENS:
        if re.search(rf"\b{re.escape(token)}\b", text):
            found.append(token)
    return found


def _collect_uses(body: str, *, known_names: set[str], self_name: str) -> list[str]:
    uses: list[str] = []
    seen: set[str] = set()
    for match in IDENT_PATTERN.finditer(body):
        ident = match.group(1)
        if ident == self_name or ident in LEAN_KEYWORDS:
            continue
        # Prefer fully qualified matches; also match unqualified suffix.
        candidates = [ident]
        short = ident.split(".")[-1]
        for name in known_names:
            if name == ident or name.endswith("." + short) or name.split(".")[-1] == short:
                if name != self_name:
                    candidates.append(name)
        for candidate in candidates:
            if candidate in known_names and candidate not in seen and candidate != self_name:
                seen.add(candidate)
                uses.append(candidate)
                break
    return uses


class RegexLeanExtractor:
    """AST-lite / regex Lean extractor.

    Always labels results as ``regex-stub``. Never claims elaborator completeness.
    """

    provider_id = REGEX_STUB_EXTRACTOR
    provider_version = "0.4.0"

    def extract_file(
        self,
        path: Path,
        *,
        logical_path: str | None = None,
    ) -> LeanExtractionResult:
        if not path.exists():
            return LeanExtractionResult(
                errors=[f"file not found: {path}"],
                extractor=REGEX_STUB_EXTRACTOR,
                complete=False,
                toolchain_available=lean_toolchain_available(path.parent),
            )
        text = path.read_text(encoding="utf-8", errors="replace")
        report_path = (logical_path or str(path)).replace("\\", "/")
        return self.extract_text(text, path=report_path)

    def extract_text(self, text: str, *, path: str = "<inline>") -> LeanExtractionResult:
        lines = text.splitlines()
        imports: list[str] = []
        decl_headers: list[tuple[int, re.Match[str], str]] = []

        for line_no, line in enumerate(lines, start=1):
            import_match = IMPORT_PATTERN.match(line)
            if import_match:
                imports.append(import_match.group("module"))
                continue
            open_match = OPEN_PATTERN.match(line)
            if open_match:
                for module in open_match.group("modules").split():
                    cleaned = module.strip()
                    if cleaned:
                        imports.append(cleaned)
                continue
            decl_match = DECL_PATTERN.match(line)
            if decl_match:
                decl_headers.append((line_no, decl_match, line))

        current_module = _module_name_from_path(path)
        # First pass: names for cross-ref.
        provisional_names: list[str] = []
        for _line_no, decl_match, _line in decl_headers:
            name = decl_match.group("name")
            full_name = name if "." in name else f"{current_module}.{name}"
            provisional_names.append(full_name)
        known_names = set(provisional_names)

        declarations: list[LeanDeclaration] = []
        axioms_used: list[str] = []
        edges: list[tuple[str, str]] = []
        import_edges: list[tuple[str, str]] = []
        placeholders_all: list[str] = []

        for idx, (line_no, decl_match, header_line) in enumerate(decl_headers):
            kind = decl_match.group("kind")
            name = decl_match.group("name")
            full_name = provisional_names[idx]
            is_axiom = kind == "axiom"
            vis = (decl_match.group("vis") or "").strip()
            public = vis != "private"
            signature = _signature_from_header(header_line)
            # Body: from this header through the line before the next header.
            end_line = (
                decl_headers[idx + 1][0] - 1 if idx + 1 < len(decl_headers) else len(lines)
            )
            body = "\n".join(lines[line_no - 1 : end_line])
            placeholders = _find_placeholders(body)
            placeholders_all.extend(placeholders)
            uses = _collect_uses(body, known_names=known_names, self_name=full_name)

            decl = LeanDeclaration(
                name=full_name,
                kind=kind,
                path=path,
                line=line_no,
                signature=signature,
                signature_hash=sha256_text(signature),
                is_axiom=is_axiom,
                public=public,
                imports=tuple(imports),
                uses=tuple(uses),
                placeholders=tuple(placeholders),
            )
            declarations.append(decl)
            if is_axiom:
                axioms_used.append(full_name)

            # Downstream-capable edges: dependee -> depender (AUDIT-012).
            for used in uses:
                edges.append((used, full_name))
            for imp in imports:
                edges.append((imp, full_name))
                import_edges.append((imp, current_module))

        # Decl-decl subset for schema 1.1 consumers.
        decl_names = {d.name for d in declarations}
        decl_edges = [(a, b) for a, b in edges if a in decl_names and b in decl_names]
        notes = [
            "regex-stub extraction: lexical AST-lite only; not elaborator axiom closure",
        ]
        return LeanExtractionResult(
            declarations=declarations,
            axioms_used=list(dict.fromkeys(axioms_used)),
            imports=list(dict.fromkeys(imports)),
            dependency_edges=edges,
            declaration_dependency_edges=list(dict.fromkeys(decl_edges)),
            import_edges=list(dict.fromkeys(import_edges)),
            placeholders=list(dict.fromkeys(placeholders_all)),
            extractor=REGEX_STUB_EXTRACTOR,
            complete=False,
            toolchain_available=lean_toolchain_available(),
            notes=notes,
            extraction_schema_version=EXTRACTION_SCHEMA_V1_1,
        )

    def extract_repository(
        self,
        repository: Path,
        *,
        lean_paths: list[str] | None = None,
        baseline_imports: list[str] | None = None,
    ) -> LeanExtractionResult:
        merged = LeanExtractionResult(
            extractor=REGEX_STUB_EXTRACTOR,
            complete=False,
            toolchain_available=lean_toolchain_available(repository),
            notes=[
                "regex-stub extraction: lexical AST-lite only; not elaborator axiom closure",
            ],
        )
        paths = lean_paths or [
            str(p.relative_to(repository)).replace("\\", "/")
            for p in repository.rglob("*.lean")
            if ".git" not in p.parts and ".lake" not in p.parts
        ]
        file_results: list[LeanExtractionResult] = []
        for rel in sorted(paths):
            result = self.extract_file(repository / rel, logical_path=rel)
            file_results.append(result)
            merged.declarations.extend(result.declarations)
            merged.axioms_used.extend(result.axioms_used)
            merged.imports.extend(result.imports)
            merged.dependency_edges.extend(result.dependency_edges)
            merged.declaration_dependency_edges.extend(
                result.declaration_dependency_edges
            )
            merged.import_edges.extend(result.import_edges)
            merged.placeholders.extend(result.placeholders)
            merged.errors.extend(result.errors)

        # Second-pass: keep import edges; refine decl→use edges with global names.
        known = {d.name for d in merged.declarations}
        short_index: dict[str, list[str]] = {}
        for name in known:
            short_index.setdefault(name.split(".")[-1], []).append(name)

        refined_edges: list[tuple[str, str]] = []
        refined_import_edges: list[tuple[str, str]] = list(
            dict.fromkeys(merged.import_edges)
        )
        for dependee, depender in merged.dependency_edges:
            if dependee not in known:
                # Module / import edge (dependee is not a declaration name).
                refined_edges.append((dependee, depender))
                if depender in known:
                    # Also record module→module when depender is a decl.
                    mod = depender.rsplit(".", 1)[0] if "." in depender else depender
                    refined_import_edges.append((dependee, mod))

        for decl in merged.declarations:
            path = Path(decl.path)
            if not path.is_file():
                path = repository / decl.path
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            file_result = self.extract_text(
                text, path=str(decl.path).replace("\\", "/")
            )
            local = next((d for d in file_result.declarations if d.name == decl.name), None)
            if local is None:
                continue
            for used in local.uses:
                resolved: str | None = None
                if used in known:
                    resolved = used
                elif used in short_index and len(short_index[used]) == 1:
                    resolved = short_index[used][0]
                else:
                    matches = short_index.get(used.split(".")[-1], [])
                    if len(matches) == 1:
                        resolved = matches[0]
                if resolved and resolved != decl.name:
                    refined_edges.append((resolved, decl.name))

        merged.dependency_edges = list(dict.fromkeys(refined_edges))
        decl_only = [(a, b) for a, b in refined_edges if a in known and b in known]
        merged.declaration_dependency_edges = list(dict.fromkeys(decl_only))
        merged.import_edges = list(dict.fromkeys(refined_import_edges))
        merged.imports = list(dict.fromkeys(merged.imports))
        merged.axioms_used = list(dict.fromkeys(merged.axioms_used))
        merged.placeholders = list(dict.fromkeys(merged.placeholders))
        merged.extraction_schema_version = EXTRACTION_SCHEMA_V1_1
        if baseline_imports is not None:
            merged.import_diff = import_expansion(baseline_imports, merged.imports)
        return merged


def load_toolchain_json(path: Path) -> LeanExtractionResult | None:
    """Load and normalize a toolchain extraction JSON artifact."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return LeanExtractionResult(
            errors=[f"invalid toolchain extraction JSON at {path}: {exc}"],
            extractor=REGEX_STUB_EXTRACTOR,
            complete=False,
            toolchain_available=True,
        )
    # Fill missing signature hashes (Lean helper may leave them empty).
    for item in data.get("declarations") or []:
        if isinstance(item, dict) and not item.get("signature_hash") and item.get("signature"):
            item["signature_hash"] = sha256_text(str(item["signature"]))
    result = LeanExtractionResult.from_dict(data)
    # Only claim toolchain when the artifact self-identifies (or omits extractor).
    claimed = str(data.get("extractor") or TOOLCHAIN_EXTRACTOR)
    if claimed == TOOLCHAIN_EXTRACTOR or claimed == "":
        result.extractor = TOOLCHAIN_EXTRACTOR
        result.complete = bool(data.get("complete", True)) and not result.errors
    else:
        result.extractor = claimed
        result.complete = False
    result.toolchain_available = True
    if not result.notes:
        result.notes = [f"loaded toolchain extraction from {path.as_posix()}"]
    return result


# Backward-compatible private alias.
_load_toolchain_json = load_toolchain_json


def _try_lake_extract_env(repository: Path) -> LeanExtractionResult | None:
    """Optionally probe Lake; never invent declaration data from a probe alone."""
    lake = shutil.which("lake")
    if lake is None:
        return None
    lakefile = repository / "lakefile.lean"
    lakefile_toml = repository / "lakefile.toml"
    if not lakefile.is_file() and not lakefile_toml.is_file():
        return None
    # Honor an explicit extract artifact env override.
    artifact = os.environ.get("LPE_LEAN_EXTRACTION_JSON")
    if artifact:
        loaded = load_toolchain_json(Path(artifact))
        if loaded is not None:
            return loaded
    # If Lake can run `env`, record toolchain availability but do not claim decls.
    try:
        proc = subprocess.run(
            [lake, "env", "printenv", "LEAN_PATH"],
            cwd=repository,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    # Toolchain is present but no extraction JSON — caller falls back to regex.
    return LeanExtractionResult(
        extractor=REGEX_STUB_EXTRACTOR,
        complete=False,
        toolchain_available=True,
        notes=[
            "lake env probe succeeded; no lean-extraction.json present — using regex-stub",
        ],
    )


def _apply_path_filters(
    loaded: LeanExtractionResult,
    *,
    lean_paths: list[str] | None,
    baseline_imports: list[str] | None,
) -> LeanExtractionResult:
    if lean_paths:
        allowed = {p.replace("\\", "/") for p in lean_paths}
        loaded.declarations = [
            d for d in loaded.declarations if d.path.replace("\\", "/") in allowed
        ]
    if baseline_imports is not None:
        loaded.import_diff = import_expansion(baseline_imports, loaded.imports)
    loaded.toolchain_available = True
    return loaded


class AdaptiveLeanExtractor:
    """Prefer toolchain JSON / Lake ``lpe_extract`` when available; else regex-stub."""

    provider_id = "lean.adaptive-extractor"
    provider_version = "0.5.0"

    def __init__(self) -> None:
        self._regex = RegexLeanExtractor()

    def extract_file(self, path: Path) -> LeanExtractionResult:
        return self._regex.extract_file(path)

    def extract_text(self, text: str, *, path: str = "<inline>") -> LeanExtractionResult:
        return self._regex.extract_text(text, path=path)

    def extract_repository(
        self,
        repository: Path,
        *,
        lean_paths: list[str] | None = None,
        baseline_imports: list[str] | None = None,
        run_toolchain: bool = True,
    ) -> LeanExtractionResult:
        toolchain_available = lean_toolchain_available(repository)
        # 1) Explicit toolchain artifact in the target repo.
        for rel in TOOLCHAIN_RESULT_CANDIDATES:
            loaded = load_toolchain_json(repository / rel)
            if loaded is not None and loaded.extractor == TOOLCHAIN_EXTRACTOR and not loaded.errors:
                return _apply_path_filters(
                    loaded, lean_paths=lean_paths, baseline_imports=baseline_imports
                )
            if loaded is not None and loaded.errors:
                # Fail closed: surface errors, still fall back to regex for decls.
                regex_result = self._regex.extract_repository(
                    repository,
                    lean_paths=lean_paths,
                    baseline_imports=baseline_imports,
                )
                regex_result.errors = list(loaded.errors) + list(regex_result.errors)
                regex_result.toolchain_available = True
                regex_result.notes.append(
                    "toolchain JSON invalid; fell back to regex-stub"
                )
                return regex_result

        # 2) Invoke Lake/Lean helper to produce toolchain JSON when available.
        lake_result: LeanExtractionResult | None = None
        if run_toolchain and toolchain_available:
            # Local import avoids import cycle at module load.
            from lpe.lean.toolchain import try_run_lake_extract

            lake_result = try_run_lake_extract(repository, force=True)
            if (
                lake_result is not None
                and lake_result.extractor == TOOLCHAIN_EXTRACTOR
                and lake_result.complete
                and not lake_result.errors
            ):
                return _apply_path_filters(
                    lake_result, lean_paths=lean_paths, baseline_imports=baseline_imports
                )
            if lake_result is not None and lake_result.errors:
                # Fail closed on extract errors: do not claim PASS via empty regex axioms.
                regex_result = self._regex.extract_repository(
                    repository,
                    lean_paths=lean_paths,
                    baseline_imports=baseline_imports,
                )
                regex_result.errors = list(lake_result.errors) + list(regex_result.errors)
                regex_result.toolchain_available = True
                regex_result.notes.extend(lake_result.notes)
                regex_result.notes.append(
                    "lake extract failed; fell back to regex-stub (incomplete)"
                )
                return regex_result

        # 3) Lake env probe — confirms toolchain, does not fabricate decls.
        probe = _try_lake_extract_env(repository)
        if probe is not None and probe.extractor == TOOLCHAIN_EXTRACTOR:
            return _apply_path_filters(
                probe, lean_paths=lean_paths, baseline_imports=baseline_imports
            )

        result = self._regex.extract_repository(
            repository,
            lean_paths=lean_paths,
            baseline_imports=baseline_imports,
        )
        result.toolchain_available = toolchain_available or (
            probe.toolchain_available if probe is not None else False
        ) or (lake_result.toolchain_available if lake_result is not None else False)
        notes: list[str] = []
        if lake_result is not None:
            notes.extend(lake_result.notes)
        if probe is not None:
            notes.extend(probe.notes)
        notes.extend(result.notes)
        result.notes = list(dict.fromkeys(notes))
        return result


def impact_cone(
    graph: dict[str, list[str]],
    *,
    changed: set[str],
) -> set[str]:
    """Return downstream dependents reachable from ``changed`` (AUDIT-012).

    ``graph[u]`` lists nodes that *depend on* ``u``. The returned set does not
    include the changed seeds themselves unless they appear as dependents of
    another changed node.
    """
    cone: set[str] = set()
    frontier = list(changed)
    while frontier:
        node = frontier.pop()
        for downstream in graph.get(node, []):
            if downstream not in cone:
                cone.add(downstream)
                frontier.append(downstream)
    return cone


def resolve_changed_names_for_cone(
    changed_declarations: list[Any],
    extraction: LeanExtractionResult,
) -> set[str]:
    """Map git short names to module FQNs when extraction names are available.

    Git classification emits short identifiers (``helper``). Toolchain /
    regex-stub graphs use module FQNs (``LpeFixture.Core.helper``). When
    extraction is present, resolve via:

    1. Exact match against known declaration / edge endpoint names
    2. Path-derived module FQN (``LpeFixture/Core.lean`` + ``helper``)
    3. Unique short-name suffix match among known names
    4. Path-derived FQN (best effort) or the original name

    Without extraction names, still prefers path→FQN when a ``.lean`` path is
    present so cones can align once edges appear.
    """
    known: set[str] = {d.name for d in extraction.declarations}
    for a, b in extraction.effective_declaration_edges():
        known.add(a)
        known.add(b)
    for a, b in extraction.dependency_edges:
        known.add(a)
        known.add(b)

    resolved: set[str] = set()
    for decl in changed_declarations:
        name = str(getattr(decl, "name", "") or "")
        path = str(getattr(decl, "path", "") or "")
        if not name:
            continue
        if name in known:
            resolved.add(name)
            continue

        path_fqn: str | None = None
        if path.endswith(".lean"):
            path_fqn = f"{_module_name_from_path(path)}.{name}"
            if path_fqn in known:
                resolved.add(path_fqn)
                continue

        if known:
            suffix = f".{name}"
            matches = sorted(k for k in known if k == name or k.endswith(suffix))
            if len(matches) == 1:
                resolved.add(matches[0])
                continue

        if path_fqn is not None:
            resolved.add(path_fqn)
        else:
            resolved.add(name)
    return resolved


def expand_imports(imports: list[str], known_modules: set[str]) -> list[str]:
    """Filter import list to modules present in ``known_modules`` (stable order)."""
    expanded: list[str] = []
    seen: set[str] = set()
    for module in imports:
        if module in seen:
            continue
        seen.add(module)
        if module in known_modules:
            expanded.append(module)
    return expanded


def import_expansion(
    before: list[str],
    after: list[str],
) -> dict[str, list[str]]:
    """Compute added/removed imports (ISSUE-027).

    Semantics: set difference on module name lists. ``added`` are modules
    present in ``after`` but not ``before``; ``removed`` are the reverse.
    Order is sorted for stable findings. Does not expand transitive Lake
    import closures beyond what the extractor recorded in ``imports``.
    """
    before_set = set(before)
    after_set = set(after)
    return {
        "added": sorted(after_set - before_set),
        "removed": sorted(before_set - after_set),
    }


def build_dependency_graph(extraction: LeanExtractionResult) -> dict[str, list[str]]:
    """Build adjacency list for downstream impact walks.

    Prefers ``declaration_dependency_edges`` (schema 1.1 Environment IR).
    Edge ``(dependee, depender)`` becomes ``graph[dependee].append(depender)``.

    Legacy ``dependency_edges`` may include ``(imported_module, local_decl)``;
    those expand onto declarations defined in the imported module so changing
    ``Core.foo`` reaches dependents that only recorded a module import
    (regex-stub). Schema 1.1 ``import_edges`` (module→module) are **not**
    expanded into the impact graph — they feed import-expansion findings only,
    so toolchain cones stay decl-dep trustworthy.
    """
    graph: dict[str, list[str]] = {}

    def _link(dependee: str, depender: str) -> None:
        bucket = graph.setdefault(dependee, [])
        if depender not in bucket:
            bucket.append(depender)

    decl_names = {d.name for d in extraction.declarations}
    module_to_decls: dict[str, list[str]] = {}
    for name in decl_names:
        if "." in name:
            module_to_decls.setdefault(name.rsplit(".", 1)[0], []).append(name)

    # Primary: Environment / refined decl→decl edges.
    for dependee, depender in extraction.effective_declaration_edges():
        _link(dependee, depender)

    # Legacy mixed dependency_edges (module→decl) for regex / schema 1.0.
    for dependee, depender in extraction.dependency_edges:
        if dependee in decl_names and depender in decl_names:
            _link(dependee, depender)
        elif dependee not in decl_names and depender in decl_names:
            _link(dependee, depender)
            for decl_name in module_to_decls.get(dependee, []):
                _link(decl_name, depender)

    return graph


def extract_lean_repository(
    repository: Path,
    *,
    lean_paths: list[str] | None = None,
    baseline_imports: list[str] | None = None,
    run_toolchain: bool = True,
) -> LeanExtractionResult:
    """Public entry: adaptive extractor with fail-closed honesty.

    When ``run_toolchain`` is True and Lake/Lean is available, projects that
    declare ``lpe_extract`` may produce ``.lpe/lean-extraction.json`` on the fly.
    """
    return AdaptiveLeanExtractor().extract_repository(
        repository,
        lean_paths=lean_paths,
        baseline_imports=baseline_imports,
        run_toolchain=run_toolchain,
    )
