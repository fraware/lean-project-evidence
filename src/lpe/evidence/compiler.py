from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lpe import __version__
from lpe.contract.loader import load_contract, validate_candidate_obligations
from lpe.evidence.gates import decide
from lpe.evidence.risk import classify_risk
from lpe.evidence.router import select_review_question
from lpe.execution.allowlist import validate_build_command
from lpe.execution.protocol import LeanExecutor
from lpe.execution.runner import SubprocessLeanExecutor
from lpe.execution.sandbox import (
    DockerSandboxExecutor,
    combined_build_extract_enabled,
    isolation_status_for_executor,
    parse_combined_phase,
)
from lpe.execution.worktree import create_isolated_worktree, store_execution_logs
from lpe.git.candidate import enrich_candidate_from_git
from lpe.git.diff import GitError
from lpe.hashing import sha256_text, sha256_value
from lpe.ids import new_id
from lpe.paths import PathTraversalError, assert_safe_repo_relative
from lpe.lean.extractor import (
    REGEX_STUB_EXTRACTOR,
    TOOLCHAIN_EXTRACTOR,
    build_dependency_graph,
    extract_lean_repository,
    impact_cone,
    import_expansion,
    resolve_changed_names_detailed,
    resolve_changed_names_for_cone,
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
    EvidenceDimension,
    EvidenceFinding,
    EvidencePacket,
    FindingStatus,
    ProjectContract,
    Provenance,
    Severity,
)
from lpe.providers.semantic import (
    CounterexampleProvider,
    DownstreamReplacementProvider,
    DuplicateRetrievalProvider,
    ExampleRunnerProvider,
    StatementDiffProvider,
)

# Extractors that cannot prove axiom closure — never PASS lean.prohibited_axioms.
_INCOMPLETE_AXIOM_EXTRACTORS = frozenset(
    {
        REGEX_STUB_EXTRACTOR,
        "lean.regex-extractor",  # legacy id
        "lean.adaptive-extractor",
    }
)


class HostExecutionRefusedError(RuntimeError):
    """Raised when a host subprocess build would run without an explicit insecure opt-in."""


class NetworkPolicyError(RuntimeError):
    """Raised when network_policy cannot be enforced with the selected executor."""


def _normalize_network_policy(policy: str) -> str:
    normalized = (policy or "deny").strip().lower()
    if normalized not in {"deny", "allow"}:
        # Fail closed: unknown policies are treated as deny.
        return "deny"
    return normalized


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
            command=command,
            output={"status": status, "summary": summary},
            provider_metadata=provider_metadata,
        ),
    )


def _select_executor(
    *,
    insecure_host_exec: bool,
    network_policy: str,
) -> tuple[LeanExecutor, bool]:
    """Prefer Docker sandbox; refuse host subprocess unless explicitly opted in.

    Returns (executor, network_isolated). network_isolated is True only when Docker
    will run with --network=none.
    """
    policy = _normalize_network_policy(network_policy)

    if policy == "deny":
        # Host subprocess cannot enforce network isolation (AUDIT-019).
        if insecure_host_exec:
            raise NetworkPolicyError(
                "network_policy is 'deny', which requires Docker --network=none. "
                "Host subprocess execution (--insecure-host-exec) cannot enforce "
                "network isolation and is refused. Install Docker, or set "
                "network_policy to 'allow' only for trusted repositories."
            )
        if not DockerSandboxExecutor.is_available():
            raise HostExecutionRefusedError(
                "network_policy is 'deny' and Docker sandbox is unavailable. "
                "Install Docker and ensure it is on PATH. Host builds cannot "
                "satisfy a deny network policy (--insecure-host-exec is not "
                "sufficient when network_policy is deny)."
            )
        return DockerSandboxExecutor(network_none=True), True

    # policy == "allow": sandbox preferred; host opt-in permitted.
    if insecure_host_exec:
        return SubprocessLeanExecutor(), False
    if DockerSandboxExecutor.is_available():
        return DockerSandboxExecutor(network_none=False), False
    raise HostExecutionRefusedError(
        "Docker sandbox is unavailable and host subprocess builds are refused by default "
        "for untrusted repositories. Install Docker and ensure it is on PATH, or pass "
        "--insecure-host-exec to allow unisolated host builds (not recommended)."
    )


def _is_incomplete_axiom_extractor(extractor_id: str) -> bool:
    if extractor_id == TOOLCHAIN_EXTRACTOR:
        return False
    return (
        extractor_id in _INCOMPLETE_AXIOM_EXTRACTORS
        or "regex" in extractor_id
        or extractor_id == REGEX_STUB_EXTRACTOR
    )


def _is_toolchain_complete(extraction) -> bool:
    return (
        extraction.extractor == TOOLCHAIN_EXTRACTOR
        and bool(getattr(extraction, "complete", False))
        and not extraction.errors
    )


