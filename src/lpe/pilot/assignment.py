"""Deterministic blocked condition assignment (CLOSURE-027).

Blocked 2:2:1 (40/40/20); stratify risk x artifact type; blocks of five;
HMAC-SHA256 shuffle; workload balance; author exclusion; repair blinding.
"""

from __future__ import annotations

import hashlib
import hmac
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from pydantic import Field, field_validator

from lpe.hashing import sha256_value
from lpe.models import StrictModel
from lpe.pilot.protocol import AssignmentConfig, ReviewerRoster, ReviewerRosterEntry

ConditionTag = Literal["control", "instrumented", "shadow"]

BLOCK_PATTERN: tuple[ConditionTag, ...] = (
    "control",
    "control",
    "instrumented",
    "instrumented",
    "shadow",
)


class AssignmentError(ValueError):
    """Raised when assignment cannot be produced under protocol constraints."""


class EpisodeSpec(StrictModel):
    candidate_id: str
    risk_class: str
    artifact_type: str
    author_id: str | None = None
    root_candidate_id: str | None = None
    is_repair: bool = False


class ReviewerAssignment(StrictModel):
    reviewer_id: str
    roles: list[str]


class ConditionAssignment(StrictModel):
    condition_assignment_id: str
    candidate_id: str
    condition_tag: ConditionTag
    stratum_id: str
    block_id: str
    block_index: int
    reviewers: list[ReviewerAssignment] = Field(default_factory=list)
    assignment_hash: str


class AssignmentManifest(StrictModel):
    assignment_id: str
    protocol_id: str
    seed_key_id: str
    seed_disclosed: bool = False
    assignments: list[ConditionAssignment]
    quotas: dict[str, int]
    manifest_hash: str

    @field_validator("assignments")
    @classmethod
    def non_empty(cls, value: list[ConditionAssignment]) -> list[ConditionAssignment]:
        if not value:
            raise ValueError("assignments must be non-empty")
        return value


