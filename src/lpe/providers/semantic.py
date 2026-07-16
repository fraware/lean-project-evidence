"""Semantic evidence providers (AUDIT-010).

These checks are **heuristic / structural**, not Lean elaborator or intent-fidelity
oracles. PASS means a local structured protocol succeeded; UNKNOWN means evidence
was incomplete or missing — never silent PASS on absence.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from lpe import __version__
from lpe.hashing import sha256_text, sha256_value
from lpe.ids import new_id
from lpe.lean.extractor import (
    TOOLCHAIN_EXTRACTOR,
    build_dependency_graph,
    extract_lean_repository,
    impact_cone,
    lean_toolchain_available,
    resolve_changed_names_for_cone,
    signature_for_hash,
)
from lpe.lean.toolchain import has_lakefile
from lpe.models import (
    CandidateDescriptor,
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    ProjectContract,
    Provenance,
    Severity,
)

# Structured fixtures under contract tests/ (README alone does not count).
_STRUCTURED_SUFFIXES = {".lean", ".json", ".yaml", ".yml"}
_META_NAMES = {"readme.md", "readme.txt", ".gitkeep"}


def _provenance(
    *,
    check_input: dict[str, Any],
    started: datetime,
    finished: datetime,
    command: list[str] | None = None,
    output: Any | None = None,
) -> Provenance:
    return Provenance(
        tool="lean-project-evidence",
        tool_version=__version__,
        command=command or [],
        input_hash=sha256_value(check_input),
        output_hash=sha256_value(output) if output is not None else None,
        started_at=started,
        finished_at=finished,
        elapsed_ms=max(0, int((finished - started).total_seconds() * 1000)),
    )


def _finding(
    *,
    check_id: str,
    dimension: EvidenceDimension,
    status: FindingStatus,
    severity: Severity,
    summary: str,
    details: dict[str, Any],
    started: datetime,
    finished: datetime,
) -> EvidenceFinding:
    return EvidenceFinding(
        finding_id=new_id("finding"),
        check_id=check_id,
        check_version="0.1.0",
        dimension=dimension,
        status=status,
        severity=severity,
        summary=summary,
        details=details,
        provenance=_provenance(
            check_input={"check_id": check_id, "details": details},
            started=started,
            finished=finished,
            output={"status": status, "summary": summary},
        ),
    )


def _normalize_signature(signature: str) -> str:
    return " ".join(signature_for_hash(signature).split())


def short_name_in_line(full_name: str, line: str) -> bool:
    short = full_name.split(".")[-1]
    return short in line


def _contract_tests_root(project_path: Path) -> Path:
    return project_path / ".lean-project-contract" / "tests"


def _list_structured_fixtures(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if path.name.lower() in _META_NAMES:
            continue
        if path.suffix.lower() in _STRUCTURED_SUFFIXES:
            files.append(path)
    return files


def _load_structured_document(path: Path) -> dict[str, Any] | list[Any] | str | None:
    """Load JSON/YAML or return Lean source text. Failures return None."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, (dict, list)) else None
    if suffix in {".yaml", ".yml"}:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            return None
        return data if isinstance(data, (dict, list)) else None
    if suffix == ".lean":
        return text
    return None


def _example_document_ok(doc: dict[str, Any] | list[Any] | str, *, obligation_ids: list[str]) -> tuple[bool, str]:
    """Heuristic structural validity for an example fixture (not Lean execution)."""
    if isinstance(doc, str):
        if not doc.strip():
            return False, "empty lean example"
        if "sorry" in doc or "admit" in doc:
            return False, "lean example contains placeholder tokens"
        return True, "lean example present without placeholders"
    if isinstance(doc, list):
        if not doc:
            return False, "empty example list"
        return True, f"example list with {len(doc)} entries"
    # dict
    if not doc:
        return False, "empty example object"
    obl = doc.get("obligation_id") or doc.get("obligation_ids")
    if obl is not None:
        if isinstance(obl, str):
            obl_list = [obl]
        elif isinstance(obl, list):
            obl_list = [str(x) for x in obl]
        else:
            return False, "obligation_id must be string or list"
        if obligation_ids and not any(o in obligation_ids for o in obl_list):
            return False, f"obligation refs {obl_list} not in candidate obligations"
    if "expected" in doc or "distinguishes" in doc or "behavior" in doc or "name" in doc:
        return True, "structured example fields present"
    if "lean" in doc or "source" in doc or "snippet" in doc:
        return True, "example source field present"
    # Minimal viable: non-empty object with obligation binding.
    if obl is not None:
        return True, "obligation-bound example object"
    return False, "missing obligation binding or expected/behavior fields"


