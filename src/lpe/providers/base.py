from __future__ import annotations

from pathlib import Path
from typing import Protocol

from lpe.models import CandidateDescriptor, EvidenceFinding, ProjectContract


class EvidenceProvider(Protocol):
    provider_id: str
    provider_version: str

    def collect(
        self,
        project_path: Path,
        contract: ProjectContract,
        candidate: CandidateDescriptor,
    ) -> list[EvidenceFinding]: ...


class ArtifactStore(Protocol):
    def put_text(self, content: str, media_type: str) -> str: ...
    def get_text(self, digest: str) -> str: ...
