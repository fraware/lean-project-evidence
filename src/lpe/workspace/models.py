"""Immutable evaluation workspace and run provenance models (CLOSURE-001/011)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from lpe.models import StrictModel

if TYPE_CHECKING:
    from lpe.execution.protocol import LeanExecutor
    from lpe.workspace.artifacts import ContentAddressedArtifactStore


class ExecutorDescriptor(StrictModel):
    """Pinned executor identity for packet / RunManifest provenance (CLOSURE-004)."""

    backend: Literal["docker", "host"]
    image_reference: str | None = None
    image_digest: str | None = None
    network_policy: Literal["deny", "allow"] = "deny"
    uid: int | None = None
    gid: int | None = None
    memory_bytes: int = 2 * 1024 * 1024 * 1024
    cpu_quota: float = 2.0
    pids_limit: int = 256
    readonly_root: bool = True
    source_mount_readonly: bool = True

    @property
    def digest_resolved(self) -> bool:
        return self.backend == "docker" and bool(self.image_digest)

    @property
    def blocks_auto_accept(self) -> bool:
        """Host mode or unresolved Docker digest cannot support automatic acceptance."""
        if self.backend == "host":
            return True
        return not self.digest_resolved


@dataclass
class WorkspaceCleanupToken:
    """Mutable gate: cleanup is allowed only after durable packet persistence."""

    run_id: str
    packet_persisted: bool = False
    cleaned: bool = False

    def mark_packet_persisted(self) -> None:
        self.packet_persisted = True

    def mark_cleaned(self) -> None:
        self.cleaned = True

    def may_cleanup(self) -> bool:
        return self.packet_persisted and not self.cleaned


class RunManifest(StrictModel):
    """Canonical run identity hashed into the evidence fingerprint (CLOSURE-011)."""

    schema_version: Literal["0.2.0"] = "0.2.0"
    run_id: str
    project_id: str
    candidate_id: str
    base_commit: str
    candidate_commit: str
    base_tree_hash: str
    candidate_tree_hash: str
    patch_sha256: str | None = None
    contract_hash: str
    obligation_freeze_hash: str
    lean_toolchain_sha256: str
    lake_manifest_sha256: str | None = None
    compiler_version: str
    extraction_protocol_version: str = "1.0"
    provider_versions: dict[str, str] = Field(default_factory=dict)
    executor: ExecutorDescriptor
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def fingerprint_payload(self) -> dict[str, Any]:
        """Canonical fields for hashing — excludes run_id and created_at."""
        data = self.model_dump(mode="json")
        data.pop("run_id", None)
        data.pop("created_at", None)
        return data


@dataclass(frozen=True)
class EvaluationWorkspace:
    """Frozen candidate-consistent evaluation context (CLOSURE-001)."""

    run_id: str
    repository_origin: Path
    base_path: Path
    candidate_path: Path
    base_commit: str
    head_commit: str | None
    patch_sha256: str | None
    base_tree_hash: str
    candidate_tree_hash: str
    contract_hash: str
    obligation_freeze_hash: str
    executor: LeanExecutor
    executor_descriptor: ExecutorDescriptor
    artifact_store: ContentAddressedArtifactStore
    cleanup_token: WorkspaceCleanupToken
    run_manifest: RunManifest | None = None
    # Ephemeral root holding worktrees / copies; removed on cleanup.
    session_root: Path | None = None
    git_backed: bool = False

    @property
    def snapshot_fingerprint(self) -> str:
        from lpe.hashing import sha256_value

        return sha256_value(
            {
                "base_tree_hash": self.base_tree_hash,
                "candidate_tree_hash": self.candidate_tree_hash,
                "patch_sha256": self.patch_sha256,
                "contract_hash": self.contract_hash,
                "obligation_freeze_hash": self.obligation_freeze_hash,
                "executor": self.executor_descriptor.model_dump(mode="json"),
            }
        )
