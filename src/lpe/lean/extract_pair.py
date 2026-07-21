"""Paired base/candidate Lean extraction with fingerprint reuse gates (CLOSURE-008)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from lpe.hashing import sha256_value
from lpe.lean.generic import (
    read_toolchain_spec,
    run_generic_extract,
    snapshot_fingerprint_for,
    try_generic_extract,
)
from lpe.lean.models import (
    EXTRACTION_PROTOCOL_VERSION,
    ExtractionError,
    LeanExtractionResultV2,
    empty_extraction_v2,
)

if TYPE_CHECKING:
    from lpe.execution.protocol import LeanExecutor
    from lpe.workspace.artifacts import ContentAddressedArtifactStore
    from lpe.workspace.models import EvaluationWorkspace

ARTIFACT_LOGICAL_BASE = "lean-extraction-v2.base.json"
ARTIFACT_LOGICAL_HEAD = "lean-extraction-v2.head.json"


class StaleExtractionError(RuntimeError):
    """Raised when a cached extraction fingerprint does not match the snapshot."""


@dataclass(frozen=True)
class ExtractionFingerprint:
    tree_hash: str
    toolchain_spec: str
    protocol_version: str = EXTRACTION_PROTOCOL_VERSION

    @property
    def digest(self) -> str:
        return snapshot_fingerprint_for(
            tree_hash=self.tree_hash,
            toolchain_spec=self.toolchain_spec,
            protocol_version=self.protocol_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tree_hash": self.tree_hash,
            "toolchain_spec": self.toolchain_spec,
            "protocol_version": self.protocol_version,
            "digest": self.digest,
        }


@dataclass(frozen=True)
class PairedExtraction:
    base: LeanExtractionResultV2
    candidate: LeanExtractionResultV2
    base_fingerprint: ExtractionFingerprint
    candidate_fingerprint: ExtractionFingerprint
    base_artifact_digest: str | None = None
    candidate_artifact_digest: str | None = None
    reused_base: bool = False
    reused_candidate: bool = False

    @property
    def both_ok(self) -> bool:
        return not self.base.has_blocking_errors and not self.candidate.has_blocking_errors


def fingerprint_for_path(path: Path, *, tree_hash: str) -> ExtractionFingerprint:
    return ExtractionFingerprint(
        tree_hash=tree_hash,
        toolchain_spec=read_toolchain_spec(path),
    )


def assert_artifact_fresh(
    result: LeanExtractionResultV2,
    expected: ExtractionFingerprint,
    *,
    label: str,
) -> None:
    """Refuse stale artifacts whose snapshot fingerprint does not match."""
    if result.snapshot_fingerprint != expected.digest:
        raise StaleExtractionError(
            f"stale {label} extraction: artifact fingerprint "
            f"{result.snapshot_fingerprint!r} != expected {expected.digest!r} "
            f"(tree/toolchain/protocol change invalidates reuse)"
        )
    if result.toolchain_spec and result.toolchain_spec != expected.toolchain_spec:
        raise StaleExtractionError(
            f"stale {label} extraction: toolchain {result.toolchain_spec!r} "
            f"!= {expected.toolchain_spec!r}"
        )


def _load_cached(
    store: ContentAddressedArtifactStore,
    *,
    logical_name: str,
    expected: ExtractionFingerprint,
    label: str,
) -> LeanExtractionResultV2 | None:
    """Attempt to load a prior CAS artifact by scanning store index — not available.

    CAS is content-addressed without a name index; callers pass an explicit digest
    via ``reuse_digests`` when known. This helper validates an on-disk path cache.
    """
    del store, logical_name, expected, label
    return None


def _persist(
    store: ContentAddressedArtifactStore | None,
    result: LeanExtractionResultV2,
    *,
    logical_name: str,
    producer_id: str = "lpe.lean.extract_pair",
) -> str | None:
    if store is None:
        return None
    payload = json.dumps(result.to_protocol_dict(), indent=2, sort_keys=True) + "\n"
    ref = store.put_text(
        payload,
        "application/json",
        logical_name=logical_name,
        producer_id=producer_id,
    )
    return ref.sha256


def extract_pair(
    *,
    base_path: Path,
    candidate_path: Path,
    base_tree_hash: str,
    candidate_tree_hash: str,
    executor: LeanExecutor | None = None,
    artifact_store: ContentAddressedArtifactStore | None = None,
    reuse_base: LeanExtractionResultV2 | None = None,
    reuse_candidate: LeanExtractionResultV2 | None = None,
    dry_run: bool = False,
    timeout_seconds: int = 600,
) -> PairedExtraction:
    """Independently extract base and candidate snapshots (§9.5 / CLOSURE-008).

    Tree or toolchain changes invalidate reuse; mismatched fingerprints raise
    ``StaleExtractionError`` (fail closed — never silent reuse).
    """
    base_fp = fingerprint_for_path(base_path, tree_hash=base_tree_hash)
    cand_fp = fingerprint_for_path(candidate_path, tree_hash=candidate_tree_hash)

    reused_base = False
    reused_candidate = False

    if reuse_base is not None:
        assert_artifact_fresh(reuse_base, base_fp, label="base")
        base_result = reuse_base
        reused_base = True
    else:
        base_result = run_generic_extract(
            base_path,
            snapshot_fingerprint=base_fp.digest,
            executor=executor,
            tree_hash=base_tree_hash,
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
        )

    if reuse_candidate is not None:
        assert_artifact_fresh(reuse_candidate, cand_fp, label="candidate")
        cand_result = reuse_candidate
        reused_candidate = True
    else:
        cand_result = run_generic_extract(
            candidate_path,
            snapshot_fingerprint=cand_fp.digest,
            executor=executor,
            tree_hash=candidate_tree_hash,
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
        )

    # Ensure fingerprints are stamped even if Lean omitted them.
    if base_result.snapshot_fingerprint != base_fp.digest:
        base_result = base_result.model_copy(update={"snapshot_fingerprint": base_fp.digest})
    if cand_result.snapshot_fingerprint != cand_fp.digest:
        cand_result = cand_result.model_copy(update={"snapshot_fingerprint": cand_fp.digest})

    base_digest = _persist(artifact_store, base_result, logical_name=ARTIFACT_LOGICAL_BASE)
    cand_digest = _persist(artifact_store, cand_result, logical_name=ARTIFACT_LOGICAL_HEAD)

    return PairedExtraction(
        base=base_result,
        candidate=cand_result,
        base_fingerprint=base_fp,
        candidate_fingerprint=cand_fp,
        base_artifact_digest=base_digest,
        candidate_artifact_digest=cand_digest,
        reused_base=reused_base,
        reused_candidate=reused_candidate,
    )


def extract_pair_for_workspace(
    workspace: EvaluationWorkspace,
    *,
    dry_run: bool = False,
    reuse_base: LeanExtractionResultV2 | None = None,
    reuse_candidate: LeanExtractionResultV2 | None = None,
    timeout_seconds: int = 600,
) -> PairedExtraction:
    """Run paired extract against an EvaluationWorkspace's base/candidate paths."""
    return extract_pair(
        base_path=workspace.base_path,
        candidate_path=workspace.candidate_path,
        base_tree_hash=workspace.base_tree_hash,
        candidate_tree_hash=workspace.candidate_tree_hash,
        executor=workspace.executor,
        artifact_store=workspace.artifact_store,
        reuse_base=reuse_base,
        reuse_candidate=reuse_candidate,
        dry_run=dry_run,
        timeout_seconds=timeout_seconds,
    )


