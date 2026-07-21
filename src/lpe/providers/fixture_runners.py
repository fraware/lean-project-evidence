"""Manifest-driven example and counterexample runners (CLOSURE-013)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Literal

from lpe import __version__
from lpe.evidence.payloads import FindingPayload, executed_check_payload
from lpe.execution.protocol import ValidatedCommand
from lpe.hashing import sha256_value
from lpe.lean.extractor import lean_toolchain_available
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
from lpe.providers.fixtures import load_fixture_suite
from lpe.workspace.manager import make_stable_finding_id


def _redact_log_snippet(text: str, *, limit: int = 400) -> str:
    from lpe.execution.redact import redact_secrets

    return redact_secrets(text or "")[:limit]


def _try_lake_env_lean(context: ProviderContext, rel_lean: str) -> dict[str, Any]:
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


def _provider_result(
    provider: Any,
    context: ProviderContext,
    findings: list[EvidenceFinding],
    *,
    started: datetime,
    finished: datetime,
) -> ProviderResult:
    return ProviderResult(
        provider_id=str(provider.provider_id),
        provider_version=str(provider.provider_version),
        snapshot_fingerprint=context.snapshot_fingerprint,
        findings=findings,
        started_at=started,
        finished_at=finished,
    )


def _finding(
    *,
    check_id: str,
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
    dimension = EvidenceDimension.SEMANTIC
    typed_payload: FindingPayload = (
        payload if payload is not None else executed_check_payload(check_id, details)
    )
    now_prov = Provenance(
        tool="lean-project-evidence",
        tool_version=__version__,
        command=[],
        input_hash=sha256_value({"check_id": check_id, "details": details}),
        output_hash=sha256_value({"status": status, "summary": summary}),
        started_at=started,
        finished_at=finished,
        elapsed_ms=max(0, int((finished - started).total_seconds() * 1000)),
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
        provenance=now_prov,
        basis=basis,
        coverage=coverage,
        subject_refs=list(subject_refs or []),
        payload=typed_payload,
        required_basis=required_basis,
    )


def _diagnostic_matches(stderr: str, *, regex: str | None, needles: list[str]) -> bool:
    if regex:
        return re.search(regex, stderr, flags=re.IGNORECASE | re.MULTILINE) is not None
    if needles:
        lowered = stderr.lower()
        return all(n.lower() in lowered for n in needles)
    return True


def _is_unrelated_lean_failure(stderr: str, exit_code: int | None) -> bool:
    text = (stderr or "").lower()
    markers = (
        "unknown package",
        "could not find",
        "no such file",
        "lean toolchain",
        "invalid lean",
        "parse error",
        "unexpected token",
        "failed to import",
        "lake failed",
        "error: no such file or directory",
    )
    if exit_code is None:
        return True
    return any(m in text for m in markers)


def collect_fixture_suite(
    provider: object,
    context: ProviderContext,
    *,
    kind: Literal["examples", "counterexamples"],
    check_id: str,
    expected_success: bool,
) -> ProviderResult:
    started = datetime.now(UTC)
    candidate = context.candidate
    project_path = context.candidate_path
    suite, load_report = load_fixture_suite(project_path, kind=kind)
    lake_capable = has_lakefile(project_path) and lean_toolchain_available(project_path)

    protocol = {
        "kind": "fixture-suite-manifest",
        "suite_kind": kind,
        "toolchain_backed": lake_capable,
        "note": ("YAML suite manifests required; directory heuristics cannot PASS (CLOSURE-013)"),
    }

    if suite is None:
        finished = datetime.now(UTC)
        return _provider_result(
            provider,
            context,
            [
                _finding(
                    check_id=check_id,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L2,
                    summary=(
                        f"{kind} suite unresolved: {load_report.get('error') or 'manifest_missing'}"
                    ),
                    details={
                        "load_report": load_report,
                        "protocol": protocol,
                        "attempted": True,
                        "obligation_ids": list(candidate.obligation_ids),
                    },
                    started=started,
                    finished=finished,
                    basis=EvidenceBasis.EXECUTED_TEST,
                    coverage=EvidenceCoverage(
                        requested_subject_count=0,
                        evaluated_subject_count=0,
                        complete_for_declared_scope=False,
                        exclusion_reasons=[str(load_report.get("error") or "manifest_missing")],
                    ),
                )
            ],
            started=started,
            finished=finished,
        )

    suite_obs = set(suite.obligation_ids)
    cand_obs = set(candidate.obligation_ids)
    if suite_obs.isdisjoint(cand_obs):
        finished = datetime.now(UTC)
        return _provider_result(
            provider,
            context,
            [
                _finding(
                    check_id=check_id,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L2,
                    summary=(
                        f"{kind} suite obligation_ids {sorted(suite_obs)} do not "
                        f"bind candidate obligations {sorted(cand_obs)}"
                    ),
                    details={
                        "suite_id": suite.suite_id,
                        "suite_obligation_ids": list(suite.obligation_ids),
                        "candidate_obligation_ids": list(candidate.obligation_ids),
                        "protocol": protocol,
                        "attempted": True,
                    },
                    started=started,
                    finished=finished,
                    basis=EvidenceBasis.EXECUTED_TEST,
                    coverage=EvidenceCoverage(
                        requested_subject_count=len(suite.fixtures),
                        evaluated_subject_count=0,
                        complete_for_declared_scope=False,
                        exclusion_reasons=["obligation_binding_mismatch"],
                    ),
                )
            ],
            started=started,
            finished=finished,
        )

    results: list[dict[str, Any]] = []
    failures: list[str] = []
    unknowns: list[str] = []
    evaluated = 0

    for entry in suite.fixtures:
        targets: list[str] = []
        if entry.run_on in {"candidate", "both"}:
            targets.append("candidate")
        if entry.run_on in {"base", "both"}:
            targets.append("base")

        for target in targets:
            evaluated += 1
            root = context.base_path if target == "base" else context.candidate_path
            fixture_path = root / entry.path
            rel = entry.path.replace("\\", "/")
            record: dict[str, Any] = {
                "fixture_id": entry.fixture_id,
                "path": rel,
                "run_on": target,
                "expected_exit": entry.expected_exit,
            }

            if not fixture_path.is_file():
                unknowns.append(entry.fixture_id)
                record.update({"ok": False, "reason": "fixture_missing"})
                results.append(record)
                continue

            if fixture_path.suffix.lower() != ".lean":
                unknowns.append(entry.fixture_id)
                record.update(
                    {
                        "ok": False,
                        "reason": "non_lean_fixture_requires_executed_test",
                        "note": "JSON/YAML alone cannot satisfy EXECUTED_TEST basis",
                    }
                )
                results.append(record)
                continue

            if not lake_capable:
                unknowns.append(entry.fixture_id)
                record.update({"ok": False, "reason": "lake_unavailable"})
                results.append(record)
                continue

            lake = _try_lake_env_lean(context, rel)
            exit_code = lake.get("exit_code")
            stderr = str(lake.get("stderr") or "")
            record["lake"] = lake
            exit_int = exit_code if isinstance(exit_code, int) else None
            if lake.get("reason") == "lake_invoke_error" or _is_unrelated_lean_failure(
                stderr, exit_int
            ):
                unknowns.append(entry.fixture_id)
                record.update({"ok": False, "reason": "unrelated_lean_failure"})
                results.append(record)
                continue

            exit_ok = exit_int == entry.expected_exit
            diag_ok = _diagnostic_matches(
                stderr,
                regex=entry.expected_diagnostic_regex,
                needles=list(entry.expected_diagnostics),
            )
            if expected_success:
                ok = exit_ok and diag_ok and bool(lake.get("ok"))
            else:
                if exit_ok and not diag_ok:
                    unknowns.append(entry.fixture_id)
                    record.update(
                        {
                            "ok": False,
                            "reason": "diagnostic_mismatch",
                            "stderr": stderr[:400],
                        }
                    )
                    results.append(record)
                    continue
                ok = exit_ok and diag_ok

            if not ok:
                failures.append(entry.fixture_id)
            record.update({"ok": ok, "reason": "executed"})
            results.append(record)

    finished = datetime.now(UTC)
    details: dict[str, Any] = {
        "suite_id": suite.suite_id,
        "obligation_ids": list(suite.obligation_ids),
        "fixtures": results,
        "fixture_count": len(suite.fixtures),
        "protocol": protocol,
        "attempted": True,
        "load_report": load_report,
        "failures": failures,
        "unknowns": unknowns,
    }
    coverage = EvidenceCoverage(
        requested_subject_count=len(suite.fixtures),
        evaluated_subject_count=evaluated,
        excluded_subject_count=len(unknowns),
        exclusion_reasons=[f"unknown:{u}" for u in unknowns],
        complete_for_declared_scope=not unknowns,
    )
    subjects = [SubjectReference(kind="fixture", ref=e.fixture_id) for e in suite.fixtures]

    if unknowns and not failures:
        status = FindingStatus.UNKNOWN
        summary = f"{kind} suite incomplete / unrelated failures: {unknowns}"
    elif failures and not unknowns:
        status = FindingStatus.FAIL
        summary = f"{kind} suite failed fixtures: {failures}"
    elif failures or unknowns:
        status = FindingStatus.UNKNOWN
        summary = f"{kind} suite mixed outcomes: failures={failures} unknowns={unknowns}"
    else:
        status = FindingStatus.PASS
        summary = f"{kind} suite passed ({len(suite.fixtures)} fixtures; executed)"

    return _provider_result(
        provider,
        context,
        [
            _finding(
                check_id=check_id,
                status=status,
                severity=Severity.INFO if status is FindingStatus.PASS else Severity.L2,
                summary=summary,
                details=details,
                started=started,
                finished=finished,
                basis=EvidenceBasis.EXECUTED_TEST,
                coverage=coverage,
                subject_refs=subjects,
                required_basis=EvidenceBasis.EXECUTED_TEST,
            )
        ],
        started=started,
        finished=finished,
    )


class ExampleRunnerProvider:
    """Project-example protocol driven by YAML fixture suite manifests."""

    provider_id = "semantic.example-runner"
    provider_version = "0.2.0"
    required_basis = EvidenceBasis.EXECUTED_TEST

    def collect(self, context: ProviderContext) -> ProviderResult:
        return collect_fixture_suite(
            self,
            context,
            kind="examples",
            check_id="semantic.project_examples",
            expected_success=True,
        )


class CounterexampleProvider:
    """Counterexample protocol driven by YAML fixture suite manifests."""

    provider_id = "semantic.counterexample"
    provider_version = "0.2.0"
    required_basis = EvidenceBasis.EXECUTED_TEST

    def collect(self, context: ProviderContext) -> ProviderResult:
        return collect_fixture_suite(
            self,
            context,
            kind="counterexamples",
            check_id="semantic.counterexamples",
            expected_success=False,
        )