def _extract_executor_from_notes(extraction) -> str | None:
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
    contract,
    extraction,
    *,
    started: datetime,
) -> EvidenceFinding:
    allowed = set(contract.project.allowed_axioms)
    used = set(extraction.axioms_used)
    prohibited = sorted(used - allowed)
    incomplete = _is_incomplete_axiom_extractor(extraction.extractor)

    if extraction.errors:
        finished = datetime.now(timezone.utc)
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
        finished = datetime.now(timezone.utc)
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
        finished = datetime.now(timezone.utc)
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
        finished = datetime.now(timezone.utc)
        return _finding(
            check_id="lean.prohibited_axioms",
            dimension=EvidenceDimension.KERNEL,
            status=FindingStatus.UNKNOWN,
            severity=Severity.L3,
            summary=(
                "Toolchain extraction is present but incomplete; "
                "axiom closure remains unresolved"
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

    finished = datetime.now(timezone.utc)
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
        patch_file = assert_safe_repo_relative(
            repository, candidate.patch_path, label="patch_path"
        )
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

    started = datetime.now(timezone.utc)
    if contract is None:
        contract = load_contract(project_path)
    validate_candidate_obligations(
        contract, candidate.project_id, candidate.obligation_ids
    )

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

    finished = datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
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
        token
        for token in contract.project.prohibited_tokens
        if token in scan_material
    ]
    now = datetime.now(timezone.utc)
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

    build_repo = repository_path
    worktree_session = None
    network_policy = _normalize_network_policy(contract.project.execution.network_policy)
    build_ran = False
    network_isolated = False
    executor: LeanExecutor
    # Capture extraction before worktree cleanup so post-build JSON is not lost.
    pending_extraction = None
    extract_executor_name: str | None = None
    sandbox_invocations: int | None = None
    combined_build_extract = False
    extract_already_done = False

    try:
        if use_worktree and candidate.head_commit:
            worktree_session = create_isolated_worktree(
                repository_path,
                head_commit=candidate.head_commit,
            )
            build_repo = worktree_session.worktree_path

        if skip_build:
            now = datetime.now(timezone.utc)
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
            # Do not claim isolation for a build that did not run (AUDIT-006).
            if insecure_host_exec:
                executor = SubprocessLeanExecutor()
                network_isolated = False
            elif DockerSandboxExecutor.is_available() and network_policy == "deny":
                executor = DockerSandboxExecutor(network_none=True)
                network_isolated = True
            elif DockerSandboxExecutor.is_available():
                executor = DockerSandboxExecutor(network_none=False)
                network_isolated = False
            else:
                executor = SubprocessLeanExecutor()
                network_isolated = False
        else:
            executor, network_isolated = _select_executor(
                insecure_host_exec=insecure_host_exec,
                network_policy=network_policy,
            )
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
            build_started = datetime.now(timezone.utc)
            if use_combined:
                out_rel = str(
                    extraction_artifact_path(build_repo).relative_to(build_repo)
                ).replace("\\", "/")
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

            build_finished = datetime.now(timezone.utc)
            build_ran = True
            if worktree_session is not None:
                store_execution_logs(
                    worktree_session, stdout=result.stdout, stderr=result.stderr
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
                        "worktree": str(build_repo) if use_worktree else None,
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
                    environment_allowlist=list(
                        contract.project.execution.environment_allowlist
                    ),
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
                            dict.fromkeys(
                                [*pending_extraction.notes, *lake_extract.notes]
                            )
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
                            dict.fromkeys(
                                [*loaded.notes, *pending_extraction.notes]
                            )
                        )
                        pending_extraction = loaded
            elif not build_ran:
                pending_extraction = extract_lean_repository(build_repo)
            # Persist out of the worktree before cleanup so providers re-reading
            # the primary project path still see toolchain-complete JSON.
            if (
                pending_extraction is not None
                and _is_toolchain_complete(pending_extraction)
                and build_repo.resolve() != repository_path.resolve()
            ):
                persist_toolchain_artifact(build_repo, repository_path)
    finally:
        # Always tear down worktrees, including when build/validation raises.
        if worktree_session is not None:
            worktree_session.cleanup()

    iso_status_name, iso_executor = isolation_status_for_executor(
        executor,
        build_ran=build_ran,
        skip_build=skip_build,
        network_isolated=network_isolated,
    )
    isolation_now = datetime.now(timezone.utc)
    if iso_status_name == "PASS":
        iso_status = FindingStatus.PASS
        iso_severity = Severity.INFO
        iso_summary = "Build executed in network-isolated Docker sandbox"
    elif iso_status_name == "NOT_APPLICABLE":
        iso_status = FindingStatus.NOT_APPLICABLE
        iso_severity = Severity.INFO
        iso_summary = (
            "Build was skipped; isolation was not exercised "
            "(not claimed as PASS)"
        )
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

    axiom_started = datetime.now(timezone.utc)
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
        impact_now = datetime.now(timezone.utc)
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
                "Impact cone estimated via regex-stub dependency graph; "
                "not elaborator-complete"
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
                    "declaration_edge_count": len(
                        extraction.effective_declaration_edges()
                    ),
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

        import_now = datetime.now(timezone.utc)
        baseline_imports: list[str] = []
        # Compare candidate-touched file imports against empty baseline when no prior
        # extraction artifact is supplied; surface added imports honestly.
        import_diff = extraction.import_diff or import_expansion(
            baseline_imports, extraction.imports
        )
        if not extraction.imports and not import_diff.get("added") and not import_diff.get(
            "removed"
        ):
            import_status = FindingStatus.NOT_APPLICABLE
            import_summary = "No imports observed in extracted Lean paths"
        elif toolchain_ok:
            import_status = FindingStatus.PASS
            import_summary = "Import expansion computed from toolchain extraction"
        else:
            import_status = FindingStatus.UNKNOWN
            import_summary = (
                "Import expansion from regex-stub only; not elaborator-complete"
            )
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
                finished=datetime.now(timezone.utc),
            )
        )

    risk_class = classify_risk(candidate)

    if enable_semantic_providers:
        for provider in (
            StatementDiffProvider(),
            ExampleRunnerProvider(),
            CounterexampleProvider(),
            DuplicateRetrievalProvider(),
            DownstreamReplacementProvider(),
        ):
            findings.extend(provider.collect(project_path, contract, candidate))
    else:
        semantic_started = datetime.now(timezone.utc)
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
                finished=datetime.now(timezone.utc),
            )
        )

    public_declarations = [
        declaration.name
        for declaration in candidate.changed_declarations
        if declaration.public
    ]
    now = datetime.now(timezone.utc)
    if public_declarations:
        api_fit_status = FindingStatus.UNKNOWN
        api_fit_severity = Severity.L2
        api_fit_summary = "Repository API fit has not yet been established"
    else:
        # No public surface change → API-fit evidence is not required.
        api_fit_status = FindingStatus.NOT_APPLICABLE
        api_fit_severity = Severity.INFO
        api_fit_summary = (
            "No public declaration changes; repository API fit not applicable"
        )
    findings.append(
        _finding(
            check_id="repository.api_fit",
            dimension=EvidenceDimension.REPOSITORY,
            status=api_fit_status,
            severity=api_fit_severity,
            summary=api_fit_summary,
            details={"public_declarations": public_declarations},
            started=now,
            finished=now,
        )
    )

    now = datetime.now(timezone.utc)
    if public_declarations:
        declared_use_status = FindingStatus.UNKNOWN
        declared_use_severity = Severity.L2
        declared_use_summary = "Declared downstream use has not yet been executed"
    else:
        # Private / docs-only candidates do not yet require executed downstream use.
        declared_use_status = FindingStatus.NOT_APPLICABLE
        declared_use_severity = Severity.INFO
        declared_use_summary = (
            "No public declaration changes; declared downstream use not applicable"
        )
    findings.append(
        _finding(
            check_id="downstream.declared_use",
            dimension=EvidenceDimension.DOWNSTREAM,
            status=declared_use_status,
            severity=declared_use_severity,
            summary=declared_use_summary,
            details={"obligation_ids": candidate.obligation_ids},
            started=now,
            finished=now,
        )
    )

    persistence_now = datetime.now(timezone.utc)
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
    decision = decide(
        findings=findings,
        risk_class=risk_class,
        auto_accept_eligible=rule.auto_accept_eligible,
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
        reasons.append(
            "hard failures: " + ", ".join(decision.hard_failures)
        )
    if decision.unresolved_hard_checks:
        reasons.append(
            "unresolved hard-relevant checks (do not treat as axiom-safe): "
            + ", ".join(decision.unresolved_hard_checks)
        )

    candidate_hash = sha256_value(candidate.model_dump(mode="json"))
    evidence_fingerprint = sha256_value(
        {
            "contract_hash": contract.contract_hash,
            "candidate_hash": candidate_hash,
            "compiler_version": __version__,
        }
    )
    return EvidencePacket(
        packet_id=f"packet_{evidence_fingerprint}",
        run_id=run_id,
        project_id=contract.project.project_id,
        contract_hash=contract.contract_hash,
        candidate=candidate,
        risk_class=risk_class,
        findings=findings,
        hard_gate_passed=decision.hard_gate_passed,
        recommendation=decision.recommendation,
        recommendation_reasons=reasons,
        unresolved_uncertainty=decision.uncertainty,
        review_question=question,
        evidence_fingerprint=evidence_fingerprint,
    )
