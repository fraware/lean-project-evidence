"""Content-addressed artifact store under ``.lpe/artifacts/sha256/<aa>/<digest>``."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from lpe.execution.redact import redact_secrets
from lpe.hashing import canonical_json, sha256_text
from lpe.models import StrictModel

# Packet may embed at most this many redacted UTF-8 bytes of an excerpt.
MAX_EXCERPT_BYTES = 4 * 1024
# CLOSURE-012: assembled packet must stay under 1 MiB excluding artifact refs.
PACKET_SIZE_BUDGET_BYTES = 1 * 1024 * 1024


class PacketSizeBudgetError(ValueError):
    """Raised when an assembled packet exceeds the size budget."""


class ArtifactReference(StrictModel):
    sha256: str
    media_type: str
    byte_length: int = Field(ge=0)
    logical_name: str
    redaction_applied: bool = False
    producer_id: str
    excerpt: str | None = None


def redact_excerpt(text: str, *, limit: int = MAX_EXCERPT_BYTES) -> str:
    """Redact secrets and cap excerpt size at ``limit`` UTF-8 bytes."""
    cleaned = redact_secrets(text or "")
    encoded = cleaned.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return cleaned
    truncated = encoded[:limit]
    # Avoid splitting a multibyte sequence at the boundary.
    while truncated and (truncated[-1] & 0xC0) == 0x80:
        truncated = truncated[:-1]
    return truncated.decode("utf-8", errors="replace")


def _strip_artifact_refs(node: Any) -> Any:
    """Drop ``artifact_refs`` subtrees so packet budget excludes CAS payloads."""
    if isinstance(node, dict):
        return {
            key: _strip_artifact_refs(value)
            for key, value in node.items()
            if key != "artifact_refs"
        }
    if isinstance(node, list):
        return [_strip_artifact_refs(item) for item in node]
    return node


def packet_bytes_excluding_artifact_refs(packet: Any) -> int:
    """UTF-8 size of canonical packet JSON with artifact refs removed."""
    if hasattr(packet, "model_dump"):
        payload = packet.model_dump(mode="json")
    else:
        payload = dict(packet)
    stripped = _strip_artifact_refs(payload)
    return len(canonical_json(stripped).encode("utf-8"))


def validate_packet_size_budget(
    packet: Any,
    *,
    budget: int = PACKET_SIZE_BUDGET_BYTES,
) -> int:
    """Fail closed when packet size (excl. artifact refs) exceeds ``budget``.

    Returns the measured byte count on success.
    """
    size = packet_bytes_excluding_artifact_refs(packet)
    if size > budget:
        raise PacketSizeBudgetError(
            f"evidence packet exceeds size budget: {size} bytes > {budget} "
            "(excluding artifact refs)"
        )
    return size


class ContentAddressedArtifactStore:
    """CAS layout: ``.lpe/artifacts/sha256/<first-two>/<digest>``."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._cas = self.root / ".lpe" / "artifacts" / "sha256"
        self._cas.mkdir(parents=True, exist_ok=True)

    def _path_for(self, digest: str) -> Path:
        if len(digest) < 2 or any(c not in "0123456789abcdef" for c in digest.lower()):
            raise ValueError(f"invalid sha256 digest: {digest!r}")
        digest = digest.lower()
        return self._cas / digest[:2] / digest

    def put_bytes(
        self,
        data: bytes,
        *,
        media_type: str,
        logical_name: str,
        producer_id: str,
        redact: bool = True,
        include_excerpt: bool = True,
    ) -> ArtifactReference:
        text: str | None = None
        payload = data
        redaction_applied = False
        if redact:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            if text is not None:
                cleaned = redact_secrets(text)
                if cleaned != text:
                    redaction_applied = True
                payload = cleaned.encode("utf-8")
                text = cleaned
        digest = __import__("hashlib").sha256(payload).hexdigest()
        dest = self._path_for(digest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_bytes(payload)
        excerpt = None
        if include_excerpt and text is not None:
            excerpt = redact_excerpt(text)
        elif include_excerpt:
            excerpt = None
        return ArtifactReference(
            sha256=digest,
            media_type=media_type,
            byte_length=len(payload),
            logical_name=logical_name,
            redaction_applied=redaction_applied,
            producer_id=producer_id,
            excerpt=excerpt,
        )

    def put_text(
        self,
        content: str,
        media_type: str,
        *,
        logical_name: str = "artifact.txt",
        producer_id: str = "lpe",
        redact: bool = True,
        include_excerpt: bool = True,
    ) -> ArtifactReference:
        return self.put_bytes(
            content.encode("utf-8"),
            media_type=media_type,
            logical_name=logical_name,
            producer_id=producer_id,
            redact=redact,
            include_excerpt=include_excerpt,
        )

    def get_bytes(self, digest: str) -> bytes:
        path = self._path_for(digest)
        if not path.is_file():
            raise FileNotFoundError(f"artifact not found: {digest}")
        return path.read_bytes()

    def get_text(self, digest: str) -> str:
        return self.get_bytes(digest).decode("utf-8")

    def verify(self, ref: ArtifactReference) -> Literal["ok"]:
        data = self.get_bytes(ref.sha256)
        actual = __import__("hashlib").sha256(data).hexdigest()
        if actual != ref.sha256.lower():
            raise ValueError(f"artifact digest mismatch: expected {ref.sha256}, got {actual}")
        if len(data) != ref.byte_length:
            raise ValueError(
                f"artifact length mismatch for {ref.sha256}: "
                f"expected {ref.byte_length}, got {len(data)}"
            )
        return "ok"

    def path_for(self, digest: str) -> Path:
        return self._path_for(digest)


def sha256_of_text(content: str) -> str:
    return sha256_text(content)
