"""EvaluationWorkspace lifecycle manager (CLOSURE-001)."""

from __future__ import annotations

import os
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpe import __version__
from lpe.execution.protocol import LeanExecutor
from lpe.execution.runner import SubprocessLeanExecutor
from lpe.execution.sandbox import (
    DockerSandboxExecutor,
    build_executor_descriptor,
    resolve_docker_image_digest,
)
from lpe.hashing import sha256_value
from lpe.ids import new_id
from lpe.models import CandidateDescriptor, ProjectContract
from lpe.workspace.artifacts import ContentAddressedArtifactStore
from lpe.workspace.models import (
    EvaluationWorkspace,
    ExecutorDescriptor,
    RunManifest,
    WorkspaceCleanupToken,
)
from lpe.workspace.snapshots import (
    SnapshotPair,
    cleanup_snapshot_pair,
    create_snapshot_pair,
    lake_manifest_hash,
    toolchain_file_hash,
)


class WorkspaceError(RuntimeError):
    pass


class HostExecutionRefusedError(RuntimeError):
    """Raised when a host subprocess build would run without an explicit insecure opt-in."""


class NetworkPolicyError(RuntimeError):
    """Raised when network_policy cannot be enforced with the selected executor."""


def _normalize_network_policy(policy: str) -> str:
    normalized = (policy or "deny").strip().lower()
    if normalized not in {"deny", "allow"}:
        return "deny"
    return normalized


def select_executor(
    *,
    insecure_host_exec: bool,
    network_policy: str,
    memory_bytes: int | None = None,
    cpu_quota: float | None = None,
    pids_limit: int | None = None,
) -> tuple[LeanExecutor, ExecutorDescriptor, bool]:
    """Prefer Docker sandbox; refuse host unless opted in with network_policy=allow.

    Returns (executor, descriptor, network_isolated).
    """
    policy = _normalize_network_policy(network_policy)
    mem = memory_bytes or int(
        os.environ.get("LPE_DOCKER_MEMORY_BYTES", str(2 * 1024 * 1024 * 1024))
    )
    cpus = cpu_quota if cpu_quota is not None else float(os.environ.get("LPE_DOCKER_CPUS", "2"))
    pids = pids_limit if pids_limit is not None else int(os.environ.get("LPE_DOCKER_PIDS", "256"))

    if policy == "deny":
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
        executor = DockerSandboxExecutor(
            network_none=True,
            memory_bytes=mem,
            cpu_quota=cpus,
            pids_limit=pids,
            readonly_root=True,
            source_mount_readonly=True,
        )
        digest = resolve_docker_image_digest(executor.image)
        descriptor = build_executor_descriptor(
            executor,
            network_policy="deny",
            image_digest=digest,
        )
        return executor, descriptor, True

    # policy == "allow"
    if insecure_host_exec:
        warnings.warn(
            "LPE: --insecure-host-exec selected with network_policy=allow. "
            "Host execution produces isolation=UNKNOWN and disables automatic "
            "acceptance. Forbidden in pilot control/instrumented conditions.",
            UserWarning,
            stacklevel=2,
        )
        host_executor: LeanExecutor = SubprocessLeanExecutor()
        descriptor = ExecutorDescriptor(
            backend="host",
            image_reference=None,
            image_digest=None,
            network_policy="allow",
            uid=None,
            gid=None,
            memory_bytes=mem,
            cpu_quota=cpus,
            pids_limit=pids,
            readonly_root=False,
            source_mount_readonly=False,
        )
        return host_executor, descriptor, False

    if DockerSandboxExecutor.is_available():
        allow_executor = DockerSandboxExecutor(
            network_none=False,
            memory_bytes=mem,
            cpu_quota=cpus,
            pids_limit=pids,
            readonly_root=True,
            source_mount_readonly=True,
        )
        digest = resolve_docker_image_digest(allow_executor.image)
        descriptor = build_executor_descriptor(
            allow_executor,
            network_policy="allow",
            image_digest=digest,
        )
        return allow_executor, descriptor, False

    raise HostExecutionRefusedError(
        "Docker sandbox is unavailable and host subprocess builds are refused by default "
        "for untrusted repositories. Install Docker and ensure it is on PATH, or pass "
        "--insecure-host-exec to allow unisolated host builds (not recommended)."
    )


