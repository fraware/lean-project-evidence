"""Provider contract: ProviderContext in, ProviderResult out (CLOSURE-002)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import Field

from lpe.execution.protocol import DEFAULT_RESOURCE_PROFILES, ProviderResourceProfile
from lpe.models import CandidateDescriptor, EvidenceFinding, ProjectContract, StrictModel
from lpe.paths import PathTraversalError, assert_safe_repo_relative
from lpe.workspace.artifacts import ArtifactReference

if TYPE_CHECKING:
    from lpe.workspace.models import EvaluationWorkspace


class CancellationToken:
    """Cooperative cancellation for provider deadlines."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def check(self) -> None:
        if self._cancelled:
            raise TimeoutError("provider cancelled")


@dataclass(frozen=True)
class ProviderContext:
    """Workspace-scoped provider input. Never uses the operator checkout as root."""

    workspace: EvaluationWorkspace
    contract: ProjectContract
    candidate: CandidateDescriptor
    base_extraction: Any | None = None
    candidate_extraction: Any | None = None
    cancellation: CancellationToken = field(default_factory=CancellationToken)
    provider_deadline: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def candidate_path(self) -> Path:
        return self.workspace.candidate_path

    @property
    def base_path(self) -> Path:
        return self.workspace.base_path

    @property
    def snapshot_fingerprint(self) -> str:
        return self.workspace.snapshot_fingerprint

    def resolve_candidate_path(self, relative: str, *, label: str = "path") -> Path:
        """Resolve ``relative`` under the candidate snapshot only."""
        return assert_safe_repo_relative(self.workspace.candidate_path, relative, label=label)

    def resolve_base_path(self, relative: str, *, label: str = "path") -> Path:
        """Resolve ``relative`` under the base snapshot only."""
        return assert_safe_repo_relative(self.workspace.base_path, relative, label=label)

    def resource_profile_for(self, provider_id: str) -> ProviderResourceProfile:
        return DEFAULT_RESOURCE_PROFILES.get(
            provider_id,
            ProviderResourceProfile(
                timeout_seconds=120,
                max_stdout_bytes=512 * 1024,
                max_stderr_bytes=512 * 1024,
                memory_bytes=1 * 1024 * 1024 * 1024,
                pids_limit=256,
                cpu_quota=1.0,
            ),
        )


class ProviderResult(StrictModel):
    schema_version: Literal["0.2.0"] = "0.2.0"
    provider_id: str
    provider_version: str
    snapshot_fingerprint: str
    findings: list[EvidenceFinding] = Field(default_factory=list)
    artifact_refs: list[ArtifactReference] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime
    status: Literal["COMPLETED", "TIMED_OUT", "FAILED", "CANCELLED"] = "COMPLETED"


class EvidenceProvider(Protocol):
    provider_id: str
    provider_version: str

    def collect(self, context: ProviderContext) -> ProviderResult: ...


class ArtifactStore(Protocol):
    def put_text(self, content: str, media_type: str) -> str: ...
    def get_text(self, digest: str) -> str: ...


def ensure_under_workspace(root: Path, target: Path) -> Path:
    """Fail closed if ``target`` escapes ``root``."""
    resolved_root = root.resolve()
    resolved = target.resolve()
    if resolved != resolved_root and not resolved.is_relative_to(resolved_root):
        raise PathTraversalError(f"path escapes workspace root: {target}")
    return resolved