def _hmac_digest(seed: str, message: str) -> bytes:
    return hmac.new(
        seed.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()


def _stratum_id(risk_class: str, artifact_type: str) -> str:
    return f"{risk_class}::{artifact_type}"


def assign_conditions(
    *,
    protocol_id: str,
    config: AssignmentConfig,
    episodes: list[EpisodeSpec],
    roster: ReviewerRoster,
    seed_plaintext: str,
) -> AssignmentManifest:
    """Produce a deterministic blocked assignment from the frozen seed.

    ``seed_plaintext`` is the operational seed (encrypted at rest until data lock).
    """
    if not seed_plaintext.strip():
        raise AssignmentError("randomization seed must be non-empty")
    if config.randomization_seed_ciphertext.strip() == "":
        raise AssignmentError("assignment config missing seed ciphertext placeholder")

    eligible = [r for r in roster.reviewers if r.eligible]
    if len(eligible) < 2:
        raise AssignmentError("need at least two eligible reviewers")

    # Repair blinding: group repair episodes with root; assign after originals.
    originals = [e for e in episodes if not e.is_repair]
    repairs = [e for e in episodes if e.is_repair]

    by_stratum: dict[str, list[EpisodeSpec]] = defaultdict(list)
    for ep in originals:
        by_stratum[_stratum_id(ep.risk_class, ep.artifact_type)].append(ep)

    assignments: list[ConditionAssignment] = []
    workload: dict[str, int] = defaultdict(int)
    seen_candidates: set[str] = set()

    for stratum, items in sorted(by_stratum.items()):
        # Stable order then HMAC shuffle within stratum before blocking.
        ordered = sorted(items, key=lambda e: e.candidate_id)
        ordered.sort(
            key=lambda e: _hmac_digest(
                seed_plaintext,
                f"{protocol_id}|{stratum}|{e.candidate_id}",
            )
        )
        # Pad incomplete final block is not allowed for locked pilot quotas;
        # remaining <5 stay unassigned until filled (fail closed for freeze).
        block_no = 0
        for offset in range(0, len(ordered), 5):
            chunk = ordered[offset : offset + 5]
            if len(chunk) < 5:
                raise AssignmentError(
                    f"stratum {stratum} has {len(chunk)} leftover episodes "
                    "(need multiples of 5 for 2:2:1 blocks)"
                )
            # Deterministic permutation of the fixed 2:2:1 multiset via HMAC.
            keyed = sorted(
                enumerate(BLOCK_PATTERN),
                key=lambda pair: _hmac_digest(
                    seed_plaintext,
                    f"{protocol_id}|{stratum}|block{block_no}|slot{pair[0]}",
                ),
            )
            tags = [tag for _, tag in keyed]
            block_id = f"{stratum}|b{block_no}"
            for idx, (ep, tag) in enumerate(zip(chunk, tags, strict=True)):
                if ep.candidate_id in seen_candidates:
                    raise AssignmentError(f"duplicate candidate {ep.candidate_id}")
                seen_candidates.add(ep.candidate_id)
                reviewers = _pick_reviewers(
                    eligible=eligible,
                    episode=ep,
                    workload=workload,
                    config=config,
                )
                raw = {
                    "candidate_id": ep.candidate_id,
                    "condition_tag": tag,
                    "stratum_id": stratum,
                    "block_id": block_id,
                    "block_index": idx,
                    "reviewers": [r.model_dump() for r in reviewers],
                }
                assignment = ConditionAssignment(
                    condition_assignment_id=f"asg-{ep.candidate_id}",
                    candidate_id=ep.candidate_id,
                    condition_tag=tag,
                    stratum_id=stratum,
                    block_id=block_id,
                    block_index=idx,
                    reviewers=reviewers,
                    assignment_hash=sha256_value(raw),
                )
                assignments.append(assignment)
            block_no += 1

    # Repair episodes: different reviewers than those who saw the original when possible.
    original_reviewers: dict[str, set[str]] = {
        a.candidate_id: {r.reviewer_id for r in a.reviewers} for a in assignments
    }
    for ep in sorted(repairs, key=lambda e: e.candidate_id):
        root = ep.root_candidate_id or ep.candidate_id.rsplit(".r", 1)[0]
        prior = original_reviewers.get(root, set())
        # Inherit condition from root when present.
        root_asg = next((a for a in assignments if a.candidate_id == root), None)
        if root_asg is None:
            raise AssignmentError(f"repair {ep.candidate_id} missing root assignment")
        if config.repair_blinding:
            pool = [r for r in eligible if r.reviewer_id not in prior]
            if not pool:
                raise AssignmentError(f"no conflict-free reviewer for repair {ep.candidate_id}")
        else:
            pool = eligible
        reviewers = _pick_reviewers(
            eligible=pool,
            episode=ep,
            workload=workload,
            config=config,
        )
        raw = {
            "candidate_id": ep.candidate_id,
            "condition_tag": root_asg.condition_tag,
            "stratum_id": root_asg.stratum_id,
            "block_id": f"repair|{ep.candidate_id}",
            "block_index": 0,
            "reviewers": [r.model_dump() for r in reviewers],
        }
        assignments.append(
            ConditionAssignment(
                condition_assignment_id=f"asg-{ep.candidate_id}",
                candidate_id=ep.candidate_id,
                condition_tag=root_asg.condition_tag,
                stratum_id=root_asg.stratum_id,
                block_id=f"repair|{ep.candidate_id}",
                block_index=0,
                reviewers=reviewers,
                assignment_hash=sha256_value(raw),
            )
        )

    quotas = {
        "control": sum(1 for a in assignments if a.condition_tag == "control"),
        "instrumented": sum(1 for a in assignments if a.condition_tag == "instrumented"),
        "shadow": sum(1 for a in assignments if a.condition_tag == "shadow"),
        "total": len(assignments),
    }
    manifest = AssignmentManifest(
        assignment_id=config.assignment_id,
        protocol_id=protocol_id,
        seed_key_id=config.seed_key_id,
        seed_disclosed=False,
        assignments=assignments,
        quotas=quotas,
        manifest_hash="",  # filled below
    )
    manifest.manifest_hash = sha256_value(
        manifest.model_dump(mode="json", exclude={"manifest_hash"})
    )
    return manifest


def _pick_reviewers(
    *,
    eligible: list[ReviewerRosterEntry],
    episode: EpisodeSpec,
    workload: dict[str, int],
    config: AssignmentConfig,
) -> list[ReviewerAssignment]:
    pool = list(eligible)
    if config.author_exclusion and episode.author_id:
        pool = [r for r in pool if r.reviewer_id != episode.author_id]
    if not pool:
        raise AssignmentError(f"no eligible reviewer for candidate {episode.candidate_id}")
    if config.workload_balance:
        pool.sort(key=lambda r: (workload[r.reviewer_id], r.reviewer_id))
    else:
        pool.sort(key=lambda r: r.reviewer_id)
    chosen = pool[0]
    workload[chosen.reviewer_id] += 1
    return [ReviewerAssignment(reviewer_id=chosen.reviewer_id, roles=list(chosen.roles))]


def verify_assignment_with_seed(
    manifest: AssignmentManifest,
    *,
    config: AssignmentConfig,
    episodes: list[EpisodeSpec],
    roster: ReviewerRoster,
    seed_plaintext: str,
) -> bool:
    """Recompute assignment from disclosed seed; return True if identical."""
    recomputed = assign_conditions(
        protocol_id=manifest.protocol_id,
        config=config,
        episodes=episodes,
        roster=roster,
        seed_plaintext=seed_plaintext,
    )
    return recomputed.manifest_hash == manifest.manifest_hash


@dataclass
class EncryptedSeed:
    """Opaque seed ciphertext handle (encryption is operator-supplied)."""

    ciphertext: str
    key_id: str
    disclosed: bool = False
    plaintext: str | None = field(default=None, repr=False)

    def disclose(self, plaintext: str) -> None:
        self.plaintext = plaintext
        self.disclosed = True
