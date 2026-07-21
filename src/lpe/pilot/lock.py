"""Pilot data lock (CLOSURE-029 / §15.9).

Verifies protocol freeze, ledger chain, off-host seal, held-out set,
assignment plan, and analysis image digest. Mismatch blocks.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator

from lpe.hashing import sha256_file, sha256_value
from lpe.ledger.seal import LedgerSealError, verify_seal
from lpe.ledger.store import LedgerIntegrityError, LedgerStore
from lpe.models import StrictModel
from lpe.pilot.protocol import ProtocolError, verify_freeze


class DataLockError(ValueError):
    """Raised when data lock preconditions fail (fail-closed)."""


class DataLockRecord(StrictModel):
    schema_version: Literal["0.3.0"] = "0.3.0"
    lock_id: str
    protocol_id: str
    protocol_hash: str
    data_lock_hash: str
    ledger_export_hash: str
    seal_hash: str
    held_out_set_hash: str
    analysis_image_digest: str
    assignment_plan_hash: str
    exclusions_resolved: bool
    locked_at: datetime
    component_hashes: dict[str, str] = Field(default_factory=dict)

    @field_validator("analysis_image_digest")
    @classmethod
    def require_digest(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in {"todo", "tbd", "latest", "local"}:
            raise ValueError("analysis_image_digest must be a concrete content digest, not a tag")
        return cleaned

    @field_validator("locked_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("locked_at must be timezone-aware")
        return value


def _file_hash_or_error(path: Path, label: str, errors: list[str]) -> str | None:
    if not path.is_file():
        errors.append(f"missing {label}: {path}")
        return None
    return sha256_file(path)


def perform_data_lock(
    *,
    protocol_bundle: Path,
    ledger_path: Path,
    seal_path: Path,
    assignment_plan_path: Path,
    analysis_image_digest: str,
    expected_episode_ids: list[str],
    completed_episode_ids: list[str],
    attestation_complete: bool,
    exclusions_resolved: bool,
    held_out_set_path: Path | None = None,
    locked_at: datetime | None = None,
    output_path: Path | None = None,
) -> DataLockRecord:
    """Verify lock preconditions and write a content-addressed lock record."""
    errors: list[str] = []
    protocol_hash = ""
    protocol_id = ""
    expected_held = ""

    try:
        bundle = verify_freeze(protocol_bundle)
        protocol_hash = bundle.protocol_hash
        protocol_id = bundle.protocol.protocol_id
        expected_held = bundle.protocol.held_out_set_hash
        if bundle.analysis.analysis_image_digest:
            if bundle.analysis.analysis_image_digest.strip() != analysis_image_digest.strip():
                errors.append("analysis_image_digest does not match frozen analysis.yaml")
    except ProtocolError as exc:
        errors.append(str(exc))

    held_path = held_out_set_path or (protocol_bundle / "held-out-set.json")
    held_hash = _file_hash_or_error(held_path, "held-out-set", errors)
    if expected_held and held_hash and held_hash != expected_held:
        errors.append("held-out set hash mismatch vs protocol")

    assign_hash = _file_hash_or_error(assignment_plan_path, "assignment plan", errors)

    ledger_export_hash = ""
    seal_hash = ""
    try:
        store = LedgerStore(ledger_path)
        verify_seal(store, seal_path)
        seal_hash = sha256_file(seal_path)
        sealed = json.loads(seal_path.read_text(encoding="utf-8"))
        ledger_export_hash = str(
            sealed.get("export_content_hash") or sealed.get("ledger_export_hash") or ""
        )
        if not ledger_export_hash:
            errors.append("seal missing export_content_hash")
    except (
        LedgerIntegrityError,
        LedgerSealError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        errors.append(f"ledger/seal verification failed: {exc}")

    # Off-host seal requirement (§15.9 / CLOSURE-029).
    from lpe.ledger.seal import is_seal_colocated

    if is_seal_colocated(ledger_path, seal_path):
        errors.append(
            "seal is co-located with ledger; store an off-host/read-only seal copy for data lock"
        )

    missing_episodes = sorted(set(expected_episode_ids) - set(completed_episode_ids))
    if missing_episodes:
        errors.append(f"incomplete episodes: {missing_episodes}")
    if not attestation_complete:
        errors.append("review attestations incomplete")
    if not exclusions_resolved:
        errors.append("exclusions not resolved")

    digest_clean = analysis_image_digest.strip()
    if not digest_clean or digest_clean.lower() in {"todo", "tbd", "latest", "local"}:
        errors.append("analysis image digest missing or non-concrete")

    if errors:
        raise DataLockError("; ".join(errors))

    components = {
        "protocol_hash": protocol_hash,
        "held_out_set_hash": held_hash or "",
        "assignment_plan_hash": assign_hash or "",
        "ledger_export_hash": ledger_export_hash,
        "seal_hash": seal_hash,
        "analysis_image_digest": digest_clean,
    }
    lock_body = {
        "protocol_id": protocol_id,
        "components": components,
        "expected_episodes": sorted(expected_episode_ids),
        "completed_episodes": sorted(completed_episode_ids),
        "exclusions_resolved": exclusions_resolved,
    }
    data_lock_hash = sha256_value(lock_body)
    record = DataLockRecord(
        lock_id=f"lock-{data_lock_hash[:16]}",
        protocol_id=protocol_id,
        protocol_hash=protocol_hash,
        data_lock_hash=data_lock_hash,
        ledger_export_hash=ledger_export_hash,
        seal_hash=seal_hash,
        held_out_set_hash=held_hash or "",
        analysis_image_digest=digest_clean,
        assignment_plan_hash=assign_hash or "",
        exclusions_resolved=True,
        locked_at=locked_at or datetime.now(UTC),
        component_hashes=components,
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(record.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
    return record


def require_locked_for_analysis(lock: DataLockRecord | Path) -> DataLockRecord:
    """Fail closed if analysis is attempted without a verified lock record."""
    if isinstance(lock, Path):
        if not lock.is_file():
            raise DataLockError(f"data lock record missing: {lock}")
        record = DataLockRecord.model_validate(json.loads(lock.read_text(encoding="utf-8")))
    else:
        record = lock
    if not record.data_lock_hash.strip():
        raise DataLockError("data lock hash missing")
    return record


def require_new_analysis_version_after_correction(
    prior_lock: DataLockRecord,
    *,
    correction_event_ids: list[str],
    new_analysis_version: str,
    prior_analysis_version: str = "analysis.v1",
) -> dict[str, Any]:
    """Post-lock corrections mint a new analysis version (never mutate the lock)."""
    if not correction_event_ids:
        raise DataLockError("corrections required to advance analysis version")
    if new_analysis_version == prior_analysis_version:
        raise DataLockError("new analysis version must differ from locked version")
    return {
        "prior_data_lock_hash": prior_lock.data_lock_hash,
        "prior_analysis_version": prior_analysis_version,
        "new_analysis_version": new_analysis_version,
        "correction_event_ids": list(correction_event_ids),
    }