def invalidate_reuse_reason(
    cached: LeanExtractionResultV2,
    *,
    tree_hash: str,
    toolchain_spec: str,
) -> str | None:
    """Return a human reason if cached artifact must not be reused, else None."""
    expected = ExtractionFingerprint(tree_hash=tree_hash, toolchain_spec=toolchain_spec)
    if cached.snapshot_fingerprint != expected.digest:
        return (
            f"fingerprint mismatch: cached={cached.snapshot_fingerprint} expected={expected.digest}"
        )
    if cached.toolchain_spec and cached.toolchain_spec != toolchain_spec:
        return f"toolchain changed: cached={cached.toolchain_spec!r} current={toolchain_spec!r}"
    return None


Side = Literal["base", "candidate"]


def load_extraction_json(path: Path) -> LeanExtractionResultV2:
    data = json.loads(path.read_text(encoding="utf-8"))
    return LeanExtractionResultV2.model_validate(data)


def fallback_pair_when_generic_unavailable(
    *,
    base_path: Path,
    candidate_path: Path,
    base_tree_hash: str,
    candidate_tree_hash: str,
    reason: str,
) -> PairedExtraction:
    """Emit incomplete paired stubs when generic injection cannot run."""
    base_fp = fingerprint_for_path(base_path, tree_hash=base_tree_hash)
    cand_fp = fingerprint_for_path(candidate_path, tree_hash=candidate_tree_hash)
    err = ExtractionError(
        code="GENERIC_EXTRACT_UNAVAILABLE",
        message=reason,
        actionable="Enable Lake/Docker executor or fix module discovery",
    )
    return PairedExtraction(
        base=empty_extraction_v2(
            snapshot_fingerprint=base_fp.digest,
            toolchain_spec=base_fp.toolchain_spec,
            errors=[err],
            notes=["paired extract fallback stub"],
        ),
        candidate=empty_extraction_v2(
            snapshot_fingerprint=cand_fp.digest,
            toolchain_spec=cand_fp.toolchain_spec,
            errors=[err],
            notes=["paired extract fallback stub"],
        ),
        base_fingerprint=base_fp,
        candidate_fingerprint=cand_fp,
    )


# Re-export for manager wiring convenience.
__all__ = [
    "ARTIFACT_LOGICAL_BASE",
    "ARTIFACT_LOGICAL_HEAD",
    "ExtractionFingerprint",
    "PairedExtraction",
    "StaleExtractionError",
    "assert_artifact_fresh",
    "extract_pair",
    "extract_pair_for_workspace",
    "fallback_pair_when_generic_unavailable",
    "fingerprint_for_path",
    "invalidate_reuse_reason",
    "load_extraction_json",
    "sha256_value",
    "try_generic_extract",
]
