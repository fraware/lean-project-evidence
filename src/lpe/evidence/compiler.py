from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpe import __version__
from lpe.contract.loader import load_contract, validate_candidate_obligations
from lpe.evidence.gates import decide
from lpe.evidence.payloads import (
    FindingPayload,
    executed_check_payload,
    opaque_finding_payload,
    structural_diff_payload,
)
from lpe.evidence.risk import classify_risk
from lpe.evidence.router import select_review_question
from lpe.evidence.synthesis import apply_synthesis, recommendation_policy_id
from lpe.execution.allowlist import validate_build_command
from lpe.execution.protocol import LeanExecutor
from lpe.execution.runner import SubprocessLeanExecutor
from lpe.execution.sandbox import (
    DockerSandboxExecutor,
    combined_build_extract_enabled,
    isolation_status_for_executor,
    parse_combined_phase,
)
from lpe.git.candidate import enrich_candidate_from_git
from lpe.git.diff import GitError
from lpe.hashing import sha256_text, sha256_value
from lpe.ids import new_id
from lpe.lean.extractor import (
    REGEX_STUB_EXTRACTOR,
    TOOLCHAIN_EXTRACTOR,
    build_dependency_graph,
    extract_lean_repository,
    impact_cone,
    import_expansion,
    resolve_changed_names_detailed,
)
from lpe.lean.toolchain import (
    NOTE_DOCKER_EXTRACT,
    build_failed_before_extract_result,
    extract_executor_label,
    extraction_artifact_path,
    finalize_extract_from_exit,
    persist_toolchain_artifact,
    project_declares_lpe_extract,
    try_run_lake_extract,
)
from lpe.models import (
    CandidateDescriptor,
    EvidenceCoverage,
    EvidenceDimension,
    EvidenceFinding,
    EvidencePacket,
    FindingStatus,
    HardGateResult,
    ProjectContract,
    Provenance,
    Severity,
    UncertaintyRecord,
)
from lpe.paths import PathTraversalError, assert_safe_repo_relative
from lpe.providers.base import CancellationToken, ProviderContext
from lpe.providers.downstream import DownstreamSuccessorProvider
from lpe.providers.semantic import (
    CounterexampleProvider,
    DownstreamReplacementProvider,
    DuplicateRetrievalProvider,
    ExampleRunnerProvider,
    StatementDiffProvider,
)
from lpe.workspace.artifacts import (
    validate_packet_size_budget,
)
from lpe.workspace.manager import (
    EvaluationWorkspaceManager,
    HostExecutionRefusedError,
    NetworkPolicyError,
    canonical_finding_payload,
    compute_evidence_fingerprint,
    select_executor,
    stable_finding_id,
)

# Re-export workspace policy errors for CLI / callers that historically imported
# them from the compiler module.
__all__ = [
    "HostExecutionRefusedError",
    "NetworkPolicyError",
    "compile_evidence",
]

# Compatibility re-exports for tests that still patch the legacy worktree helper.
from lpe.execution.worktree import create_isolated_worktree  # noqa: F401
from lpe.workspace.snapshots import create_snapshot_pair  # noqa: F401

# Extractors that cannot prove axiom closure — never PASS lean.prohibited_axioms.
_INCOMPLETE_AXIOM_EXTRACTORS = frozenset(
    {
        REGEX_STUB_EXTRACTOR,
        "lean.regex-extractor",  # legacy id
        "lean.adaptive-extractor",
    }
)


def _normalize_network_policy(policy: str) -> str:
    normalized = (policy or "deny").strip().lower()
    if normalized not in {"deny", "allow"}:
        # Fail closed: unknown policies are treated as deny.
        return "deny"
    return normalized


def _select_executor(
    *,
    insecure_host_exec: bool,
    network_policy: str,
) -> tuple[LeanExecutor, bool]:
    """Compatibility wrapper; prefer ``select_executor`` for descriptors."""
    executor, _descriptor, network_isolated = select_executor(
        insecure_host_exec=insecure_host_exec,
        network_policy=network_policy,
    )
    return executor, network_isolated


def _provenance(
    *,
    check_input: dict[str, Any],
    started: datetime,
    finished: datetime,
    command: list[str] | None = None,
    output: Any | None = None,
    provider_metadata: dict[str, Any] | None = None,
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
        provider_metadata=provider_metadata or {},
    )


_DEFAULT_CHECK_VERSION = "0.1.0"


def _subject_hash(*, check_id: str, dimension: EvidenceDimension, details: dict[str, Any]) -> str:
    """Stable subject digest for finding IDs (CLOSURE-011)."""
    return sha256_value(
        {
            "check_id": check_id,
            "dimension": dimension.value if hasattr(dimension, "value") else str(dimension),
            "details": details,
        }
    )[:16]


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
    command: list[str] | None = None,
    provider_metadata: dict[str, Any] | None = None,
    check_version: str = _DEFAULT_CHECK_VERSION,
    payload: FindingPayload | None = None,
) -> EvidenceFinding:
    finding_id = stable_finding_id(
        check_id=check_id,
        subject_hash=_subject_hash(check_id=check_id, dimension=dimension, details=details),
        check_version=check_version,
    )
    typed_payload: FindingPayload = (
        payload if payload is not None else _default_compiler_payload(check_id, details)
    )
    return EvidenceFinding(
        finding_id=finding_id,
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
            output={"status": status, "summary": summary},
            provider_metadata=provider_metadata,
        ),
        payload=typed_payload,
    )