def obligation_freeze_hash(contract: ProjectContract, obligation_ids: list[str]) -> str:
    """Hash the frozen obligation set bound to this candidate."""
    wanted = set(obligation_ids)
    obligations = [
        o.model_dump(mode="json")
        for o in contract.obligations.obligations
        if o.obligation_id in wanted
    ]
    obligations.sort(key=lambda item: item.get("obligation_id", ""))
    return sha256_value(
        {
            "contract_hash": contract.contract_hash,
            "obligation_ids": sorted(obligation_ids),
            "obligations": obligations,
        }
    )


class EvaluationWorkspaceManager:
    """Create, persist against, and clean EvaluationWorkspace instances."""

    def __init__(self, artifact_root: Path | None = None) -> None:
        self._artifact_root = artifact_root
        self._pair: SnapshotPair | None = None
        self._workspace: EvaluationWorkspace | None = None

    @property
    def workspace(self) -> EvaluationWorkspace | None:
        return self._workspace

    def create(
        self,
        repository: Path,
        contract: ProjectContract,
        candidate: CandidateDescriptor,
        *,
        executor: LeanExecutor,
        executor_descriptor: ExecutorDescriptor,
        run_id: str | None = None,
        provider_versions: dict[str, str] | None = None,
        artifact_root: Path | None = None,
    ) -> EvaluationWorkspace:
        repository = repository.resolve()
        run_id = run_id or new_id("run")
        root = artifact_root or self._artifact_root or repository
        store = ContentAddressedArtifactStore(root)

        pair = create_snapshot_pair(
            repository,
            base_commit=candidate.base_commit,
            head_commit=candidate.head_commit,
            patch_text=candidate.patch_text,
            patch_path=candidate.patch_path,
        )
        self._pair = pair

        freeze = obligation_freeze_hash(contract, list(candidate.obligation_ids))
        token = WorkspaceCleanupToken(run_id=run_id)
        toolchain = toolchain_file_hash(pair.candidate_path)
        lake = lake_manifest_hash(pair.candidate_path)

        manifest = RunManifest(
            run_id=run_id,
            project_id=contract.project.project_id,
            candidate_id=candidate.candidate_id,
            base_commit=pair.base_commit,
            candidate_commit=pair.candidate_commit,
            base_tree_hash=pair.base_tree_hash,
            candidate_tree_hash=pair.candidate_tree_hash,
            patch_sha256=pair.patch_sha256,
            contract_hash=contract.contract_hash,
            obligation_freeze_hash=freeze,
            lean_toolchain_sha256=toolchain,
            lake_manifest_sha256=lake,
            compiler_version=__version__,
            provider_versions=dict(provider_versions or {}),
            executor=executor_descriptor,
            created_at=datetime.now(UTC),
        )

        workspace = EvaluationWorkspace(
            run_id=run_id,
            repository_origin=repository,
            base_path=pair.base_path,
            candidate_path=pair.candidate_path,
            base_commit=pair.base_commit,
            head_commit=candidate.head_commit,
            patch_sha256=pair.patch_sha256,
            base_tree_hash=pair.base_tree_hash,
            candidate_tree_hash=pair.candidate_tree_hash,
            contract_hash=contract.contract_hash,
            obligation_freeze_hash=freeze,
            executor=executor,
            executor_descriptor=executor_descriptor,
            artifact_store=store,
            cleanup_token=token,
            run_manifest=manifest,
            session_root=pair.session_root,
            git_backed=pair.git_backed,
        )
        self._workspace = workspace
        return workspace

    def mark_persisted(self) -> None:
        if self._workspace is None:
            raise WorkspaceError("no active workspace")
        self._workspace.cleanup_token.mark_packet_persisted()

    def cleanup(self, *, force: bool = False) -> None:
        """Clean worktrees only after durable persist (unless ``force`` on failure paths)."""
        if self._workspace is None:
            return
        token = self._workspace.cleanup_token
        if token.cleaned:
            return
        if not force and not token.packet_persisted:
            raise WorkspaceError(
                "cleanup refused: packet/artifacts not marked durable; "
                "call mark_persisted() first or pass force=True after failure handling"
            )
        if self._pair is not None:
            cleanup_snapshot_pair(
                self._pair,
                repository=self._workspace.repository_origin,
            )
            self._pair = None
        token.mark_cleaned()

    def verify_cleanup(self) -> bool:
        if self._workspace is None:
            return True
        root = self._workspace.session_root
        if root is None:
            return self._workspace.cleanup_token.cleaned
        return self._workspace.cleanup_token.cleaned and not root.exists()

    def extract_pair(
        self,
        *,
        dry_run: bool = False,
        timeout_seconds: int = 600,
    ) -> Any:
        """Run paired base/candidate generic extraction (CLOSURE-008).

        Updates ``run_manifest.extraction_protocol_version`` to ``2.0`` when a
        manifest is present. Refuses stale reuse via fingerprint gates.
        """
        if self._workspace is None:
            raise WorkspaceError("no active workspace")
        from lpe.lean.extract_pair import extract_pair_for_workspace
        from lpe.lean.models import EXTRACTION_PROTOCOL_VERSION

        paired = extract_pair_for_workspace(
            self._workspace,
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
        )
        manifest = self._workspace.run_manifest
        if (
            manifest is not None
            and manifest.extraction_protocol_version != EXTRACTION_PROTOCOL_VERSION
        ):
            # RunManifest is a pydantic model - replace via model_copy on workspace field.
            updated = manifest.model_copy(
                update={"extraction_protocol_version": EXTRACTION_PROTOCOL_VERSION}
            )
            object.__setattr__(self._workspace, "run_manifest", updated)
        return paired


