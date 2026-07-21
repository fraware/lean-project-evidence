"""Paired downstream successor suite provider (CLOSURE-014)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from lpe import __version__
from lpe.evidence.payloads import FindingPayload, executed_check_payload
from lpe.execution.protocol import ValidatedCommand
from lpe.hashing import sha256_value
from lpe.models import (
    EvidenceBasis,
    EvidenceCoverage,
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    Provenance,
    Severity,
    SubjectReference,
    SuccessorSuite,
)
from lpe.providers.base import ProviderContext, ProviderResult
from lpe.providers.fixtures import load_successor_suite
from lpe.workspace.manager import make_stable_finding_id


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
        producer_id="downstream.successor-suite",
        producer_version="0.2.0",
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
    basis: EvidenceBasis,
    coverage: EvidenceCoverage,
    subject_refs: list[SubjectReference] | None = None,
    command: list[str] | None = None,
    payload: FindingPayload | None = None,
) -> EvidenceFinding:
    check_version = "0.2.0"
    dimension = EvidenceDimension.DOWNSTREAM
    typed_payload: FindingPayload = (
        payload if payload is not None else executed_check_payload(check_id, details)
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
            command=command,
            output={"status": status.value, "summary": summary},
        ),
        basis=basis,
        coverage=coverage,
        subject_refs=list(subject_refs or []),
        payload=typed_payload,
        required_basis=EvidenceBasis.EXECUTED_TEST,
    )


def _run_command(
    context: ProviderContext,
    *,
    root_label: str,
    argv: list[str],
    timeout_seconds: int,
) -> dict[str, Any]:
    """Execute ``argv`` under the workspace executor on base or candidate."""
    profile = context.resource_profile_for("downstream.successor-suite")
    if timeout_seconds < profile.timeout_seconds:
        # ProviderResourceProfile is a Pydantic model — use model_copy.
        profile = profile.model_copy(update={"timeout_seconds": timeout_seconds})

    allowlist = list(context.contract.project.execution.environment_allowlist)
    snapshot_root = "base" if root_label == "base" else "candidate"
    try:
        command = ValidatedCommand.from_argv(argv, snapshot_root=snapshot_root)
        result = context.workspace.executor.run(
            workspace=context.workspace,
            command=command,
            resource_profile=profile,
            environment_allowlist=allowlist,
        )
    except (OSError, TimeoutError, ValueError) as exc:
        return {
            "ok": False,
            "exit_code": None,
            "timed_out": False,
            "stderr": str(exc)[:400],
            "reason": "invoke_error",
            "root": root_label,
        }

    ok = result.exit_code == 0 and not result.timed_out
    return {
        "ok": ok,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "stderr": (result.stderr or result.stdout or "")[:400],
        "reason": "ok" if ok else ("timeout" if result.timed_out else "nonzero_exit"),
        "root": root_label,
        "executor": context.workspace.executor_descriptor.backend,
        "snapshot_fingerprint": context.snapshot_fingerprint,
    }


def _classify_pair(base: dict[str, Any], candidate: dict[str, Any]) -> str:
    """Classify successor outcome relative to base."""
    base_ok = bool(base.get("ok"))
    cand_ok = bool(candidate.get("ok"))
    if not base_ok and cand_ok:
        return "enabled"
    if base_ok and not cand_ok:
        return "regressed"
    return "unchanged"


class DownstreamSuccessorProvider:
    """Run declared successor suite on base and candidate (CLOSURE-014)."""

    provider_id = "downstream.successor-suite"
    provider_version = "0.2.0"
    required_basis = EvidenceBasis.EXECUTED_TEST

    def collect(self, context: ProviderContext) -> ProviderResult:
        started = datetime.now(UTC)
        candidate = context.candidate
        suite, load_report = load_successor_suite(context.candidate_path)

        if suite is None:
            finished = datetime.now(UTC)
            status = FindingStatus.UNKNOWN
            # No public surface → N/A is acceptable without a suite.
            if not any(d.public for d in candidate.changed_declarations):
                status = FindingStatus.NOT_APPLICABLE
            finding = _finding(
                check_id="downstream.successor_suite",
                status=status,
                severity=Severity.INFO if status is FindingStatus.NOT_APPLICABLE else Severity.L2,
                summary=(
                    "Downstream successor suite not applicable"
                    if status is FindingStatus.NOT_APPLICABLE
                    else (
                        "Downstream successor suite unresolved: "
                        f"{load_report.get('error') or 'manifest_missing'}"
                    )
                ),
                details={
                    "obligation_ids": list(candidate.obligation_ids),
                    "load_report": load_report,
                    "attempted": True,
                    "enabled": [],
                    "regressed": [],
                    "unchanged": [],
                },
                started=started,
                finished=finished,
                basis=EvidenceBasis.EXECUTED_TEST,
                coverage=EvidenceCoverage(
                    requested_subject_count=0,
                    evaluated_subject_count=0,
                    complete_for_declared_scope=status is FindingStatus.NOT_APPLICABLE,
                    exclusion_reasons=(
                        []
                        if status is FindingStatus.NOT_APPLICABLE
                        else [str(load_report.get("error") or "manifest_missing")]
                    ),
                ),
            )
            return ProviderResult(
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                snapshot_fingerprint=context.snapshot_fingerprint,
                findings=[finding],
                started_at=started,
                finished_at=finished,
            )

        return self._run_suite(context, suite, load_report, started=started)

    def _run_suite(
        self,
        context: ProviderContext,
        suite: SuccessorSuite,
        load_report: dict[str, Any],
        *,
        started: datetime,
    ) -> ProviderResult:
        results: list[dict[str, Any]] = []
        enabled: list[str] = []
        regressed: list[str] = []
        unchanged: list[str] = []
        unknown_failures: list[str] = []

        for entry in suite.successors:
            base_run = _run_command(
                context,
                root_label="base",
                argv=list(entry.command),
                timeout_seconds=entry.timeout_seconds,
            )
            cand_run = _run_command(
                context,
                root_label="candidate",
                argv=list(entry.command),
                timeout_seconds=entry.timeout_seconds,
            )
            # Unrelated invoke errors → UNKNOWN for that successor.
            if base_run.get("reason") == "invoke_error" or cand_run.get("reason") == "invoke_error":
                classification = "unknown"
                unknown_failures.append(entry.successor_id)
            else:
                classification = _classify_pair(base_run, cand_run)
                if classification == "enabled":
                    enabled.append(entry.successor_id)
                elif classification == "regressed":
                    regressed.append(entry.successor_id)
                else:
                    unchanged.append(entry.successor_id)

            results.append(
                {
                    "successor_id": entry.successor_id,
                    "required": entry.required,
                    "command": list(entry.command),
                    "base": base_run,
                    "candidate": cand_run,
                    "classification": classification,
                    "module": entry.module,
                    "declarations": list(entry.declarations),
                }
            )

        finished = datetime.now(UTC)
        details: dict[str, Any] = {
            "suite_id": suite.suite_id,
            "obligation_ids": list(suite.obligation_ids),
            "load_report": load_report,
            "successors": results,
            "enabled": enabled,
            "regressed": regressed,
            "unchanged": unchanged,
            "unknown": unknown_failures,
            "attempted": True,
            "shared_provenance": {
                "snapshot_fingerprint": context.snapshot_fingerprint,
                "executor_backend": context.workspace.executor_descriptor.backend,
                "run_id": context.workspace.run_id,
            },
        }

        subject_refs = [
            SubjectReference(kind="successor", ref=e.successor_id) for e in suite.successors
        ]
        coverage = EvidenceCoverage(
            requested_subject_count=len(suite.successors),
            evaluated_subject_count=len(results),
            excluded_subject_count=len(unknown_failures),
            exclusion_reasons=(
                [f"invoke_error:{sid}" for sid in unknown_failures] if unknown_failures else []
            ),
            complete_for_declared_scope=not unknown_failures,
        )

        if unknown_failures:
            status = FindingStatus.UNKNOWN
            severity = Severity.L2
            summary = (
                f"Downstream successor suite incomplete due to execution errors: {unknown_failures}"
            )
        elif regressed:
            required_regressed = [
                r["successor_id"]
                for r in results
                if r["classification"] == "regressed" and r.get("required", True)
            ]
            status = FindingStatus.FAIL if required_regressed else FindingStatus.WARN
            severity = Severity.L2
            summary = f"Downstream successors regressed: {regressed}" + (
                f"; newly enabled: {enabled}" if enabled else ""
            )
        else:
            status = FindingStatus.PASS
            severity = Severity.INFO
            summary = (
                f"Downstream successor suite complete "
                f"(enabled={len(enabled)}, unchanged={len(unchanged)}, regressed=0)"
            )

        finding = _finding(
            check_id="downstream.successor_suite",
            status=status,
            severity=severity,
            summary=summary,
            details=details,
            started=started,
            finished=finished,
            basis=EvidenceBasis.EXECUTED_TEST,
            coverage=coverage,
            subject_refs=subject_refs,
        )
        return ProviderResult(
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            snapshot_fingerprint=context.snapshot_fingerprint,
            findings=[finding],
            started_at=started,
            finished_at=finished,
        )