def _default_compiler_payload(check_id: str, details: dict[str, Any]) -> FindingPayload:
    if check_id in {"lean.build", "lean.typecheck"}:
        return executed_check_payload(check_id, details)
    if check_id.startswith("lean.") or check_id.startswith("repository."):
        if any(
            key in details for key in ("changed", "compared", "missing", "impact_cone", "axioms")
        ):
            return structural_diff_payload(details)
    return opaque_finding_payload(details)


def _is_incomplete_axiom_extractor(extractor_id: str) -> bool:
    if extractor_id == TOOLCHAIN_EXTRACTOR:
        return False
    return (
        extractor_id in _INCOMPLETE_AXIOM_EXTRACTORS
        or "regex" in extractor_id
        or extractor_id == REGEX_STUB_EXTRACTOR
    )


def _is_toolchain_complete(extraction: Any) -> bool:
    return (
        extraction.extractor == TOOLCHAIN_EXTRACTOR
        and bool(getattr(extraction, "complete", False))
        and not extraction.errors
    )


def _extract_executor_from_notes(extraction: Any) -> str | None:
    """Derive extract provenance from toolchain notes (docker-sandbox vs host)."""
    notes = list(getattr(extraction, "notes", []) or [])
    for note in notes:
        if "via docker-sandbox" in note:
            return "docker-sandbox"
        if "via SubprocessLeanExecutor" in note:
            return "SubprocessLeanExecutor"
    if any("produced by lake exe lpe_extract" in n for n in notes):
        return "host"
    return None


def _check_axioms(
    contract: Any,
    extraction: Any,
    *,
    started: datetime,
) -> EvidenceFinding:
    allowed = set(contract.project.allowed_axioms)
    used = set(extraction.axioms_used)
    prohibited = sorted(used - allowed)
    incomplete = _is_incomplete_axiom_extractor(extraction.extractor)

    if extraction.errors:
        finished = datetime.now(UTC)
        return _finding(
            check_id="lean.prohibited_axioms",
            dimension=EvidenceDimension.KERNEL,
            status=FindingStatus.UNKNOWN,
            severity=Severity.L3,
            summary="Lean extraction encountered errors; axiom closure unresolved",
            details={"errors": extraction.errors, "extractor": extraction.extractor},
            started=started,
            finished=finished,
            provider_metadata={"extractor": extraction.extractor},
        )

    if prohibited:
        finished = datetime.now(UTC)
        return _finding(
            check_id="lean.prohibited_axioms",
            dimension=EvidenceDimension.KERNEL,
            status=FindingStatus.FAIL,
            severity=Severity.L3,
            summary=f"Prohibited axioms detected: {prohibited}",
            details={
                "allowed_axioms": sorted(allowed),
                "axioms_used": sorted(used),
                "prohibited_axioms": prohibited,
                "extractor": extraction.extractor,
            },
            started=started,
            finished=finished,
            provider_metadata={"extractor": extraction.extractor},
        )

    # Fail closed: incomplete extractors must never PASS (empty axioms_used is not proof).
    if incomplete:
        finished = datetime.now(UTC)
        return _finding(
            check_id="lean.prohibited_axioms",
            dimension=EvidenceDimension.KERNEL,
            status=FindingStatus.UNKNOWN,
            severity=Severity.L3,
            summary=(
                "Axiom dependency closure is incomplete with the regex-stub extractor; "
                "escalating until a toolchain extractor is available"
            ),
            details={
                "allowed_axioms": sorted(allowed),
                "axioms_used": sorted(used),
                "prohibited_axioms": [],
                "extractor": extraction.extractor,
                "complete": getattr(extraction, "complete", False),
                "required_remedy": (
                    "provide .lpe/lean-extraction.json from a Lean/Lake elaborator; "
                    "empty axioms_used from regex-stub must not be treated as axiom closure"
                ),
            },
            started=started,
            finished=finished,
            provider_metadata={"extractor": extraction.extractor},
        )

    # Fail closed: lean.toolchain without complete=true is not axiom closure.
    if not _is_toolchain_complete(extraction):
        finished = datetime.now(UTC)
        return _finding(
            check_id="lean.prohibited_axioms",
            dimension=EvidenceDimension.KERNEL,
            status=FindingStatus.UNKNOWN,
            severity=Severity.L3,
            summary=(
                "Toolchain extraction is present but incomplete; axiom closure remains unresolved"
            ),
            details={
                "allowed_axioms": sorted(allowed),
                "axioms_used": sorted(used),
                "prohibited_axioms": [],
                "extractor": extraction.extractor,
                "complete": getattr(extraction, "complete", False),
                "required_remedy": (
                    "emit .lpe/lean-extraction.json with extractor=lean.toolchain "
                    "and complete=true from a Lean/Lake elaborator"
                ),
            },
            started=started,
            finished=finished,
            provider_metadata={"extractor": extraction.extractor},
        )

    finished = datetime.now(UTC)
    return _finding(
        check_id="lean.prohibited_axioms",
        dimension=EvidenceDimension.KERNEL,
        status=FindingStatus.PASS,
        severity=Severity.INFO,
        summary="All extracted axioms are allowed by project policy",
        details={
            "allowed_axioms": sorted(allowed),
            "axioms_used": sorted(used),
            "prohibited_axioms": prohibited,
            "extractor": extraction.extractor,
            "complete": True,
            "notes": list(getattr(extraction, "notes", []) or []),
            "extract_executor": _extract_executor_from_notes(extraction),
        },
        started=started,
        finished=finished,
        provider_metadata={"extractor": extraction.extractor},
    )