def compute_evidence_fingerprint(
    run_manifest: RunManifest,
    findings_canonical: list[dict[str, Any]],
) -> str:
    """Hash canonical RunManifest + canonical findings (CLOSURE-011)."""
    return sha256_value(
        {
            "run_manifest": run_manifest.fingerprint_payload(),
            "findings": findings_canonical,
        }
    )


def canonical_finding_payload(finding: Any) -> dict[str, Any]:
    """Strip random IDs and timestamps from a finding for fingerprinting."""
    data = finding.model_dump(mode="json") if hasattr(finding, "model_dump") else dict(finding)
    data.pop("finding_id", None)
    prov = data.get("provenance") or {}
    for key in ("started_at", "finished_at", "elapsed_ms"):
        prov.pop(key, None)
    data["provenance"] = prov
    return data


def stable_finding_id(
    *,
    check_id: str,
    subject_hash: str,
    check_version: str,
) -> str:
    """Deterministic finding id: ``finding_<check_id>_<subject_hash>_<check_version>``."""
    safe_check = check_id.replace(".", "_")
    safe_ver = check_version.replace(".", "_")
    return f"finding_{safe_check}_{subject_hash[:16]}_{safe_ver}"


def subject_hash_for_finding(
    *,
    check_id: str,
    dimension: Any,
    details: dict[str, Any],
) -> str:
    """Stable 16-hex subject digest for finding IDs (CLOSURE-011)."""
    dim = dimension.value if hasattr(dimension, "value") else str(dimension)
    return sha256_value(
        {
            "check_id": check_id,
            "dimension": dim,
            "details": details,
        }
    )[:16]


def make_stable_finding_id(
    *,
    check_id: str,
    dimension: Any,
    details: dict[str, Any],
    check_version: str,
) -> str:
    """Build ``finding_<check>_<subject>_<version>`` from finding subject material."""
    return stable_finding_id(
        check_id=check_id,
        subject_hash=subject_hash_for_finding(
            check_id=check_id, dimension=dimension, details=details
        ),
        check_version=check_version,
    )
