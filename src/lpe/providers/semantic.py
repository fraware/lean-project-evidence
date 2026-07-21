"""Semantic evidence providers (AUDIT-010).

These checks are **heuristic / structural**, not Lean elaborator or intent-fidelity
oracles. PASS means a local structured protocol succeeded; UNKNOWN means evidence
was incomplete or missing — never silent PASS on absence.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from lpe import __version__
from lpe.evidence.payloads import (
    FindingPayload,
    executed_check_payload,
    opaque_finding_payload,
    structural_diff_payload,
)
from lpe.execution.protocol import ValidatedCommand
from lpe.hashing import sha256_text, sha256_value
from lpe.lean.extractor import (
    TOOLCHAIN_EXTRACTOR,
    build_dependency_graph,
    extract_lean_repository,
    impact_cone,
    lean_toolchain_available,
    resolve_changed_names_detailed,
    signature_for_hash,
)
from lpe.lean.toolchain import has_lakefile
from lpe.models import (
    EvidenceBasis,
    EvidenceCoverage,
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    Provenance,
    Severity,
    SubjectReference,
)
from lpe.providers.base import ProviderContext, ProviderResult
from lpe.workspace.manager import make_stable_finding_id

# Structured fixtures under contract tests/ (README alone does not count).
_STRUCTURED_SUFFIXES = {".lean", ".json", ".yaml", ".yml"}
_META_NAMES = {"readme.md", "readme.txt", ".gitkeep"}


def _provider_result(
    provider: Any,
    context: ProviderContext,
    findings: list[EvidenceFinding],
    *,
    started: datetime,
    finished: datetime,
    status: str = "COMPLETED",
    artifact_refs: list[Any] | None = None,
) -> ProviderResult:
    return ProviderResult(
        provider_id=str(provider.provider_id),
        provider_version=str(provider.provider_version),
        snapshot_fingerprint=context.snapshot_fingerprint,
        findings=findings,
        artifact_refs=list(artifact_refs or []),
        started_at=started,
        finished_at=finished,
        status=status,  # type: ignore[arg-type]
    )


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


def _statement_diff_payload(details: dict[str, Any]) -> FindingPayload:
    return structural_diff_payload(details)


def _downstream_replacement_payload(check_id: str, details: dict[str, Any]) -> FindingPayload:
    """Prefer executed payload when Lake/signature checks ran; else structural."""
    lake = details.get("lake_dependent_check")
    hash_check = details.get("signature_hash_check")
    if isinstance(lake, dict) and lake.get("attempted"):
        return executed_check_payload(check_id, details)
    if isinstance(hash_check, dict) and hash_check.get("ran"):
        return executed_check_payload(check_id, details)
    if details.get("changed") or details.get("impact_cone") is not None:
        return structural_diff_payload(details)
    return opaque_finding_payload(details)


def _default_semantic_payload(check_id: str, details: dict[str, Any]) -> FindingPayload:
    if check_id == "semantic.statement_diff":
        return _statement_diff_payload(details)
    if check_id == "downstream.replacement_tests":
        return _downstream_replacement_payload(check_id, details)
    return opaque_finding_payload(details)


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
    basis: EvidenceBasis | None = None,
    coverage: EvidenceCoverage | None = None,
    subject_refs: list[SubjectReference] | None = None,
    required_basis: EvidenceBasis | None = None,
    payload: FindingPayload | None = None,
) -> EvidenceFinding:
    check_version = "0.2.0"
    typed_payload: FindingPayload = (
        payload if payload is not None else _default_semantic_payload(check_id, details)
    )
    return EvidenceFinding(
        finding_id=make_stable_finding_id(
            check_id=check_id,
            dimension=dimension,
            details=details,
            check_version=check_version,
        ),
        check_id=check_id,
        check_version=check_version,
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
        basis=basis,
        coverage=coverage,
        subject_refs=list(subject_refs or []),
        payload=typed_payload,
        required_basis=required_basis,
    )


def _normalize_signature(signature: str) -> str:
    return " ".join(signature_for_hash(signature).split())


def parse_signature_structure(signature: str) -> dict[str, str | None]:
    """Split a Lean-ish declaration header into binder/domain/conclusion fields.

    Heuristic structural parse only — not an elaborator. Used when toolchain
    extraction exposes signature text (ISSUE-029 fixture depth).
    """
    normalized = _normalize_signature(signature)
    # Drop leading kind keyword when present.
    rest = normalized
    for kind in (
        "theorem",
        "lemma",
        "def",
        "abbrev",
        "instance",
        "structure",
        "class",
        "axiom",
        "opaque",
    ):
        prefix = kind + " "
        if rest.lower().startswith(prefix):
            rest = rest[len(prefix) :]
            break
    # Name is first token; remainder may include binders then ``:`` type.
    parts = rest.split(None, 1)
    name = parts[0] if parts else None
    after_name = parts[1] if len(parts) > 1 else ""
    binders: str | None = None
    domain: str | None = None
    conclusion: str | None = None
    if ":" in after_name:
        before_colon, after_colon = after_name.split(":", 1)
        binders = before_colon.strip() or None
        type_part = after_colon.strip()
        # Arrow conclusions: treat last ``→`` / ``->`` segment as conclusion.
        for arrow in (" → ", " -> ", "→", "->"):
            if arrow in type_part:
                idx = type_part.rfind(arrow)
                domain = type_part[:idx].strip() or None
                conclusion = type_part[idx + len(arrow) :].strip() or None
                break
        else:
            conclusion = type_part or None
    else:
        binders = after_name.strip() or None
    return {
        "decl_name": name,
        "binders": binders,
        "domain": domain,
        "conclusion": conclusion,
        "normalized_signature": normalized,
    }


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


def _redact_log_snippet(text: str, *, limit: int = 400) -> str:
    """Trim and lightly redact obvious secret-shaped tokens from Lake logs."""
    from lpe.execution.redact import redact_secrets

    cleaned = redact_secrets(text or "")
    return cleaned[:limit]


def _try_lake_env_lean(context: ProviderContext, rel_lean: str) -> dict[str, Any]:
    """Run ``lake env lean <rel>`` via the workspace executor (CLOSURE-003)."""

    profile = context.resource_profile_for("semantic.example-runner")
    allowlist = list(context.contract.project.execution.environment_allowlist)
    try:
        command = ValidatedCommand.from_argv(["lake", "env", "lean", rel_lean.replace("\\", "/")])
        result = context.workspace.executor.run(
            workspace=context.workspace,
            command=command,
            resource_profile=profile,
            environment_allowlist=allowlist,
        )
    except (OSError, TimeoutError, ValueError) as exc:
        return {
            "ok": False,
            "reason": "lake_invoke_error",
            "exit_code": None,
            "stderr": _redact_log_snippet(str(exc)),
        }
    ok = result.exit_code == 0 and not result.timed_out
    if result.timed_out:
        return {
            "ok": False,
            "reason": "lake_invoke_error",
            "exit_code": result.exit_code,
            "stderr": _redact_log_snippet(result.stderr or "timed out"),
        }
    return {
        "ok": ok,
        "reason": "lake_env_ok" if ok else "lake_env_failed",
        "exit_code": result.exit_code,
        "stderr": _redact_log_snippet(result.stderr or result.stdout or ""),
    }


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


def _example_document_ok(
    doc: dict[str, Any] | list[Any] | str,
    *,
    obligation_ids: list[str],
) -> tuple[bool, str]:
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
    """Statement comparison preferring elaborated base/head types (§11.1).

    Never treats a single patch line as authoritative when elaborated snapshots
    exist. Does not claim semantic/intent fidelity.
    """

    provider_id = "semantic.statement-diff"
    provider_version = "0.2.0"
    required_basis = EvidenceBasis.ELABORATOR_EXTRACTED

    def collect(self, context: ProviderContext) -> ProviderResult:
        started = datetime.now(UTC)
        candidate = context.candidate
        project_path = context.candidate_path
        changed = [d for d in candidate.changed_declarations if d.signature_changed]
        if not changed:
            finished = datetime.now(UTC)
            return _provider_result(
                self,
                context,
                [
                    _finding(
                        check_id="semantic.statement_diff",
                        dimension=EvidenceDimension.SEMANTIC,
                        status=FindingStatus.NOT_APPLICABLE,
                        severity=Severity.INFO,
                        summary="No signature changes require statement comparison",
                        details={},
                        started=started,
                        finished=finished,
                        basis=EvidenceBasis.ELABORATOR_EXTRACTED,
                        coverage=EvidenceCoverage(
                            requested_subject_count=0,
                            evaluated_subject_count=0,
                            complete_for_declared_scope=True,
                        ),
                    )
                ],
                started=started,
                finished=finished,
            )

        head_extraction = context.candidate_extraction or extract_lean_repository(project_path)
        base_extraction = context.base_extraction
        toolchain_complete = bool(
            getattr(head_extraction, "complete", False)
            and head_extraction.extractor == TOOLCHAIN_EXTRACTOR
        )
        base_complete = bool(
            base_extraction is not None
            and getattr(base_extraction, "complete", False)
            and getattr(base_extraction, "extractor", None) == TOOLCHAIN_EXTRACTOR
        )
        head_by_name = {d.name: d for d in head_extraction.declarations}
        base_by_name = {d.name: d for d in base_extraction.declarations} if base_extraction else {}
        compared: list[dict[str, Any]] = []
        missing: list[str] = []
        mismatches: list[str] = []
        used_patch_fallback = False

        def _resolve(by_name: dict[str, Any], decls: list[Any], name: str) -> Any | None:
            extracted = by_name.get(name)
            if extracted is not None:
                return extracted
            short = name.split(".")[-1]
            matches = [d for d in decls if d.name.endswith("." + short) or d.name == short]
            return matches[0] if len(matches) == 1 else None

        for decl in changed:
            head_decl = _resolve(head_by_name, list(head_extraction.declarations), decl.name)
            if head_decl is None:
                missing.append(decl.name)
                continue

            base_decl = (
                _resolve(base_by_name, list(base_extraction.declarations), decl.name)
                if base_extraction is not None
                else None
            )

            # Prefer elaborated types; patch line is never authoritative when present.
            head_sig = getattr(head_decl, "signature", None)
            head_hash = getattr(head_decl, "signature_hash", None)
            base_sig = getattr(base_decl, "signature", None) if base_decl else None
            base_hash = getattr(base_decl, "signature_hash", None) if base_decl else None

            patch_sig = None
            if (
                not (toolchain_complete and head_hash)
                and candidate.patch_text
                and decl.name.split(".")[-1] in candidate.patch_text
            ):
                for line in candidate.patch_text.splitlines():
                    if line.startswith("+") and short_name_in_line(decl.name, line[1:]):
                        patch_sig = _normalize_signature(line[1:])
                        used_patch_fallback = True
                        break

            authority = (
                "elaborated_pair"
                if base_complete and toolchain_complete and base_hash and head_hash
                else ("elaborated_head" if toolchain_complete and head_hash else "patch_fallback")
            )
            structure_head = parse_signature_structure(str(head_sig or ""))
            structure_base = parse_signature_structure(str(base_sig or "")) if base_sig else None
            entry = {
                "name": decl.name,
                "resolved_name": head_decl.name,
                "authority": authority,
                "base_signature": base_sig,
                "base_signature_hash": base_hash,
                "head_signature": head_sig,
                "head_signature_hash": head_hash,
                "patch_signature_fallback": patch_sig,
                "path": getattr(head_decl, "path", None),
                "toolchain_backed": toolchain_complete,
                "structure_head": structure_head,
                "structure_base": structure_base,
                "binder_domain_conclusion": {
                    "head": structure_head,
                    "base": structure_base,
                },
            }
            compared.append(entry)
            if authority == "elaborated_pair" and base_hash != head_hash:
                # Type changed between base and head — expected for signature_changed;
                # record as compared difference, not integrity mismatch vs patch.
                entry["type_changed"] = True
            elif authority == "patch_fallback" and patch_sig:
                if sha256_text(patch_sig) != head_hash:
                    mismatches.append(decl.name)

        finished = datetime.now(UTC)
        details: dict[str, Any] = {
            "compared": compared,
            "missing": missing,
            "mismatches": mismatches,
            "extractor": head_extraction.extractor,
            "complete": getattr(head_extraction, "complete", False),
            "toolchain_backed": toolchain_complete,
            "base_elaborated": base_complete,
            "used_patch_fallback": used_patch_fallback,
            "note": (
                "elaborated base/head types are authoritative when available; "
                "patch lines are never authority when elaborations exist (§11.1)"
            ),
        }
        coverage = EvidenceCoverage(
            requested_subject_count=len(changed),
            evaluated_subject_count=len(compared),
            excluded_subject_count=len(missing),
            exclusion_reasons=[f"missing:{n}" for n in missing],
            complete_for_declared_scope=not missing,
        )
        basis = (
            EvidenceBasis.ELABORATOR_EXTRACTED
            if toolchain_complete
            else EvidenceBasis.STRUCTURAL_COMPARISON
        )

        if missing:
            return _provider_result(
                self,
                context,
                [
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
                        basis=basis,
                        coverage=coverage,
                    )
                ],
                started=started,
                finished=finished,
            )

        if mismatches:
            return _provider_result(
                self,
                context,
                [
                    _finding(
                        check_id="semantic.statement_diff",
                        dimension=EvidenceDimension.SEMANTIC,
                        status=FindingStatus.FAIL,
                        severity=Severity.L3,
                        summary=(
                            "Structural signature mismatch between patch fallback and "
                            f"extracted declarations: {mismatches}"
                        ),
                        details=details,
                        started=started,
                        finished=finished,
                        basis=basis,
                        coverage=coverage,
                    )
                ],
                started=started,
                finished=finished,
            )

        if toolchain_complete or (compared and not used_patch_fallback):
            status = FindingStatus.PASS
            summary = f"Elaborated statement comparison complete ({len(compared)} decls" + (
                "; base+head pair)" if base_complete else "; head only)"
            )
        elif used_patch_fallback:
            status = FindingStatus.UNKNOWN
            summary = (
                "Statement comparison unresolved: elaborated types unavailable; "
                "patch-line fallback is not authoritative"
            )
        else:
            status = FindingStatus.UNKNOWN
            summary = "Statement comparison unresolved; no elaborated signatures"

        return _provider_result(
            self,
            context,
            [
                _finding(
                    check_id="semantic.statement_diff",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=status,
                    severity=Severity.INFO if status is FindingStatus.PASS else Severity.L3,
                    summary=summary,
                    details=details,
                    started=started,
                    finished=finished,
                    basis=basis,
                    coverage=coverage,
                    subject_refs=[
                        SubjectReference(kind="declaration", ref=d.name) for d in changed
                    ],
                    required_basis=EvidenceBasis.ELABORATOR_EXTRACTED
                    if status is FindingStatus.PASS and toolchain_complete
                    else None,
                )
            ],
            started=started,
            finished=finished,
        )


# ExampleRunnerProvider / CounterexampleProvider live in fixture_runners (CLOSURE-013).
from lpe.providers.fixture_runners import (  # noqa: E402
    CounterexampleProvider,
    ExampleRunnerProvider,
)

__all__ = [
    "CounterexampleProvider",
    "DownstreamReplacementProvider",
    "DuplicateRetrievalProvider",
    "ExampleRunnerProvider",
    "StatementDiffProvider",
    "parse_signature_structure",
    "short_name_in_line",
]


class DuplicateRetrievalProvider:
    """Local corpus near-duplicate scan over ``.lean`` declaration names/signatures.

    Uses lexical Jaccard on name tokens and exact signature-hash proximity.
    Empty corpus or no candidate decls → UNKNOWN. Heuristic only (not embedding ML).
    """

    provider_id = "semantic.duplicate-retrieval"
    provider_version = "0.3.0"

    def collect(self, context: ProviderContext) -> ProviderResult:
        started = datetime.now(UTC)
        candidate = context.candidate
        project_path = context.candidate_path
        names = [d.name for d in candidate.changed_declarations]
        if not names:
            finished = datetime.now(UTC)
            return _provider_result(
                self,
                context,
                [
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
                                "note": (
                                    "name-token Jaccard + signature-hash equality; "
                                    "not embedding retrieval"
                                ),
                            },
                            "attempted": True,
                        },
                        started=started,
                        finished=finished,
                    )
                ],
                started=started,
                finished=finished,
            )

        extraction = context.candidate_extraction or extract_lean_repository(project_path)
        toolchain_complete = bool(
            getattr(extraction, "complete", False) and extraction.extractor == TOOLCHAIN_EXTRACTOR
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
            finished = datetime.now(UTC)
            return _provider_result(
                self,
                context,
                [
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
                ],
                started=started,
                finished=finished,
            )

        # Prefer toolchain signature hashes from extraction; fall back to patch lines.
        candidate_sig_hashes: dict[str, str | None] = {}
        by_name = {d.name: d for d in corpus}
        for decl in candidate.changed_declarations:
            sig_hash: str | None = None
            extracted = by_name.get(decl.name)
            if extracted is None:
                short = decl.name.split(".")[-1]
                matches = [d for d in corpus if d.name.endswith("." + short) or d.name == short]
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

        finished = datetime.now(UTC)
        exact_matches = [c for c in closest if c.get("signature_hash_match")]
        heuristic_matches = [
            c for c in closest if float(c["score"]) >= 0.5 and not c.get("signature_hash_match")
        ]
        high = exact_matches + heuristic_matches
        missing_hashes = [
            name
            for name, digest in candidate_sig_hashes.items()
            if toolchain_complete and not digest
        ]
        details: dict[str, Any] = {
            "candidate_declarations": names,
            "corpus_size": len(corpus),
            "closest": closest,
            "exact_type_hash_matches": exact_matches,
            "heuristic_token_matches": heuristic_matches,
            "high_similarity": high,
            "match_classes": {
                "exact_elaborated_type_hash": len(exact_matches),
                "token_similarity": len(heuristic_matches),
                "alpha_equivalent": 0,
                "mutual_implication": 0,
                "repository_location": 0,
                "human_api_overlap": 0,
            },
            "protocol": protocol,
            "attempted": True,
            "extractor": extraction.extractor,
            "complete": getattr(extraction, "complete", False),
            "toolchain_backed": toolchain_complete,
            "missing_toolchain_hashes": missing_hashes,
            "provenance": {
                "paths": sorted({c["match_path"] for c in closest if c.get("match_path")}),
            },
            "note": (
                "exact type-hash matches use ELABORATOR_EXTRACTED; "
                "token similarity remains HEURISTIC_RETRIEVAL (§11.5)"
            ),
        }
        coverage = EvidenceCoverage(
            requested_subject_count=len(names),
            evaluated_subject_count=len(closest),
            excluded_subject_count=len(missing_hashes),
            exclusion_reasons=[f"missing_hash:{n}" for n in missing_hashes],
            complete_for_declared_scope=not missing_hashes,
        )

        if toolchain_complete and missing_hashes:
            return _provider_result(
                self,
                context,
                [
                    _finding(
                        check_id="semantic.duplicate_retrieval",
                        dimension=EvidenceDimension.SEMANTIC,
                        status=FindingStatus.UNKNOWN,
                        severity=Severity.L2,
                        summary=(
                            "Duplicate retrieval unresolved: toolchain-complete corpus "
                            f"missing signature hashes for {missing_hashes}"
                        ),
                        details=details,
                        started=started,
                        finished=finished,
                        basis=EvidenceBasis.ELABORATOR_EXTRACTED,
                        coverage=coverage,
                    )
                ],
                started=started,
                finished=finished,
            )

        if high:
            basis = (
                EvidenceBasis.ELABORATOR_EXTRACTED
                if exact_matches and not heuristic_matches
                else (
                    EvidenceBasis.HEURISTIC_RETRIEVAL
                    if heuristic_matches and not exact_matches
                    else EvidenceBasis.ELABORATOR_EXTRACTED
                )
            )
            return _provider_result(
                self,
                context,
                [
                    _finding(
                        check_id="semantic.duplicate_retrieval",
                        dimension=EvidenceDimension.SEMANTIC,
                        status=FindingStatus.WARN,
                        severity=Severity.L2,
                        summary=(
                            "Near-duplicate declarations found in local corpus "
                            f"(exact_hash={len(exact_matches)}, "
                            f"heuristic_token={len(heuristic_matches)})"
                        ),
                        details=details,
                        started=started,
                        finished=finished,
                        basis=basis,
                        coverage=coverage,
                    )
                ],
                started=started,
                finished=finished,
            )

        return _provider_result(
            self,
            context,
            [
                _finding(
                    check_id="semantic.duplicate_retrieval",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=FindingStatus.PASS,
                    severity=Severity.INFO,
                    summary=(
                        f"Local corpus scanned ({len(corpus)} decls); no high-similarity "
                        + (
                            "near-duplicates (exact type hashes separated from heuristics)"
                            if toolchain_complete
                            else "near-duplicates (heuristic scan only)"
                        )
                    ),
                    details=details,
                    started=started,
                    finished=finished,
                    basis=(
                        EvidenceBasis.ELABORATOR_EXTRACTED
                        if toolchain_complete
                        else EvidenceBasis.HEURISTIC_RETRIEVAL
                    ),
                    coverage=coverage,
                )
            ],
            started=started,
            finished=finished,
        )


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

    def collect(self, context: ProviderContext) -> ProviderResult:
        started = datetime.now(UTC)
        candidate = context.candidate
        project_path = context.candidate_path
        raw_names = {d.name for d in candidate.changed_declarations}
        protocol = {
            "kind": "impact-cone-successor-replacement",
            "note": (
                "toolchain cones attempt signature-hash + optional Lake compile "
                "of dependents; regex-stub cones are heuristic inventory only"
            ),
        }

        if not raw_names:
            finished = datetime.now(UTC)
            return _provider_result(
                self,
                context,
                [
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
                ],
                started=started,
                finished=finished,
            )

        extraction = context.candidate_extraction or extract_lean_repository(project_path)
        changed_names, resolution_warnings = resolve_changed_names_detailed(
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
            finished = datetime.now(UTC)
            return _provider_result(
                self,
                context,
                [
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
                ],
                started=started,
                finished=finished,
            )

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
            "resolution_warnings": resolution_warnings,
        }

        if not toolchain_complete:
            finished = datetime.now(UTC)
            details["replacement_check"] = "regex_stub_inventory_only"
            return _provider_result(
                self,
                context,
                [
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
                ],
                started=started,
                finished=finished,
            )

        hash_report = _successor_hash_integrity(successors)
        details["signature_hash_check"] = hash_report
        lake_report = _try_compile_successor_modules(
            context,
            successors,
            max_modules=self._MAX_LAKE_MODULES,
        )
        details["lake_dependent_check"] = lake_report

        finished = datetime.now(UTC)

        if not hash_report["ran"]:
            details["replacement_check"] = "unavailable"
            return _provider_result(
                self,
                context,
                [
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
                ],
                started=started,
                finished=finished,
            )

        if not hash_report["ok"]:
            details["replacement_check"] = "signature_hash_failed"
            return _provider_result(
                self,
                context,
                [
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
                ],
                started=started,
                finished=finished,
            )

        if lake_report["attempted"]:
            if lake_report["ok"]:
                details["replacement_check"] = "signature_hash+lake_env"
                return _provider_result(
                    self,
                    context,
                    [
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
                    ],
                    started=started,
                    finished=finished,
                )
            details["replacement_check"] = "lake_env_failed"
            return _provider_result(
                self,
                context,
                [
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
                ],
                started=started,
                finished=finished,
            )

        # Lake not runnable — hash check alone is structured but incomplete.
        # Fail closed: UNKNOWN rather than PASS without an executable check.
        if lake_report.get("reason") == "lake_unavailable":
            details["replacement_check"] = "hash_only_lake_unavailable"
            return _provider_result(
                self,
                context,
                [
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
                ],
                started=started,
                finished=finished,
            )

        details["replacement_check"] = "signature_hash"
        return _provider_result(
            self,
            context,
            [
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
            ],
            started=started,
            finished=finished,
        )


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
    ok = checked > 0 and mismatched == 0 and missing_hash == 0 and missing_signature == 0
    return {
        "ran": len(successors) > 0 and checked > 0,
        "ok": ok,
        "checked": checked,
        "mismatched": mismatched,
        "missing_hash": missing_hash,
        "missing_signature": missing_signature,
    }


def _try_compile_successor_modules(
    context: ProviderContext,
    successors: list[dict[str, Any]],
    *,
    max_modules: int,
) -> dict[str, Any]:
    """Compile unique successor ``.lean`` paths via the workspace executor."""
    project_path = context.candidate_path
    if not lean_toolchain_available(project_path) or not has_lakefile(project_path):
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
        lake_result = _try_lake_env_lean(context, rel)
        if not lake_result["ok"]:
            failures.append(
                {
                    "module": rel,
                    "exit_code": lake_result.get("exit_code"),
                    "stderr": lake_result.get("stderr", "")[:400],
                    "error": lake_result.get("reason"),
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
            "error": failures[0].get("error") or failures[0].get("stderr") or "non-zero exit",
        }

    return {
        "attempted": True,
        "ok": True,
        "reason": "lake_env_ok",
        "modules_checked": len(modules),
        "modules": modules,
    }