def _validate_candidate_paths(repository: Path, candidate: CandidateDescriptor) -> None:
    """Reject path-traversal in changed_paths / patch_path (AUDIT-025)."""
    for rel in candidate.changed_paths:
        assert_safe_repo_relative(repository, rel, label="changed_path")
    if candidate.patch_path:
        patch = Path(candidate.patch_path)
        if patch.is_absolute():
            raise PathTraversalError(
                f"patch_path must be repository-relative, got absolute {candidate.patch_path!r}"
            )
        assert_safe_repo_relative(repository, candidate.patch_path, label="patch_path")


def _collect_placeholder_materials(
    *,
    repository: Path,
    candidate: CandidateDescriptor,
) -> tuple[str, list[str]]:
    """Gather text to scan for prohibited placeholders (patch + applied tree)."""
    chunks: list[str] = []
    sources: list[str] = []

    if candidate.patch_text:
        chunks.append(candidate.patch_text)
        sources.append("patch_text")

    if candidate.patch_path:
        patch_file = assert_safe_repo_relative(repository, candidate.patch_path, label="patch_path")
        if patch_file.is_file():
            chunks.append(patch_file.read_text(encoding="utf-8", errors="replace"))
            sources.append(candidate.patch_path)

    for rel in candidate.changed_paths:
        if not rel.endswith(".lean"):
            continue
        lean_file = assert_safe_repo_relative(repository, rel, label="changed_path")
        if lean_file.is_file():
            chunks.append(lean_file.read_text(encoding="utf-8", errors="replace"))
            sources.append(rel)

    return "\n".join(chunks), sources


