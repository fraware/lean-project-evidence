"""Repair lineage for review cycles (CLOSURE-024)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from lpe.hashing import sha256_value
from lpe.ledger.events import (
    EventTypeV2,
    RepairCompletedPayload,
    RepairRequestedPayload,
    UtilityEventV2,
)
from lpe.review.models import ReviewAttestationV2

_ROOT_RE = re.compile(r"^(?P<root>.+?)(?:\.r(?P<seq>\d+))?$")


class RepairError(ValueError):
    """Raised when repair lineage cannot be constructed."""


@dataclass(frozen=True)
class RepairLineage:
    root_candidate_id: str
    prior_candidate_id: str
    new_candidate_id: str
    repair_sequence: int
    repair_request_ids: tuple[str, ...]
    applied_change_hash: str
    new_evidence_fingerprint: str | None


def root_candidate_id(candidate_id: str) -> str:
    match = _ROOT_RE.match(candidate_id)
    if match is None:
        return candidate_id
    return match.group("root")


def next_repair_candidate_id(prior_candidate_id: str) -> tuple[str, int]:
    """Return ``(root.rN, N)`` for the next repair version."""
    root = root_candidate_id(prior_candidate_id)
    match = _ROOT_RE.match(prior_candidate_id)
    seq = 0
    if match and match.group("seq") is not None:
        seq = int(match.group("seq"))
    nxt = seq + 1
    return f"{root}.r{nxt}", nxt


def build_repair_lineage(
    *,
    prior_candidate_id: str,
    repair_request_ids: list[str],
    applied_change: str | bytes | dict[str, Any],
    new_evidence_fingerprint: str | None = None,
) -> RepairLineage:
    if not repair_request_ids:
        raise RepairError("repair lineage requires at least one repair_request_id")
    new_id, seq = next_repair_candidate_id(prior_candidate_id)
    change_hash = (
        applied_change
        if isinstance(applied_change, str) and len(applied_change) == 64
        else sha256_value(applied_change)
    )
    return RepairLineage(
        root_candidate_id=root_candidate_id(prior_candidate_id),
        prior_candidate_id=prior_candidate_id,
        new_candidate_id=new_id,
        repair_sequence=seq,
        repair_request_ids=tuple(repair_request_ids),
        applied_change_hash=change_hash,
        new_evidence_fingerprint=new_evidence_fingerprint,
    )


def attestations_do_not_transfer(
    prior_attestations: list[ReviewAttestationV2],
    new_candidate_id: str,
) -> list[ReviewAttestationV2]:
    """Prior attestations never transfer to a repaired candidate."""
    del new_candidate_id, prior_attestations
    return []


def repair_requested_event(
    *,
    event_id: str,
    project_id: str,
    artifact_id: str,
    actor_id: str,
    repair_request_id: str,
    candidate_id: str,
    attestations: list[ReviewAttestationV2],
    rationale: str,
    required_change: str | None = None,
    obligation_ids: list[str] | None = None,
) -> UtilityEventV2:
    return UtilityEventV2(
        event_id=event_id,
        event_type=EventTypeV2.REPAIR_REQUESTED,
        project_id=project_id,
        artifact_id=artifact_id,
        obligation_ids=list(obligation_ids or []),
        actor_id=actor_id,
        payload=RepairRequestedPayload(
            repair_request_id=repair_request_id,
            candidate_id=candidate_id,
            attestation_ids=[a.attestation_id for a in attestations],
            rationale=rationale,
            required_change=required_change,
        ),
    )


def repair_completed_event(
    *,
    event_id: str,
    project_id: str,
    artifact_id: str,
    actor_id: str,
    lineage: RepairLineage,
    obligation_ids: list[str] | None = None,
) -> UtilityEventV2:
    return UtilityEventV2(
        event_id=event_id,
        event_type=EventTypeV2.REPAIR_COMPLETED,
        project_id=project_id,
        artifact_id=artifact_id,
        obligation_ids=list(obligation_ids or []),
        actor_id=actor_id,
        payload=RepairCompletedPayload(
            repair_request_id=lineage.repair_request_ids[0],
            prior_candidate_id=lineage.prior_candidate_id,
            new_candidate_id=lineage.new_candidate_id,
            applied_change_hash=lineage.applied_change_hash,
            new_evidence_fingerprint=lineage.new_evidence_fingerprint,
        ),
    )