def _counterexample_document_ok(
    doc: dict[str, Any] | list[Any] | str,
) -> tuple[bool, str]:
    """Structural validity for a counterexample fixture."""
    if isinstance(doc, str):
        if not doc.strip():
            return False, "empty lean counterexample"
        # Counterexamples may deliberately include sorry/admit as the bad case.
        return True, "lean counterexample source present"
    if isinstance(doc, list):
        return (False, "empty counterexample list") if not doc else (True, f"{len(doc)} cases")
    if not doc:
        return False, "empty counterexample object"
    if doc.get("should_fail") is False and "expected_error" not in doc:
        return False, "should_fail=false without expected_error is ambiguous"
    if any(k in doc for k in ("should_fail", "expected_error", "invalid", "boundary", "name")):
        return True, "structured counterexample fields present"
    if "lean" in doc or "source" in doc or "snippet" in doc:
        return True, "counterexample source field present"
    return False, "missing should_fail/expected_error/invalid fields"


def _token_set(name: str) -> set[str]:
    parts = re.split(r"[.\s_/:-]+", name.lower())
    return {p for p in parts if p and len(p) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class StatementDiffProvider:
    """Structural statement/signature comparison from extracted declarations.

    Performs a real lexical signature hash comparison when Lean sources are
    available. Does not claim semantic/intent fidelity (AUDIT-010).
    """

    provider_id = "semantic.statement-diff"
    provider_version = "0.3.0"

    def collect(
        self,
        project_path: Path,
        contract: ProjectContract,
        candidate: CandidateDescriptor,
    ) -> list[EvidenceFinding]:
        del contract
        started = datetime.now(timezone.utc)
        changed = [d for d in candidate.changed_declarations if d.signature_changed]
        if not changed:
            finished = datetime.now(timezone.utc)
            return [
                _finding(
                    check_id="semantic.statement_diff",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.NOT_APPLICABLE,
                    severity=Severity.INFO,
                    summary="No signature changes require statement comparison",
                    details={},
                    started=started,
                    finished=finished,
                )
            ]

        extraction = extract_lean_repository(project_path)
        toolchain_complete = bool(
            getattr(extraction, "complete", False)
            and extraction.extractor == TOOLCHAIN_EXTRACTOR
        )
        by_name = {d.name: d for d in extraction.declarations}
        compared: list[dict[str, Any]] = []
        missing: list[str] = []
        mismatches: list[str] = []

        for decl in changed:
            extracted = by_name.get(decl.name)
            if extracted is None:
                short = decl.name.split(".")[-1]
                matches = [
                    d
                    for d in extraction.declarations
                    if d.name.endswith("." + short) or d.name == short
                ]
                if len(matches) == 1:
                    extracted = matches[0]
                else:
                    missing.append(decl.name)
                    continue

            candidate_sig = None
            if candidate.patch_text and decl.name.split(".")[-1] in candidate.patch_text:
                for line in candidate.patch_text.splitlines():
                    if line.startswith("+") and short_name_in_line(decl.name, line[1:]):
                        candidate_sig = _normalize_signature(line[1:])
                        break

            extracted_hash = extracted.signature_hash
            candidate_hash = sha256_text(candidate_sig) if candidate_sig else None
            entry = {
                "name": decl.name,
                "extracted_signature": extracted.signature,
                "extracted_signature_hash": extracted_hash,
                "candidate_signature": candidate_sig,
                "candidate_signature_hash": candidate_hash,
                "path": extracted.path,
                "toolchain_backed": toolchain_complete,
            }
            compared.append(entry)
            if candidate_hash and candidate_hash != extracted_hash:
                mismatches.append(decl.name)

        finished = datetime.now(timezone.utc)
        details: dict[str, Any] = {
            "compared": compared,
            "missing": missing,
            "mismatches": mismatches,
            "extractor": extraction.extractor,
            "complete": getattr(extraction, "complete", False),
            "toolchain_backed": toolchain_complete,
            "note": (
                "structural signature compare using toolchain hashes"
                if toolchain_complete
                else "structural signature compare only; not semantic intent fidelity"
            ),
        }

        if missing:
            return [
                _finding(
                    check_id="semantic.statement_diff",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L3,
                    summary=(
                        "Statement signature comparison incomplete; "
                        f"missing extracted decls: {missing}"
                    ),
                    details=details,
                    started=started,
                    finished=finished,
                )
            ]

        if mismatches:
            return [
                _finding(
                    check_id="semantic.statement_diff",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.FAIL,
                    severity=Severity.L3,
                    summary=(
                        "Structural signature mismatch between patch and "
                        f"extracted declarations: {mismatches}"
                    ),
                    details=details,
                    started=started,
                    finished=finished,
                )
            ]

        incomplete = [
            entry["name"]
            for entry in compared
            if not entry.get("candidate_signature_hash")
        ]
        if not compared or incomplete:
            return [
                _finding(
                    check_id="semantic.statement_diff",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L3,
                    summary=(
                        "Structural signature comparison unresolved; "
                        "candidate patch signatures incomplete"
                        + (f" for {incomplete}" if incomplete else "")
                    ),
                    details=details,
                    started=started,
                    finished=finished,
                )
            ]

        return [
            _finding(
                check_id="semantic.statement_diff",
                dimension=EvidenceDimension.SEMANTIC,
                status=FindingStatus.PASS,
                severity=Severity.INFO,
                summary=(
                    "Structural signature hashes match extracted declarations "
                    f"({len(compared)} compared"
                    + ("; toolchain-backed)" if toolchain_complete else "); intent fidelity not claimed)")
                ),
                details=details,
                started=started,
                finished=finished,
            )
        ]


class ExampleRunnerProvider:
    """Structured project-example protocol under contract tests/examples.

    Heuristic only: reads and structurally validates fixtures. Does **not**
    execute Lean/Lake. Missing or non-structured suites → UNKNOWN (never PASS).
    """

    provider_id = "semantic.example-runner"
    provider_version = "0.2.0"

    def collect(
        self,
        project_path: Path,
        contract: ProjectContract,
        candidate: CandidateDescriptor,
    ) -> list[EvidenceFinding]:
        del contract
        started = datetime.now(timezone.utc)
        examples_dir = _contract_tests_root(project_path) / "examples"
        protocol = {
            "kind": "structured-fixture-scan",
            "toolchain_backed": False,
            "note": "heuristic structural check; Lean examples are not executed",
        }

        if not examples_dir.is_dir():
            finished = datetime.now(timezone.utc)
            return [
                _finding(
                    check_id="semantic.project_examples",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L2,
                    summary="Project example suite path is not configured",
                    details={
                        "expected_path": str(examples_dir),
                        "protocol": protocol,
                        "attempted": True,
                    },
                    started=started,
                    finished=finished,
                )
            ]

        fixtures = _list_structured_fixtures(examples_dir)
        if not fixtures:
            finished = datetime.now(timezone.utc)
            return [
                _finding(
                    check_id="semantic.project_examples",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L2,
                    summary=(
                        "Project examples directory exists but has no structured "
                        "fixtures (README alone does not count)"
                    ),
                    details={
                        "examples_dir": str(examples_dir),
                        "fixture_count": 0,
                        "protocol": protocol,
                        "attempted": True,
                    },
                    started=started,
                    finished=finished,
                )
            ]

        results: list[dict[str, Any]] = []
        failures: list[str] = []
        load_errors: list[str] = []
        for path in fixtures:
            rel = str(path.relative_to(project_path)).replace("\\", "/")
            doc = _load_structured_document(path)
            if doc is None:
                load_errors.append(rel)
                results.append({"path": rel, "ok": False, "reason": "unreadable or invalid"})
                continue
            ok, reason = _example_document_ok(doc, obligation_ids=list(candidate.obligation_ids))
            results.append({"path": rel, "ok": ok, "reason": reason})
            if not ok:
                failures.append(rel)

        finished = datetime.now(timezone.utc)
        details: dict[str, Any] = {
            "examples_dir": str(examples_dir),
            "fixtures": results,
            "fixture_count": len(fixtures),
            "protocol": protocol,
            "attempted": True,
            "provenance_paths": [r["path"] for r in results],
        }

        if load_errors or failures:
            return [
                _finding(
                    check_id="semantic.project_examples",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.FAIL,
                    severity=Severity.L2,
                    summary=(
                        "Project example structural checks failed: "
                        f"{load_errors + failures}"
                    ),
                    details=details,
                    started=started,
                    finished=finished,
                )
            ]

        return [
            _finding(
                check_id="semantic.project_examples",
                dimension=EvidenceDimension.SEMANTIC,
                status=FindingStatus.PASS,
                severity=Severity.INFO,
                summary=(
                    f"Structured project examples validated ({len(fixtures)} fixtures); "
                    "Lean execution not performed"
                ),
                details=details,
                started=started,
                finished=finished,
            )
        ]


class CounterexampleProvider:
    """Counterexample protocol under contract tests/counterexamples.

    Records an explicit attempt. Missing fixtures → UNKNOWN. Present fixtures are
    evaluated structurally (heuristic, not elaborator-backed).
    """

    provider_id = "semantic.counterexample"
    provider_version = "0.2.0"

    def collect(
        self,
        project_path: Path,
        contract: ProjectContract,
        candidate: CandidateDescriptor,
    ) -> list[EvidenceFinding]:
        del contract, candidate
        started = datetime.now(timezone.utc)
        counter_dir = _contract_tests_root(project_path) / "counterexamples"
        protocol = {
            "kind": "structured-counterexample-scan",
            "toolchain_backed": False,
            "failure_policy": "UNKNOWN when missing or unreadable; FAIL on structural errors",
            "note": "heuristic structural check; counterexamples are not executed in Lean",
        }

        if not counter_dir.is_dir():
            finished = datetime.now(timezone.utc)
            return [
                _finding(
                    check_id="semantic.counterexamples",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L2,
                    summary="Counterexample directory missing; protocol attempt recorded",
                    details={
                        "counterexample_dir": str(counter_dir),
                        "protocol": protocol,
                        "attempted": True,
                        "outcome": "directory_missing",
                    },
                    started=started,
                    finished=finished,
                )
            ]

        fixtures = _list_structured_fixtures(counter_dir)
        if not fixtures:
            finished = datetime.now(timezone.utc)
            return [
                _finding(
                    check_id="semantic.counterexamples",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L2,
                    summary=(
                        "Counterexample protocol attempted; no structured fixtures present"
                    ),
                    details={
                        "counterexample_dir": str(counter_dir),
                        "protocol": protocol,
                        "attempted": True,
                        "outcome": "no_fixtures",
                        "fixture_count": 0,
                    },
                    started=started,
                    finished=finished,
                )
            ]

        results: list[dict[str, Any]] = []
        failures: list[str] = []
        load_errors: list[str] = []
        for path in fixtures:
            rel = str(path.relative_to(project_path)).replace("\\", "/")
            doc = _load_structured_document(path)
            if doc is None:
                load_errors.append(rel)
                results.append({"path": rel, "ok": False, "reason": "unreadable or invalid"})
                continue
            ok, reason = _counterexample_document_ok(doc)
            results.append({"path": rel, "ok": ok, "reason": reason})
            if not ok:
                failures.append(rel)

        finished = datetime.now(timezone.utc)
        details: dict[str, Any] = {
            "counterexample_dir": str(counter_dir),
            "fixtures": results,
            "fixture_count": len(fixtures),
            "protocol": protocol,
            "attempted": True,
            "provenance_paths": [r["path"] for r in results],
        }

        if load_errors or failures:
            return [
                _finding(
                    check_id="semantic.counterexamples",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.FAIL,
                    severity=Severity.L2,
                    summary=(
                        "Counterexample structural checks failed: "
                        f"{load_errors + failures}"
                    ),
                    details=details,
                    started=started,
                    finished=finished,
                )
            ]

        return [
            _finding(
                check_id="semantic.counterexamples",
                dimension=EvidenceDimension.SEMANTIC,
                status=FindingStatus.PASS,
                severity=Severity.INFO,
                summary=(
                    f"Structured counterexamples validated ({len(fixtures)} fixtures); "
                    "Lean execution not performed"
                ),
                details=details,
                started=started,
                finished=finished,
            )
        ]


class DuplicateRetrievalProvider:
    """Local corpus near-duplicate scan over ``.lean`` declaration names/signatures.

    Uses lexical Jaccard on name tokens and exact signature-hash proximity.
    Empty corpus or no candidate decls → UNKNOWN. Heuristic only (not embedding ML).
    """

    provider_id = "semantic.duplicate-retrieval"
    provider_version = "0.3.0"

    def collect(
        self,
        project_path: Path,
        contract: ProjectContract,
        candidate: CandidateDescriptor,
    ) -> list[EvidenceFinding]:
        del contract
        started = datetime.now(timezone.utc)
        names = [d.name for d in candidate.changed_declarations]
        if not names:
            finished = datetime.now(timezone.utc)
            return [
                _finding(
                    check_id="semantic.duplicate_retrieval",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.NOT_APPLICABLE,
                    severity=Severity.INFO,
                    summary="No changed declarations to scan for near-duplicates",
                    details={
                        "protocol": {
                            "kind": "local-lexical-jaccard",
                            "toolchain_backed": False,
                            "note": "name-token Jaccard + signature-hash equality; not embedding retrieval",
                        },
                        "attempted": True,
                    },
                    started=started,
                    finished=finished,
                )
            ]

        extraction = extract_lean_repository(project_path)
        toolchain_complete = bool(
            getattr(extraction, "complete", False)
            and extraction.extractor == TOOLCHAIN_EXTRACTOR
        )
        protocol = {
            "kind": "local-lexical-jaccard",
            "toolchain_backed": toolchain_complete,
            "note": (
                "name-token Jaccard + toolchain signature-hash equality"
                if toolchain_complete
                else "name-token Jaccard + signature-hash equality; not embedding retrieval"
            ),
        }

        corpus = list(extraction.declarations)
        if not corpus:
            finished = datetime.now(timezone.utc)
            return [
                _finding(
                    check_id="semantic.duplicate_retrieval",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L2,
                    summary="Duplicate retrieval unresolved: empty local Lean corpus",
                    details={
                        "candidate_declarations": names,
                        "corpus_size": 0,
                        "protocol": protocol,
                        "attempted": True,
                        "extractor": extraction.extractor,
                        "toolchain_backed": toolchain_complete,
                    },
                    started=started,
                    finished=finished,
                )
            ]

        # Prefer toolchain signature hashes from extraction; fall back to patch lines.
        candidate_sig_hashes: dict[str, str | None] = {}
        by_name = {d.name: d for d in corpus}
        for decl in candidate.changed_declarations:
            sig_hash: str | None = None
            extracted = by_name.get(decl.name)
            if extracted is None:
                short = decl.name.split(".")[-1]
                matches = [
                    d
                    for d in corpus
                    if d.name.endswith("." + short) or d.name == short
                ]
                if len(matches) == 1:
                    extracted = matches[0]
            if toolchain_complete and extracted is not None and extracted.signature_hash:
                sig_hash = extracted.signature_hash
            elif candidate.patch_text:
                for line in candidate.patch_text.splitlines():
                    if line.startswith("+") and short_name_in_line(decl.name, line[1:]):
                        sig_hash = sha256_text(_normalize_signature(line[1:]))
                        break
            candidate_sig_hashes[decl.name] = sig_hash

        closest: list[dict[str, Any]] = []
        for decl_name in names:
            query_tokens = _token_set(decl_name)
            query_hash = candidate_sig_hashes.get(decl_name)
            best: dict[str, Any] | None = None
            for entry in corpus:
                if entry.name == decl_name:
                    continue
                name_score = _jaccard(query_tokens, _token_set(entry.name))
                hash_match = bool(query_hash and query_hash == entry.signature_hash)
                # Toolchain hash equality is authoritative proximity.
                score = max(name_score, 1.0 if hash_match else 0.0)
                if best is None or score > float(best["score"]):
                    best = {
                        "query": decl_name,
                        "match_name": entry.name,
                        "match_path": entry.path,
                        "match_signature": entry.signature,
                        "match_signature_hash": entry.signature_hash,
                        "name_jaccard": round(name_score, 4),
                        "signature_hash_match": hash_match,
                        "score": round(score, 4),
                        "toolchain_backed": toolchain_complete,
                    }
            if best is not None:
                closest.append(best)

        finished = datetime.now(timezone.utc)
        high = [c for c in closest if float(c["score"]) >= 0.5]
        details: dict[str, Any] = {
            "candidate_declarations": names,
            "corpus_size": len(corpus),
            "closest": closest,
            "high_similarity": high,
            "protocol": protocol,
            "attempted": True,
            "extractor": extraction.extractor,
            "complete": getattr(extraction, "complete", False),
            "toolchain_backed": toolchain_complete,
            "provenance": {
                "paths": sorted({c["match_path"] for c in closest if c.get("match_path")}),
            },
        }

        if high:
            return [
                _finding(
                    check_id="semantic.duplicate_retrieval",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.WARN,
                    severity=Severity.L2,
                    summary=(
                        "Near-duplicate declarations found in local corpus "
                        f"({len(high)} high-similarity matches)"
                        + ("; toolchain hash proximity" if toolchain_complete else "; heuristic only")
                    ),
                    details=details,
                    started=started,
                    finished=finished,
                )
            ]

        return [
            _finding(
                check_id="semantic.duplicate_retrieval",
                dimension=EvidenceDimension.SEMANTIC,
                status=FindingStatus.PASS,
                severity=Severity.INFO,
                summary=(
                    f"Local corpus scanned ({len(corpus)} decls); no high-similarity "
                    + (
                        "near-duplicates (toolchain hashes)"
                        if toolchain_complete
                        else "near-duplicates (lexical/heuristic)"
                    )
                ),
                details=details,
                started=started,
                finished=finished,
            )
        ]


class DownstreamReplacementProvider:
    """Downstream replacement findings from impact cone + successor declarations.

    When the cone is empty, status is UNKNOWN. Heuristic (regex-stub) cones emit
    WARN with successor inventory only.

    Toolchain-complete cones attempt a structured replacement check:

    1. Signature-hash integrity for each successor (``sha256(signature)``).
    2. When Lake is available, compile selected dependent ``.lean`` modules
       (capped) via ``lake env lean``.

    Fail-closed: if neither check can run, status is UNKNOWN (never silent PASS).
    """

    provider_id = "semantic.downstream-replacement"
    provider_version = "0.3.0"
    _MAX_LAKE_MODULES = 8

    def collect(
        self,
        project_path: Path,
        contract: ProjectContract,
        candidate: CandidateDescriptor,
    ) -> list[EvidenceFinding]:
        del contract
        started = datetime.now(timezone.utc)
        raw_names = {d.name for d in candidate.changed_declarations}
        protocol = {
            "kind": "impact-cone-successor-replacement",
            "note": (
                "toolchain cones attempt signature-hash + optional Lake compile "
                "of dependents; regex-stub cones are heuristic inventory only"
            ),
        }

        if not raw_names:
            finished = datetime.now(timezone.utc)
            return [
                _finding(
                    check_id="downstream.replacement_tests",
                    dimension=EvidenceDimension.DOWNSTREAM,
                    status=FindingStatus.NOT_APPLICABLE,
                    severity=Severity.INFO,
                    summary="No changed declarations for downstream replacement analysis",
                    details={"obligation_ids": candidate.obligation_ids, "protocol": protocol},
                    started=started,
                    finished=finished,
                )
            ]

        extraction = extract_lean_repository(project_path)
        changed_names = resolve_changed_names_for_cone(
            candidate.changed_declarations, extraction
        )
        graph = build_dependency_graph(extraction)
        cone = impact_cone(graph, changed=changed_names)
        toolchain_complete = bool(
            getattr(extraction, "complete", False)
            and extraction.extractor == TOOLCHAIN_EXTRACTOR
            and not extraction.errors
        )

        if not cone:
            finished = datetime.now(timezone.utc)
            return [
                _finding(
                    check_id="downstream.replacement_tests",
                    dimension=EvidenceDimension.DOWNSTREAM,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L2,
                    summary=(
                        "Downstream replacement unresolved: impact cone empty "
                        "(no successor declarations found)"
                    ),
                    details={
                        "obligation_ids": candidate.obligation_ids,
                        "changed": sorted(changed_names),
                        "impact_cone": [],
                        "extractor": extraction.extractor,
                        "complete": getattr(extraction, "complete", False),
                        "toolchain_backed": toolchain_complete,
                        "protocol": protocol,
                        "attempted": True,
                        "replacement_check": "not_applicable_empty_cone",
                    },
                    started=started,
                    finished=finished,
                )
            ]

        by_name = {d.name: d for d in extraction.declarations}
        successors: list[dict[str, Any]] = []
        for name in sorted(cone):
            decl = by_name.get(name)
            successors.append(
                {
                    "name": name,
                    "kind": decl.kind if decl else None,
                    "path": decl.path if decl else None,
                    "signature": decl.signature if decl else None,
                    "signature_hash": decl.signature_hash if decl else None,
                }
            )

        details: dict[str, Any] = {
            "obligation_ids": candidate.obligation_ids,
            "changed": sorted(changed_names),
            "impact_cone": sorted(cone),
            "successors": successors,
            "successor_count": len(successors),
            "extractor": extraction.extractor,
            "complete": getattr(extraction, "complete", False),
            "toolchain_backed": toolchain_complete,
            "protocol": protocol,
            "attempted": True,
            "graph_semantics": "dependee->depender (downstream impact)",
        }

        if not toolchain_complete:
            finished = datetime.now(timezone.utc)
            details["replacement_check"] = "regex_stub_inventory_only"
            return [
                _finding(
                    check_id="downstream.replacement_tests",
                    dimension=EvidenceDimension.DOWNSTREAM,
                    status=FindingStatus.WARN,
                    severity=Severity.L2,
                    summary=(
                        f"Downstream replacement cone estimated ({len(successors)} successors) "
                        "via regex-stub; not elaborator-complete"
                    ),
                    details=details,
                    started=started,
                    finished=finished,
                )
            ]

        hash_report = _successor_hash_integrity(successors)
        details["signature_hash_check"] = hash_report
        lake_report = _try_compile_successor_modules(
            project_path,
            successors,
            max_modules=self._MAX_LAKE_MODULES,
        )
        details["lake_dependent_check"] = lake_report

        finished = datetime.now(timezone.utc)

        if not hash_report["ran"]:
            details["replacement_check"] = "unavailable"
            return [
                _finding(
                    check_id="downstream.replacement_tests",
                    dimension=EvidenceDimension.DOWNSTREAM,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L2,
                    summary=(
                        "Downstream replacement unresolved: could not run "
                        "signature-hash check on toolchain successors"
                    ),
                    details=details,
                    started=started,
                    finished=finished,
                )
            ]

        if not hash_report["ok"]:
            details["replacement_check"] = "signature_hash_failed"
            return [
                _finding(
                    check_id="downstream.replacement_tests",
                    dimension=EvidenceDimension.DOWNSTREAM,
                    status=FindingStatus.FAIL,
                    severity=Severity.L3,
                    summary=(
                        "Downstream successor signature hashes failed integrity check "
                        f"({hash_report['mismatched']} mismatched / "
                        f"{hash_report['missing_hash']} missing)"
                    ),
                    details=details,
                    started=started,
                    finished=finished,
                )
            ]

        if lake_report["attempted"]:
            if lake_report["ok"]:
                details["replacement_check"] = "signature_hash+lake_env"
                return [
                    _finding(
                        check_id="downstream.replacement_tests",
                        dimension=EvidenceDimension.DOWNSTREAM,
                        status=FindingStatus.PASS,
                        severity=Severity.INFO,
                        summary=(
                            f"Downstream replacement verified for {len(successors)} "
                            f"successors (signature hashes + Lake env on "
                            f"{lake_report['modules_checked']} modules)"
                        ),
                        details=details,
                        started=started,
                        finished=finished,
                    )
                ]
            details["replacement_check"] = "lake_env_failed"
            return [
                _finding(
                    check_id="downstream.replacement_tests",
                    dimension=EvidenceDimension.DOWNSTREAM,
                    status=FindingStatus.FAIL,
                    severity=Severity.L3,
                    summary=(
                        "Downstream dependent modules failed Lake compile check: "
                        + (lake_report.get("error") or "non-zero exit")
                    ),
                    details=details,
                    started=started,
                    finished=finished,
                )
            ]

        # Lake not runnable — hash check alone is structured but incomplete.
        # Fail closed: UNKNOWN rather than PASS without an executable check.
        if lake_report.get("reason") == "lake_unavailable":
            details["replacement_check"] = "hash_only_lake_unavailable"
            return [
                _finding(
                    check_id="downstream.replacement_tests",
                    dimension=EvidenceDimension.DOWNSTREAM,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L2,
                    summary=(
                        f"Successor signature hashes OK ({len(successors)}), but Lake "
                        "compile of dependents could not run (fail-closed UNKNOWN)"
                    ),
                    details=details,
                    started=started,
                    finished=finished,
                )
            ]

        details["replacement_check"] = "signature_hash"
        return [
            _finding(
                check_id="downstream.replacement_tests",
                dimension=EvidenceDimension.DOWNSTREAM,
                status=FindingStatus.PASS,
                severity=Severity.INFO,
                summary=(
                    f"Downstream replacement signature hashes verified for "
                    f"{len(successors)} toolchain successors "
                    f"(no Lake modules selected: {lake_report.get('reason')})"
                ),
                details=details,
                started=started,
                finished=finished,
            )
        ]


def _successor_hash_integrity(successors: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify each successor's signature_hash matches ``sha256(signature)``."""
    checked = 0
    mismatched = 0
    missing_hash = 0
    missing_signature = 0
    for item in successors:
        sig = item.get("signature")
        digest = item.get("signature_hash")
        if not sig:
            missing_signature += 1
            continue
        checked += 1
        expected = sha256_text(str(sig))
        if not digest:
            missing_hash += 1
            continue
        if digest != expected:
            mismatched += 1
    ok = (
        checked > 0
        and mismatched == 0
        and missing_hash == 0
        and missing_signature == 0
    )
    return {
        "ran": len(successors) > 0 and checked > 0,
        "ok": ok,
        "checked": checked,
        "mismatched": mismatched,
        "missing_hash": missing_hash,
        "missing_signature": missing_signature,
    }


def _try_compile_successor_modules(
    project_path: Path,
    successors: list[dict[str, Any]],
    *,
    max_modules: int,
) -> dict[str, Any]:
    """Compile unique successor ``.lean`` paths with ``lake env lean`` when possible."""
    import shutil
    import subprocess

    lake = shutil.which("lake")
    if lake is None or not lean_toolchain_available(project_path) or not has_lakefile(
        project_path
    ):
        return {
            "attempted": False,
            "ok": False,
            "reason": "lake_unavailable",
            "modules_checked": 0,
            "modules": [],
        }

    modules: list[str] = []
    seen: set[str] = set()
    for item in successors:
        rel = item.get("path")
        if not rel or not isinstance(rel, str):
            continue
        normalized = rel.replace("\\", "/")
        if not normalized.endswith(".lean"):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        modules.append(normalized)
        if len(modules) >= max_modules:
            break

    if not modules:
        return {
            "attempted": False,
            "ok": False,
            "reason": "no_successor_lean_paths",
            "modules_checked": 0,
            "modules": [],
        }

    failures: list[dict[str, Any]] = []
    for rel in modules:
        lean_file = project_path / rel
        if not lean_file.is_file():
            failures.append({"module": rel, "error": "file_missing"})
            continue
        try:
            proc = subprocess.run(
                [lake, "env", "lean", rel.replace("\\", "/")],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            failures.append({"module": rel, "error": str(exc)})
            continue
        if proc.returncode != 0:
            failures.append(
                {
                    "module": rel,
                    "exit_code": proc.returncode,
                    "stderr": (proc.stderr or proc.stdout or "")[:400],
                }
            )

    if failures:
        return {
            "attempted": True,
            "ok": False,
            "reason": "compile_failed",
            "modules_checked": len(modules),
            "modules": modules,
            "failures": failures,
            "error": failures[0].get("error")
            or failures[0].get("stderr")
            or "non-zero exit",
        }

    return {
        "attempted": True,
        "ok": True,
        "reason": "lake_env_ok",
        "modules_checked": len(modules),
        "modules": modules,
    }