def compile_evidence(
    project_path: Path,
    candidate: CandidateDescriptor,
    *,
    skip_build: bool = False,
    insecure_host_exec: bool = False,
    use_sandbox: bool | None = None,
    use_worktree: bool = False,
    enable_lean_extraction: bool = True,
    enable_semantic_providers: bool = True,
    contract: ProjectContract | None = None,
) -> EvidencePacket:
    """Compile an evidence packet for a candidate.

    Host subprocess builds are refused unless ``insecure_host_exec`` is True AND
    ``network_policy`` is not ``deny``. When ``network_policy`` is ``deny``, Docker
    with ``--network=none`` is required. ``use_sandbox`` is retained for compatibility:
    ``True`` forces sandbox preference (default); ``False`` requires
    ``insecure_host_exec`` and a non-deny network policy for non-skipped builds.

    Pass a preloaded ``contract`` to avoid a redundant filesystem re-read when the
    caller already validated the same project path in this process.
    """
    if use_sandbox is False and not insecure_host_exec and not skip_build:
        raise HostExecutionRefusedError(
            "use_sandbox=False requires insecure_host_exec=True (or --insecure-host-exec). "
            "Host subprocess builds are refused by default for untrusted repositories."
        )
    if use_sandbox is True:
        insecure_host_exec = False

    run_id = new_id("run")
    findings: list[EvidenceFinding] = []

    started = datetime.now(UTC)
    if contract is None:
        contract = load_contract(project_path)
    validate_candidate_obligations(contract, candidate.project_id, candidate.obligation_ids)

    # Fail closed early when sandbox=False would violate network_policy=deny.
    if (
        not skip_build
        and use_sandbox is False
        and _normalize_network_policy(contract.project.execution.network_policy) == "deny"
    ):
        raise NetworkPolicyError(
            "use_sandbox=False is incompatible with network_policy='deny'. "
            "Deny requires Docker --network=none."
        )

    repository_path = project_path.resolve()
    try:
        candidate = enrich_candidate_from_git(repository_path, candidate, contract)
    except GitError as exc:
        raise GitError(str(exc)) from exc

    _validate_candidate_paths(repository_path, candidate)

    finished = datetime.now(UTC)
    findings.append(
        _finding(
            check_id="contract.valid",
            dimension=EvidenceDimension.REPOSITORY,
            status=FindingStatus.PASS,
            severity=Severity.INFO,
            summary="Project contract and obligation references are valid",
            details={"contract_hash": contract.contract_hash},
            started=started,
            finished=finished,
        )
    )
    findings.append(
        _finding(
            check_id="candidate.obligations",
            dimension=EvidenceDimension.DOWNSTREAM,
            status=FindingStatus.PASS,
            severity=Severity.INFO,
            summary="Candidate is bound to predeclared obligations",
            details={"obligation_ids": candidate.obligation_ids},
            started=started,
            finished=finished,
        )
    )

    denied = [
        path
        for path in candidate.changed_paths
        if any(path.startswith(prefix) for prefix in contract.policies.changed_path_denylist)
    ]
    now = datetime.now(UTC)
    findings.append(
        _finding(
            check_id="repository.changed_paths",
            dimension=EvidenceDimension.REPOSITORY,
            status=FindingStatus.FAIL if denied else FindingStatus.PASS,
            severity=Severity.L3 if denied else Severity.INFO,
            summary=(
                f"Candidate changes denied paths: {denied}"
                if denied
                else "Changed paths satisfy project policy"
            ),
            details={"denied_paths": denied, "changed_paths": candidate.changed_paths},
            started=now,
            finished=now,
        )
    )

    scan_material, scan_sources = _collect_placeholder_materials(
        repository=repository_path,
        candidate=candidate,
    )
    prohibited_tokens = [
        token for token in contract.project.prohibited_tokens if token in scan_material
    ]
    now = datetime.now(UTC)
    findings.append(
        _finding(
            check_id="lean.placeholders",
            dimension=EvidenceDimension.KERNEL,
            status=FindingStatus.FAIL if prohibited_tokens else FindingStatus.PASS,
            severity=Severity.L3 if prohibited_tokens else Severity.INFO,
            summary=(
                f"Prohibited tokens found: {prohibited_tokens}"
                if prohibited_tokens
                else "No prohibited placeholder token was found in patch or changed Lean files"
            ),
            details={
                "tokens": prohibited_tokens,
                "scanned_sources": scan_sources,
            },
            started=now,
            finished=now,
        )
    )

    network_policy = _normalize_network_policy(contract.project.execution.network_policy)
    build_ran = False
    network_isolated = False
    executor: LeanExecutor
    executor_descriptor = None
    pending_extraction = None
    extract_executor_name: str | None = None
    sandbox_invocations: int | None = None
    combined_build_extract = False
    extract_already_done = False
    ws_manager = EvaluationWorkspaceManager(artifact_root=repository_path)
    workspace = None
    build_repo = repository_path

    semantic_providers = (
        StatementDiffProvider(),
        ExampleRunnerProvider(),
        CounterexampleProvider(),
        DuplicateRetrievalProvider(),
        DownstreamReplacementProvider(),
        DownstreamSuccessorProvider(),
    )
    provider_versions = {p.provider_id: p.provider_version for p in semantic_providers}

    try:
        # Select executor before workspace so descriptor is frozen into RunManifest.
        if skip_build and network_policy == "deny" and not DockerSandboxExecutor.is_available():
            from lpe.workspace.models import ExecutorDescriptor as _ED

            executor = SubprocessLeanExecutor()
            executor_descriptor = _ED(
                backend="host",
                network_policy="deny",
                readonly_root=False,
                source_mount_readonly=False,
            )
            network_isolated = False
        elif skip_build and insecure_host_exec and network_policy == "allow":
            executor, executor_descriptor, network_isolated = select_executor(
                insecure_host_exec=True,
                network_policy="allow",
            )
        elif skip_build and DockerSandboxExecutor.is_available():
            executor, executor_descriptor, network_isolated = select_executor(
                insecure_host_exec=False,
                network_policy=network_policy,
            )
        elif skip_build:
            from lpe.workspace.models import ExecutorDescriptor as _ED

            executor = SubprocessLeanExecutor()
            executor_descriptor = _ED(
                backend="host",
                network_policy="allow" if network_policy == "allow" else "deny",
                readonly_root=False,
                source_mount_readonly=False,
            )
            network_isolated = False
        else:
            executor, executor_descriptor, network_isolated = select_executor(
                insecure_host_exec=insecure_host_exec,
                network_policy=network_policy,
            )

        # Always create an EvaluationWorkspace so providers never see the operator path.
        # ``use_worktree`` is retained for CLI compatibility; workspace isolation is mandatory.
        _ = use_worktree
        workspace = ws_manager.create(
            repository_path,
            contract,
            candidate,
            executor=executor,
            executor_descriptor=executor_descriptor,
            run_id=run_id,
            provider_versions=provider_versions,
            artifact_root=repository_path,
        )
        build_repo = workspace.candidate_path

        if skip_build:
            now = datetime.now(UTC)
            findings.append(
                _finding(
                    check_id="lean.build",
                    dimension=EvidenceDimension.KERNEL,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L2,
                    summary="Exact-environment build was skipped",
                    details={"repository": str(build_repo)},
                    started=now,
                    finished=now,
                )
            )
            # Executor already selected above; isolation not claimed for skipped builds.
            pass
        else:
            command = validate_build_command(list(contract.project.execution.build_command))
            allowlist = list(contract.project.execution.environment_allowlist)
            timeout_s = contract.project.execution.timeout_seconds
            max_out = contract.project.execution.max_output_bytes
            use_combined = (
                isinstance(executor, DockerSandboxExecutor)
                and combined_build_extract_enabled()
                and enable_lean_extraction
                and bool(candidate.changed_paths)
                and not os.environ.get("LPE_LEAN_EXTRACT_CMD", "").strip()
                and project_declares_lpe_extract(build_repo)
            )
            build_started = datetime.now(UTC)
            if use_combined:
                assert isinstance(executor, DockerSandboxExecutor)
                out_rel = str(extraction_artifact_path(build_repo).relative_to(build_repo)).replace(
                    "\\", "/"
                )
                result = executor.verify_build_and_extract(
                    repository=build_repo,
                    build_command=command,
                    extract_out=out_rel,
                    timeout_seconds=timeout_s,
                    max_output_bytes=max_out,
                    environment_allowlist=allowlist,
                )
                sandbox_invocations = 1
                combined_build_extract = True
                phase = parse_combined_phase(result.stderr, result.stdout)
                # Extract-phase failure still means the build succeeded.
                build_ok = result.exit_code == 0 or phase == "extract"
                extract_executor_name = extract_executor_label(executor)
                if not build_ok:
                    pending_extraction = build_failed_before_extract_result(
                        exit_code=result.exit_code,
                        provenance_note=NOTE_DOCKER_EXTRACT,
                    )
                    extract_already_done = True
                else:
                    extract_code = 0 if result.exit_code == 0 else result.exit_code
                    if phase == "ok":
                        extract_code = 0
                    elif phase == "extract":
                        extract_code = result.exit_code if result.exit_code != 0 else 1
                    pending_extraction = finalize_extract_from_exit(
                        build_repo,
                        returncode=extract_code,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        provenance_note=NOTE_DOCKER_EXTRACT,
                        via_executor=True,
                    )
                    extract_already_done = True
            else:
                result = executor.verify_build(
                    repository=build_repo,
                    command=command,
                    timeout_seconds=timeout_s,
                    max_output_bytes=max_out,
                    environment_allowlist=allowlist,
                )
                if isinstance(executor, DockerSandboxExecutor):
                    sandbox_invocations = 1
                build_ok = result.exit_code == 0

            build_finished = datetime.now(UTC)
            build_ran = True
            if workspace is not None:
                workspace.artifact_store.put_text(
                    result.stdout or "",
                    "text/plain",
                    logical_name="build.stdout.log",
                    producer_id="lpe.compiler",
                )
                workspace.artifact_store.put_text(
                    result.stderr or "",
                    "text/plain",
                    logical_name="build.stderr.log",
                    producer_id="lpe.compiler",
                )
            status = FindingStatus.PASS if build_ok else FindingStatus.FAIL
            findings.append(
                _finding(
                    check_id="lean.build",
                    dimension=EvidenceDimension.KERNEL,
                    status=status,
                    severity=Severity.INFO if status is FindingStatus.PASS else Severity.L3,
                    summary=(
                        "Exact-environment build passed"
                        if status is FindingStatus.PASS
                        else "Exact-environment build failed"
                    ),
                    details={
                        "exit_code": result.exit_code,
                        "timed_out": result.timed_out,
                        "stdout_hash": sha256_text(result.stdout),
                        "stderr_hash": sha256_text(result.stderr),
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "worktree": str(build_repo),
                        "snapshot_fingerprint": (
                            workspace.snapshot_fingerprint if workspace else None
                        ),
                        "insecure_host_exec": insecure_host_exec,
                        "network_policy": network_policy,
                        "network_isolated": network_isolated,
                        "combined_build_extract": combined_build_extract,
                        "sandbox_invocations": sandbox_invocations,
                    },
                    started=build_started,
                    finished=build_finished,
                    command=list(result.command),
                )
            )

        # Prefer toolchain JSON written by the build / lake exe lpe_extract.
        # Use the same executor as lake build so Docker E2E does not need host Lake.
        # Docker prefers one combined container; sequential extract is the fallback.
        if enable_lean_extraction and candidate.changed_paths:
            if build_ran and not extract_already_done:
                lake_extract = try_run_lake_extract(
                    build_repo,
                    force=False,
                    timeout_seconds=contract.project.execution.timeout_seconds,
                    executor=executor,
                    max_output_bytes=contract.project.execution.max_output_bytes,
                    environment_allowlist=list(contract.project.execution.environment_allowlist),
                )
                extract_executor_name = extract_executor_label(executor)
                if (
                    isinstance(executor, DockerSandboxExecutor)
                    and sandbox_invocations is not None
                    and lake_extract is not None
                ):
                    # Second container only when extract actually invoked the executor
                    # (existing complete JSON short-circuits without a run).
                    if lake_extract.notes and any(
                        "produced by lake exe lpe_extract" in n for n in lake_extract.notes
                    ):
                        sandbox_invocations = 2
                        combined_build_extract = False
                if lake_extract is not None and lake_extract.errors:
                    # Fail closed: do not let adaptive host Lake mask a sandbox miss.
                    pending_extraction = lake_extract
                else:
                    # Docker path: never re-invoke host Lake after sandboxed extract.
                    run_toolchain = not isinstance(executor, DockerSandboxExecutor)
                    pending_extraction = extract_lean_repository(
                        build_repo,
                        run_toolchain=run_toolchain,
                    )
                    if (
                        lake_extract is not None
                        and pending_extraction is not None
                        and lake_extract.notes
                    ):
                        pending_extraction.notes = list(
                            dict.fromkeys([*pending_extraction.notes, *lake_extract.notes])
                        )
            elif build_ran and extract_already_done:
                # Combined path already produced pending_extraction (success or fail-closed).
                if (
                    pending_extraction is not None
                    and not pending_extraction.errors
                    and pending_extraction.complete
                ):
                    # Reload via adaptive loader for import_diff / normalization only.
                    loaded = extract_lean_repository(build_repo, run_toolchain=False)
                    if loaded is not None and pending_extraction.notes:
                        loaded.notes = list(
                            dict.fromkeys([*loaded.notes, *pending_extraction.notes])
                        )
                        pending_extraction = loaded
            elif not build_ran:
                pending_extraction = extract_lean_repository(build_repo)
            # Persist toolchain JSON into the durable CAS root (operator .lpe),
            # while providers continue to read from the live candidate worktree.
            if (
                pending_extraction is not None
                and _is_toolchain_complete(pending_extraction)
                and workspace is not None
            ):
                persist_toolchain_artifact(build_repo, repository_path)
                workspace.artifact_store.put_text(
                    (build_repo / ".lpe" / "lean-extraction.json").read_text(
                        encoding="utf-8", errors="replace"
                    )
                    if (build_repo / ".lpe" / "lean-extraction.json").is_file()
                    else "",
                    "application/json",
                    logical_name="lean-extraction.json",
                    producer_id="lpe.compiler",
                )

        digest_resolved = bool(
            executor_descriptor and getattr(executor_descriptor, "digest_resolved", False)
        )
        iso_status_name, iso_executor = isolation_status_for_executor(
            executor,
            build_ran=build_ran,
            skip_build=skip_build,
            network_isolated=network_isolated,
            image_digest_resolved=digest_resolved,
        )
        isolation_now = datetime.now(UTC)
        if iso_status_name == "PASS":
            iso_status = FindingStatus.PASS
            iso_severity = Severity.INFO
            iso_summary = "Build executed in network-isolated Docker sandbox"
        elif iso_status_name == "NOT_APPLICABLE":
            iso_status = FindingStatus.NOT_APPLICABLE
            iso_severity = Severity.INFO
            iso_summary = "Build was skipped; isolation was not exercised (not claimed as PASS)"
        else:
            iso_status = FindingStatus.UNKNOWN
            iso_severity = Severity.L2
            iso_summary = (
                "Subprocess execution does not independently enforce the configured "
                "network-isolation policy"
                if not network_isolated
                else "Isolation status could not be confirmed for this executor"
            )
        findings.append(
            _finding(
                check_id="execution.isolation",
                dimension=EvidenceDimension.KERNEL,
                status=iso_status,
                severity=iso_severity,
                summary=iso_summary,
                details={
                    "configured_network_policy": network_policy,
                    "executor": iso_executor,
                    "build_ran": build_ran,
                    "skip_build": skip_build,
                    "network_isolated": network_isolated,
                    "insecure_host_exec": insecure_host_exec,
                    "sandbox_preferred": not insecure_host_exec,
                    "extract_executor": extract_executor_name,
                    "combined_build_extract": combined_build_extract,
                    "sandbox_invocations": sandbox_invocations,
                    "required_remedy": (
                        None
                        if iso_status is FindingStatus.PASS
                        else (
                            None
                            if iso_status is FindingStatus.NOT_APPLICABLE
                            else (
                                "install Docker for sandboxed builds with network_policy=deny; "
                                "host subprocess cannot claim network isolation"
                            )
                        )
                    ),
                },
                started=isolation_now,
                finished=isolation_now,
            )
        )

        axiom_started = datetime.now(UTC)
        if enable_lean_extraction and candidate.changed_paths:
            # Full-repo extract so impact edges can reach downstream dependents
            # outside the changed-path set (AUDIT-012). Prefer post-build capture.
            extraction = pending_extraction or extract_lean_repository(repository_path)
            findings.append(_check_axioms(contract, extraction, started=axiom_started))

            graph = build_dependency_graph(extraction)
            changed_names, resolution_warnings = resolve_changed_names_detailed(
                candidate.changed_declarations, extraction
            )
            cone = impact_cone(graph, changed=changed_names)
            impact_now = datetime.now(UTC)
            toolchain_ok = _is_toolchain_complete(extraction)
            if not changed_names and not cone:
                impact_status = FindingStatus.NOT_APPLICABLE
                impact_summary = "No changed declarations supplied for impact analysis"
            elif toolchain_ok:
                impact_status = FindingStatus.PASS
                impact_summary = "Impact cone computed from toolchain dependency graph"
            else:
                # Regex-stub cones are heuristic — never claim toolchain truth (AUDIT-011).
                impact_status = FindingStatus.UNKNOWN
                impact_summary = (
                    "Impact cone estimated via regex-stub dependency graph; not elaborator-complete"
                )
            findings.append(
                _finding(
                    check_id="lean.impact_cone",
                    dimension=EvidenceDimension.KERNEL,
                    status=impact_status,
                    severity=Severity.INFO if impact_status is FindingStatus.PASS else Severity.L2,
                    summary=impact_summary,
                    details={
                        "changed": sorted(changed_names),
                        "impact_cone": sorted(cone),
                        "import_count": len(extraction.imports),
                        "edge_count": len(extraction.dependency_edges),
                        "declaration_edge_count": len(extraction.effective_declaration_edges()),
                        "import_edge_count": len(extraction.import_edges),
                        "extraction_schema_version": getattr(
                            extraction, "extraction_schema_version", "1.0"
                        ),
                        "extractor": extraction.extractor,
                        "complete": getattr(extraction, "complete", False),
                        "notes": list(getattr(extraction, "notes", []) or []),
                        "extract_executor": _extract_executor_from_notes(extraction),
                        "graph_semantics": "dependee->depender (downstream impact)",
                        "resolution_warnings": resolution_warnings,
                    },
                    started=impact_now,
                    finished=impact_now,
                    provider_metadata={"extractor": extraction.extractor},
                )
            )

            import_now = datetime.now(UTC)
            baseline_imports: list[str] = []
            # Compare candidate-touched file imports against empty baseline when no prior
            # extraction artifact is supplied; surface added imports honestly.
            import_diff = extraction.import_diff or import_expansion(
                baseline_imports, extraction.imports
            )
            if (
                not extraction.imports
                and not import_diff.get("added")
                and not import_diff.get("removed")
            ):
                import_status = FindingStatus.NOT_APPLICABLE
                import_summary = "No imports observed in extracted Lean paths"
            elif toolchain_ok:
                import_status = FindingStatus.PASS
                import_summary = "Import expansion computed from toolchain extraction"
            else:
                import_status = FindingStatus.UNKNOWN
                import_summary = "Import expansion from regex-stub only; not elaborator-complete"
            findings.append(
                _finding(
                    check_id="lean.import_expansion",
                    dimension=EvidenceDimension.REPOSITORY,
                    status=import_status,
                    severity=Severity.INFO if import_status is FindingStatus.PASS else Severity.L2,
                    summary=import_summary,
                    details={
                        "imports": extraction.imports,
                        "added": import_diff.get("added", []),
                        "removed": import_diff.get("removed", []),
                        "import_edges": [list(e) for e in extraction.import_edges],
                        "extraction_schema_version": getattr(
                            extraction, "extraction_schema_version", "1.0"
                        ),
                        "semantics": (
                            "added=modules in after\\before; "
                            "removed=modules in before\\after; "
                            "import_edges are module→module when schema≥1.1"
                        ),
                        "extractor": extraction.extractor,
                    },
                    started=import_now,
                    finished=import_now,
                    provider_metadata={"extractor": extraction.extractor},
                )
            )
        else:
            findings.append(
                _finding(
                    check_id="lean.prohibited_axioms",
                    dimension=EvidenceDimension.KERNEL,
                    status=FindingStatus.UNKNOWN,
                    severity=Severity.L3,
                    summary="Axiom dependency closure has not yet been extracted",
                    details={
                        "allowed_axioms": contract.project.allowed_axioms,
                        "required_remedy": "enable lean extraction or supply changed .lean paths",
                    },
                    started=axiom_started,
                    finished=datetime.now(UTC),
                )
            )

        declaration_diff = None
        if workspace is not None and enable_lean_extraction:
            import os as _os

            from lpe.lean.declaration_diff import diff_extractions

            # Live paired extract (2x Lake) remains opt-in: set LPE_PAIRED_EXTRACT=1
            # when a Lean toolchain is available and elaborator-backed base/head
            # diff is required. Default dry-run still records fingerprints and
            # never invents elaborator completeness.
            paired_live = _os.environ.get("LPE_PAIRED_EXTRACT", "0").lower() in {
                "1",
                "true",
                "yes",
            }
            try:
                paired = ws_manager.extract_pair(dry_run=not paired_live)
                if (
                    paired.base.completeness.environment_loaded
                    and paired.candidate.completeness.environment_loaded
                    and not paired.base.has_blocking_errors
                    and not paired.candidate.has_blocking_errors
                ):
                    declaration_diff = diff_extractions(paired.base, paired.candidate)
            except Exception as exc:
                findings.append(
                    _finding(
                        check_id="lean.paired_extract",
                        dimension=EvidenceDimension.UNCERTAINTY,
                        status=FindingStatus.UNKNOWN,
                        severity=Severity.L2,
                        summary=f"Paired Lean extraction unavailable: {exc}",
                        details={"error": str(exc)},
                        started=datetime.now(UTC),
                        finished=datetime.now(UTC),
                    )
                )

        risk_class = classify_risk(candidate, declaration_diff=declaration_diff)

        if enable_semantic_providers:
            assert workspace is not None
            provider_context = ProviderContext(
                workspace=workspace,
                contract=contract,
                candidate=candidate,
                candidate_extraction=pending_extraction,
                cancellation=CancellationToken(),
                provider_deadline=datetime.now(UTC),
            )
            for provider in semantic_providers:
                provider_result = provider.collect(provider_context)
                findings.extend(provider_result.findings)
                for ref in provider_result.artifact_refs:
                    try:
                        workspace.artifact_store.verify(ref)
                    except (OSError, ValueError, FileNotFoundError):
                        pass
        else:
            semantic_started = datetime.now(UTC)
            signature_changes = [
                declaration.name
                for declaration in candidate.changed_declarations
                if declaration.signature_changed
            ]
            semantic_status = (
                FindingStatus.UNKNOWN if signature_changes else FindingStatus.NOT_APPLICABLE
            )
            findings.append(
                _finding(
                    check_id="semantic.intent_fidelity",
                    dimension=EvidenceDimension.SEMANTIC,
                    status=semantic_status,
                    severity=Severity.L3 if signature_changes else Severity.INFO,
                    summary=(
                        "Semantic fidelity requires authorized review for changed signatures"
                        if signature_changes
                        else "No supplied declaration signature change requires semantic comparison"
                    ),
                    details={
                        "changed_signatures": signature_changes,
                        "claimed_intent": candidate.claimed_intent,
                    },
                    started=semantic_started,
                    finished=datetime.now(UTC),
                )
            )

        public_declarations = [
            declaration.name for declaration in candidate.changed_declarations if declaration.public
        ]
        # CLOSURE-015: synthesize canonical api_fit / declared_use / intent_support
        # from provider outputs; do not emit contradictory generic UNKNOWN placeholders.
        _ = public_declarations  # retained for clarity / future coverage summaries
        findings = apply_synthesis(
            findings,
            candidate=candidate,
            risk_class=risk_class,
        )

        persistence_now = datetime.now(UTC)
        findings.append(
            _finding(
                check_id="persistence.follow_up",
                dimension=EvidenceDimension.PERSISTENCE,
                status=FindingStatus.NOT_APPLICABLE,
                severity=Severity.INFO,
                summary="Persistence is measured after integration and cannot be credited yet",
                details={"required_event": "PERSISTENCE_CONFIRMED"},
                started=persistence_now,
                finished=persistence_now,
            )
        )

        rule = contract.policies.risk_rules[risk_class]
        auto_accept_eligible = rule.auto_accept_eligible
        if executor_descriptor is not None and executor_descriptor.blocks_auto_accept:
            auto_accept_eligible = False
        decision = decide(
            findings=findings,
            risk_class=risk_class,
            auto_accept_eligible=auto_accept_eligible,
        )
        estimated_minutes = contract.review.default_review_minutes.get(risk_class, 30)
        question = (
            select_review_question(
                findings=findings,
                risk_class=risk_class,
                required_roles=rule.required_roles,
                estimated_minutes=estimated_minutes,
            )
            if decision.recommendation.value == "ESCALATE"
            else None
        )

        reasons = list(decision.reasons)
        if decision.hard_failures:
            reasons.append("hard failures: " + ", ".join(decision.hard_failures))
        if decision.unresolved_hard_checks:
            reasons.append(
                "unresolved hard-relevant checks (do not treat as axiom-safe): "
                + ", ".join(decision.unresolved_hard_checks)
            )

        assert workspace is not None and workspace.run_manifest is not None
        evidence_fingerprint = compute_evidence_fingerprint(
            workspace.run_manifest,
            [canonical_finding_payload(f) for f in findings],
        )
        coverage_summary: dict[str, EvidenceCoverage] = {}
        for finding in findings:
            if finding.coverage is None:
                continue
            key = finding.dimension.value
            prior = coverage_summary.get(key)
            if prior is None:
                coverage_summary[key] = finding.coverage
            else:
                coverage_summary[key] = EvidenceCoverage(
                    requested_subject_count=(
                        prior.requested_subject_count + finding.coverage.requested_subject_count
                    ),
                    evaluated_subject_count=(
                        prior.evaluated_subject_count + finding.coverage.evaluated_subject_count
                    ),
                    excluded_subject_count=(
                        prior.excluded_subject_count + finding.coverage.excluded_subject_count
                    ),
                    exclusion_reasons=list(
                        dict.fromkeys(
                            [*prior.exclusion_reasons, *finding.coverage.exclusion_reasons]
                        )
                    ),
                    complete_for_declared_scope=(
                        prior.complete_for_declared_scope
                        and finding.coverage.complete_for_declared_scope
                    ),
                    allows_partial_pass=(
                        prior.allows_partial_pass or finding.coverage.allows_partial_pass
                    ),
                )
        hard_gate = HardGateResult(
            passed=decision.hard_gate_passed,
            hard_failures=list(decision.hard_failures),
            unresolved_hard_checks=list(decision.unresolved_hard_checks),
            reasons=list(decision.reasons),
        )
        uncertainty_records = [
            UncertaintyRecord(code="unresolved", message=msg) for msg in decision.uncertainty
        ]
        # Stamp snapshot fingerprint on findings that lack one (V2 identity).
        snap = workspace.snapshot_fingerprint
        stamped: list[EvidenceFinding] = []
        for finding in findings:
            if finding.snapshot_fingerprint:
                stamped.append(finding)
            else:
                stamped.append(finding.model_copy(update={"snapshot_fingerprint": snap}))
        packet = EvidencePacket(
            packet_id=f"packet_{evidence_fingerprint}",
            run_id=run_id,
            project_id=contract.project.project_id,
            contract_hash=contract.contract_hash,
            candidate=candidate,
            risk_class=risk_class,
            findings=stamped,
            hard_gate_passed=decision.hard_gate_passed,
            recommendation=decision.recommendation,
            recommendation_reasons=reasons,
            unresolved_uncertainty=decision.uncertainty,
            review_question=question,
            evidence_fingerprint=evidence_fingerprint,
            recommendation_policy_id=recommendation_policy_id(),
            run_manifest=workspace.run_manifest.model_dump(mode="json"),
            coverage_summary=coverage_summary,
            hard_gate=hard_gate,
            uncertainty_records=uncertainty_records,
        )
        validate_packet_size_budget(packet)
        # Durable persist gate: cleanup only after packet + CAS refs are ready.
        ws_manager.mark_persisted()
        ws_manager.cleanup(force=False)
        if not ws_manager.verify_cleanup():
            # Best-effort second pass
            ws_manager.cleanup(force=True)
        return packet
    finally:
        if workspace is not None and not workspace.cleanup_token.cleaned:
            ws_manager.cleanup(force=True)
