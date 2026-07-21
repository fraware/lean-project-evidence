"""Ledger 0.1 → 0.2 migration and resealing (CLOSURE-020).

Preserves every source event. Ambiguous records become typed
``LEGACY_UNRESOLVED`` wrappers. Never invents acceptance or persistence.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpe.hashing import sha256_value
from lpe.ledger.events import (
    LEGACY_UNRESOLVED,
    EventTypeV2,
    LegacyUnresolvedPayload,
    UtilityEventV2,
)
from lpe.ledger.seal import write_seal
from lpe.ledger.store import LedgerIntegrityError, LedgerStore
from lpe.models import EventType, UtilityEvent

# Map legacy event types to V2 when a faithful typed mapping is unavailable.
_LEGACY_TYPE_MAP: dict[str, EventTypeV2] = {
    EventType.OBLIGATION_REGISTERED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.CANDIDATE_REGISTERED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.EVIDENCE_COMPILED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.REVIEW_REQUESTED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.REVIEW_SUBMITTED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.REPAIR_STARTED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.REPAIR_COMPLETED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.ARTIFACT_ACCEPTED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.ARTIFACT_REJECTED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.ARTIFACT_INTEGRATED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.DOWNSTREAM_ENABLED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.PERSISTENCE_CONFIRMED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.REGRESSION_DETECTED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.EXPERT_TIME_RECORDED.value: EventTypeV2.LEGACY_UNRESOLVED,
    EventType.CORRECTION_RECORDED.value: EventTypeV2.LEGACY_UNRESOLVED,
}


class LedgerMigrationError(RuntimeError):
    """Raised when migration cannot complete fail-closed."""


def migrate_legacy_event(event: UtilityEvent, *, index: int) -> UtilityEventV2:
    """Wrap a 0.1 UtilityEvent as UtilityEventV2 without inventing fields.

    Acceptance/persistence flags present in legacy payloads are preserved inside
    ``legacy_payload`` but are marked unresolved — consumers must not treat them
    as quorum-derived truth.
    """
    unresolved_fields = [LEGACY_UNRESOLVED]
    payload_keys = sorted(event.payload.keys()) if isinstance(event.payload, dict) else []
    for key in ("semantic_fidelity", "repository_accepted", "implementation_accepted"):
        if key in (event.payload or {}):
            unresolved_fields.append(f"legacy_{key}")

    v2_type = _LEGACY_TYPE_MAP.get(event.event_type.value, EventTypeV2.LEGACY_UNRESOLVED)
    obligation_ids = [event.obligation_id] if event.obligation_id else []
    return UtilityEventV2(
        event_id=event.event_id,
        event_type=v2_type,
        project_id=event.project_id,
        artifact_id=event.artifact_id,
        obligation_ids=obligation_ids,
        occurred_at=event.occurred_at,
        recorded_at=event.occurred_at,
        actor_id=event.actor_id,
        payload=LegacyUnresolvedPayload(
            legacy_event_type=event.event_type.value,
            legacy_payload=dict(event.payload or {}),
            unresolved_fields=unresolved_fields,
            migration_note=(
                f"{LEGACY_UNRESOLVED}: preserved source event #{index}; "
                f"payload_keys={payload_keys}; acceptance/persistence not inferred"
            ),
        ),
        supersedes_event_id=event.supersedes_event_id,
    )


def _mapping_entry(index: int, event: UtilityEvent, migrated: UtilityEventV2) -> dict[str, Any]:
    return {
        "index": index,
        "source_event_id": event.event_id,
        "source_event_type": event.event_type.value,
        "target_event_id": migrated.event_id,
        "target_event_type": migrated.event_type.value,
        "payload_type": migrated.payload.payload_type,
        "unresolved": LEGACY_UNRESOLVED,
        "invented_acceptance": False,
        "invented_persistence": False,
    }


def migrate_ledger(
    source: Path,
    target: Path,
    mapping_report: Path,
    *,
    source_seal: Path | None = None,
    target_seal: Path | None = None,
) -> dict[str, Any]:
    """Migrate ledger 0.1 → 0.2, verify both chains, emit linked seals + report.

    Idempotent when ``target`` already exists: re-verify source/target chains,
    recompute the mapping without rewriting history, and refresh seals/report.
    Never invents acceptance or persistence.
    """
    if source.resolve() == target.resolve():
        raise LedgerMigrationError("source and target ledger paths must differ")

    source_store = LedgerStore(source)
    try:
        source_store.verify()
    except LedgerIntegrityError as exc:
        raise LedgerMigrationError(f"source ledger verify failed: {exc}") from exc

    source_events = source_store.events()
    target_exists = target.exists()

    if target_exists:
        target_store = LedgerStore(target)
        try:
            target_store.verify()
        except LedgerIntegrityError as exc:
            raise LedgerMigrationError(f"target ledger exists but verify failed: {exc}") from exc
        target_events = target_store.events_v2()
        if len(target_events) != len(source_events):
            raise LedgerMigrationError(
                f"target ledger already exists with mismatched event count: "
                f"source={len(source_events)} target={len(target_events)}"
            )
        for index, (src, dst) in enumerate(zip(source_events, target_events, strict=True)):
            if src.event_id != dst.event_id:
                raise LedgerMigrationError(
                    f"target ledger already exists but event_id mismatch at "
                    f"index {index}: source={src.event_id!r} target={dst.event_id!r}"
                )
            if dst.event_type is not EventTypeV2.LEGACY_UNRESOLVED:
                raise LedgerMigrationError(
                    f"target event {dst.event_id} is not LEGACY_UNRESOLVED; "
                    "refuse idempotent re-run over a non-migration ledger"
                )
        mappings = [
            _mapping_entry(index, src, dst)
            for index, (src, dst) in enumerate(zip(source_events, target_events, strict=True))
        ]
    else:
        target_store = LedgerStore(target)
        target_store.initialize()
        mappings = []
        for index, event in enumerate(source_events):
            migrated = migrate_legacy_event(event, index=index)
            # LEGACY_UNRESOLVED is a side-channel type — append without lifecycle
            # gating conflicts across arbitrary historical sequences.
            target_store.append_v2(migrated)
            mappings.append(_mapping_entry(index, event, migrated))

        try:
            target_store.verify()
        except LedgerIntegrityError as exc:
            raise LedgerMigrationError(f"target ledger verify failed: {exc}") from exc

        if len(target_store.events_v2()) != len(source_events):
            raise LedgerMigrationError(
                f"event count mismatch: source={len(source_events)} "
                f"target={len(target_store.events_v2())}"
            )

    source_seal_result = write_seal(source_store, source_seal)
    target_seal_result = write_seal(target_store, target_seal)

    source_seal_hash = sha256_value(source_seal_result["manifest"])
    target_seal_hash = sha256_value(target_seal_result["manifest"])

    # Link seals: stamp prior/source relationship into report (seals themselves
    # carry sequence/prior via seal.py v2 fields).
    report = {
        "schema_version": "0.2.0",
        "kind": "lpe.ledger.migration_report",
        "migrated_at": datetime.now(UTC).isoformat(),
        "source_ledger": str(source.resolve()),
        "target_ledger": str(target.resolve()),
        "source_event_count": len(source_events),
        "target_event_count": len(mappings),
        "all_source_events_accounted": len(mappings) == len(source_events),
        "invented_acceptance": False,
        "invented_persistence": False,
        "idempotent_rerun": target_exists,
        "source_seal_path": source_seal_result["seal_path"],
        "target_seal_path": target_seal_result["seal_path"],
        "source_seal_hash": source_seal_hash,
        "target_seal_hash": target_seal_hash,
        "linked_seals": {
            "source_seal_hash": source_seal_hash,
            "target_seal_hash": target_seal_hash,
            "relation": "migration_0_1_to_0_2",
        },
        "mappings": mappings,
    }
    mapping_report.parent.mkdir(parents=True, exist_ok=True)
    mapping_report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
