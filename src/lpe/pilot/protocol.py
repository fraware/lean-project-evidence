"""Machine-readable pilot protocol bundle (CLOSURE-026).

Freeze refuses blanks; hashes all components; post-freeze change = new version.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, field_validator, model_validator

from lpe.hashing import sha256_file, sha256_text, sha256_value
from lpe.models import StrictModel

PROTOCOL_SCHEMA_VERSION = "0.3.0"
REQUIRED_BUNDLE_FILES: tuple[str, ...] = (
    "protocol.yaml",
    "endpoints.yaml",
    "assignment.yaml",
    "reviewer-roster.yaml",
    "held-out-set.json",
    "comprehension.yaml",
    "analysis.yaml",
    "signatures.json",
)


class ProtocolError(ValueError):
    """Raised when a protocol bundle is incomplete or inconsistent."""


class ConditionDesign(StrictModel):
    control_pct: int = Field(default=40, ge=0, le=100)
    instrumented_pct: int = Field(default=40, ge=0, le=100)
    shadow_pct: int = Field(default=20, ge=0, le=100)
    block_size: int = Field(default=5, ge=5, le=5)

    @model_validator(mode="after")
    def sums_to_100(self) -> ConditionDesign:
        total = self.control_pct + self.instrumented_pct + self.shadow_pct
        if total != 100:
            raise ValueError(f"condition percentages must sum to 100, got {total}")
        if self.block_size != 5:
            raise ValueError("blocked 2:2:1 design requires block_size=5")
        return self


class EndpointPlan(StrictModel):
    primary_operational: str
    primary_safety: str
    primary_north_star: str
    secondary: list[str] = Field(default_factory=list)


class ExclusionRule(StrictModel):
    rule_id: str
    description: str


class StoppingRule(StrictModel):
    rule_id: str
    description: str


class PilotProtocol(StrictModel):
    schema_version: Literal["0.3.0"] = "0.3.0"
    protocol_id: str
    project_id: str
    repository_remote: str
    repository_commit_at_freeze: str
    contract_freeze_id: str
    sample_size_min: int = Field(ge=30, le=50)
    sample_size_max: int = Field(ge=30, le=50)
    recruitment_window_start: date
    recruitment_window_end: date
    persistence_followup_days: int = Field(ge=1)
    condition_design: ConditionDesign
    endpoints: EndpointPlan
    exclusion_rules: list[ExclusionRule] = Field(min_length=1)
    stopping_rules: list[StoppingRule] = Field(min_length=1)
    held_out_set_hash: str
    analysis_plan_hash: str
    reviewer_roster_hash: str

    @model_validator(mode="after")
    def sample_bounds(self) -> PilotProtocol:
        if self.sample_size_min > self.sample_size_max:
            raise ValueError("sample_size_min must be <= sample_size_max")
        if self.recruitment_window_end < self.recruitment_window_start:
            raise ValueError("recruitment_window_end before start")
        for field_name in (
            "protocol_id",
            "project_id",
            "repository_remote",
            "repository_commit_at_freeze",
            "contract_freeze_id",
            "held_out_set_hash",
            "analysis_plan_hash",
            "reviewer_roster_hash",
        ):
            value = getattr(self, field_name)
            if not str(value).strip() or str(value).strip().lower() in {
                "todo",
                "tbd",
                "blank",
                "changeme",
            }:
                raise ValueError(f"{field_name} must not be blank/placeholder")
        return self


class ReviewerRosterEntry(StrictModel):
    reviewer_id: str
    roles: list[str] = Field(min_length=1)
    eligible: bool = True
    conflict_declaration_hash: str | None = None


class ReviewerRoster(StrictModel):
    roster_id: str
    reviewers: list[ReviewerRosterEntry] = Field(min_length=2)


class AssignmentConfig(StrictModel):
    assignment_id: str
    randomization_seed_ciphertext: str
    seed_key_id: str
    strata: list[str] = Field(default_factory=lambda: ["risk_class", "artifact_type"])
    workload_balance: bool = True
    author_exclusion: bool = True
    repair_blinding: bool = True


class ComprehensionConfig(StrictModel):
    config_id: str
    calibration_case_ids: list[str] = Field(min_length=5, max_length=5)
    pass_threshold_material: int = Field(default=4, ge=1, le=5)
    pass_threshold_basis: int = Field(default=4, ge=1, le=5)
    max_attempts: int = Field(default=2, ge=1, le=2)


class AnalysisPlan(StrictModel):
    plan_id: str
    primary_endpoints: list[str] = Field(min_length=1)
    secondary_endpoints: list[str] = Field(default_factory=list)
    agreement_methods: list[str] = Field(
        default_factory=lambda: ["cohen_kappa", "fleiss_kappa", "gwet_ac1"]
    )
    bootstrap_iterations: int = Field(default=2000, ge=100)
    analysis_image_digest: str | None = None


class ProtocolSignatures(StrictModel):
    research_lead: str
    domain_lead: str
    repository_maintainer: str
    signed_at: datetime

    @field_validator("signed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("signed_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def no_blank_signers(self) -> ProtocolSignatures:
        for name in ("research_lead", "domain_lead", "repository_maintainer"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} signature required")
        return self


class ProtocolBundle(StrictModel):
    """Validated in-memory protocol bundle with component hashes."""

    root: Path
    protocol: PilotProtocol
    endpoints: EndpointPlan
    assignment: AssignmentConfig
    roster: ReviewerRoster
    held_out_set: dict[str, Any]
    comprehension: ComprehensionConfig
    analysis: AnalysisPlan
    signatures: ProtocolSignatures
    component_hashes: dict[str, str]
    protocol_hash: str
    frozen: bool = False
    freeze_id: str | None = None


def _load_yaml(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ProtocolError(f"{path.name} is empty")
    data = yaml.safe_load(text)
    if data is None:
        raise ProtocolError(f"{path.name} is empty")
    return data


def _load_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ProtocolError(f"{path.name} is empty")
    return json.loads(text)


def validate_bundle_dir(root: Path) -> ProtocolBundle:
    """Load and validate every required file; refuse blanks."""
    root = root.resolve()
    if not root.is_dir():
        raise ProtocolError(f"protocol root not a directory: {root}")
    missing = [name for name in REQUIRED_BUNDLE_FILES if not (root / name).is_file()]
    if missing:
        raise ProtocolError(f"missing protocol files: {missing}")

    endpoints_raw = _load_yaml(root / "endpoints.yaml")
    endpoints = EndpointPlan.model_validate(endpoints_raw)

    assignment = AssignmentConfig.model_validate(_load_yaml(root / "assignment.yaml"))
    roster = ReviewerRoster.model_validate(_load_yaml(root / "reviewer-roster.yaml"))
    held_out = _load_json(root / "held-out-set.json")
    if not isinstance(held_out, dict) or not held_out:
        raise ProtocolError("held-out-set.json must be a non-empty object")
    comprehension = ComprehensionConfig.model_validate(_load_yaml(root / "comprehension.yaml"))
    analysis = AnalysisPlan.model_validate(_load_yaml(root / "analysis.yaml"))
    signatures = ProtocolSignatures.model_validate(_load_json(root / "signatures.json"))

    component_hashes = {name: sha256_file(root / name) for name in REQUIRED_BUNDLE_FILES}
    # Cross-link hashes expected inside protocol.yaml
    protocol_raw = _load_yaml(root / "protocol.yaml")
    if not isinstance(protocol_raw, dict):
        raise ProtocolError("protocol.yaml must be a mapping")
    expected = {
        "held_out_set_hash": component_hashes["held-out-set.json"],
        "analysis_plan_hash": component_hashes["analysis.yaml"],
        "reviewer_roster_hash": component_hashes["reviewer-roster.yaml"],
    }
    for key, digest in expected.items():
        if protocol_raw.get(key) != digest:
            raise ProtocolError(
                f"protocol.yaml {key} mismatch: expected {digest}, got {protocol_raw.get(key)!r}"
            )
    try:
        protocol = PilotProtocol.model_validate(protocol_raw)
    except Exception as exc:
        raise ProtocolError(f"protocol.yaml invalid: {exc}") from exc
    # Endpoints in protocol must match endpoints.yaml content hash identity
    if protocol.endpoints.model_dump() != endpoints.model_dump():
        raise ProtocolError("protocol.endpoints must match endpoints.yaml")

    protocol_hash = sha256_value(
        {
            "components": component_hashes,
            "protocol_id": protocol.protocol_id,
        }
    )
    return ProtocolBundle(
        root=root,
        protocol=protocol,
        endpoints=endpoints,
        assignment=assignment,
        roster=roster,
        held_out_set=held_out,
        comprehension=comprehension,
        analysis=analysis,
        signatures=signatures,
        component_hashes=component_hashes,
        protocol_hash=protocol_hash,
    )


def freeze_protocol(
    root: Path,
    *,
    freeze_id: str | None = None,
) -> ProtocolBundle:
    """Validate bundle and write ``freeze.json``; refuse incomplete bundles."""
    bundle = validate_bundle_dir(root)
    freeze_id = freeze_id or f"proto-freeze-{bundle.protocol.protocol_id}"
    freeze_doc = {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "freeze_id": freeze_id,
        "protocol_id": bundle.protocol.protocol_id,
        "protocol_hash": bundle.protocol_hash,
        "component_hashes": bundle.component_hashes,
        "frozen_at": datetime.now(UTC).isoformat(),
        "signatures": bundle.signatures.model_dump(mode="json"),
    }
    freeze_path = root / "freeze.json"
    if freeze_path.is_file():
        existing = json.loads(freeze_path.read_text(encoding="utf-8"))
        if existing.get("protocol_hash") != bundle.protocol_hash:
            raise ProtocolError(
                "protocol changed after prior freeze; create a new protocol version "
                f"(prior freeze_id={existing.get('freeze_id')})"
            )
        # Idempotent re-freeze of identical content.
        bundle.frozen = True
        bundle.freeze_id = str(existing["freeze_id"])
        return bundle

    freeze_path.write_text(
        json.dumps(freeze_doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    bundle.frozen = True
    bundle.freeze_id = freeze_id
    return bundle


def verify_freeze(root: Path) -> ProtocolBundle:
    """Re-validate and ensure freeze.json matches current component hashes."""
    bundle = validate_bundle_dir(root)
    freeze_path = root / "freeze.json"
    if not freeze_path.is_file():
        raise ProtocolError("freeze.json missing; run freeze first")
    freeze_doc = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze_doc.get("protocol_hash") != bundle.protocol_hash:
        raise ProtocolError(
            "frozen protocol_hash does not match current bundle; "
            "post-freeze changes require a new protocol version"
        )
    bundle.frozen = True
    bundle.freeze_id = str(freeze_doc.get("freeze_id"))
    return bundle


def write_example_bundle(root: Path, *, project_id: str = "example-partner") -> Path:
    """Write a complete non-blank example bundle for tests / operator templates.

    Values are synthetic placeholders suitable for unit tests, not a live partner.
    """
    root.mkdir(parents=True, exist_ok=True)
    held_out = {"held_out_ids": ["cal-01", "cal-02", "cal-03"], "note": "synthetic"}
    (root / "held-out-set.json").write_text(json.dumps(held_out, indent=2) + "\n", encoding="utf-8")
    held_hash = sha256_file(root / "held-out-set.json")

    analysis_yaml = {
        "plan_id": "analysis.example.v1",
        "primary_endpoints": [
            "weighted_accepted_obligations_per_review_repair_hour",
            "l2_l3_defect_sensitivity",
            "tppr_v2_by_condition",
        ],
        "secondary_endpoints": ["median_review_minutes", "agreement"],
        "agreement_methods": ["cohen_kappa", "fleiss_kappa", "gwet_ac1"],
        "bootstrap_iterations": 2000,
        "analysis_image_digest": "sha256:" + ("a" * 64),
    }
    (root / "analysis.yaml").write_text(
        yaml.safe_dump(analysis_yaml, sort_keys=False), encoding="utf-8"
    )
    analysis_hash = sha256_file(root / "analysis.yaml")

    roster = {
        "roster_id": "roster.example.v1",
        "reviewers": [
            {
                "reviewer_id": "domain-alice",
                "roles": ["domain-lead"],
                "eligible": True,
                "conflict_declaration_hash": "c" * 64,
            },
            {
                "reviewer_id": "maint-bob",
                "roles": ["repository-maintainer"],
                "eligible": True,
                "conflict_declaration_hash": "d" * 64,
            },
        ],
    }
    (root / "reviewer-roster.yaml").write_text(
        yaml.safe_dump(roster, sort_keys=False), encoding="utf-8"
    )
    roster_hash = sha256_file(root / "reviewer-roster.yaml")

    endpoints = {
        "primary_operational": "weighted_accepted_with_quorum / (H_review + H_repair)",
        "primary_safety": "proportion_adjudicated_L2_L3_before_integration",
        "primary_north_star": "tppr_v2_by_condition",
        "secondary": ["median_review_minutes", "automation_rate"],
    }
    (root / "endpoints.yaml").write_text(
        yaml.safe_dump(endpoints, sort_keys=False), encoding="utf-8"
    )

    assignment = {
        "assignment_id": "assign.example.v1",
        "randomization_seed_ciphertext": "enc:" + ("e" * 64),
        "seed_key_id": "pilot-seed-key-1",
        "strata": ["risk_class", "artifact_type"],
        "workload_balance": True,
        "author_exclusion": True,
        "repair_blinding": True,
    }
    (root / "assignment.yaml").write_text(
        yaml.safe_dump(assignment, sort_keys=False), encoding="utf-8"
    )

    comprehension = {
        "config_id": "comprehension.example.v1",
        "calibration_case_ids": [
            "ext-cal-01",
            "ext-cal-02",
            "ext-cal-03",
            "ext-cal-04",
            "ext-cal-05",
        ],
        "pass_threshold_material": 4,
        "pass_threshold_basis": 4,
        "max_attempts": 2,
    }
    (root / "comprehension.yaml").write_text(
        yaml.safe_dump(comprehension, sort_keys=False), encoding="utf-8"
    )

    protocol = {
        "schema_version": "0.3.0",
        "protocol_id": f"proto.{project_id}.v1",
        "project_id": project_id,
        "repository_remote": "https://github.com/example/partner-lean.git",
        "repository_commit_at_freeze": "b" * 40,
        "contract_freeze_id": "contract-freeze-example-1",
        "sample_size_min": 30,
        "sample_size_max": 50,
        "recruitment_window_start": "2026-08-01",
        "recruitment_window_end": "2026-10-31",
        "persistence_followup_days": 30,
        "condition_design": {
            "control_pct": 40,
            "instrumented_pct": 40,
            "shadow_pct": 20,
            "block_size": 5,
        },
        "endpoints": endpoints,
        "exclusion_rules": [
            {"rule_id": "ex-author", "description": "Author cannot review own candidate"}
        ],
        "stopping_rules": [
            {
                "rule_id": "stop-safety",
                "description": "Stop instrumented arm on additional integrated L3",
            }
        ],
        "held_out_set_hash": held_hash,
        "analysis_plan_hash": analysis_hash,
        "reviewer_roster_hash": roster_hash,
    }
    (root / "protocol.yaml").write_text(yaml.safe_dump(protocol, sort_keys=False), encoding="utf-8")

    signatures = {
        "research_lead": "research-lead@example.org",
        "domain_lead": "domain-lead@example.org",
        "repository_maintainer": "maintainer@example.org",
        "signed_at": datetime.now(UTC).isoformat(),
    }
    (root / "signatures.json").write_text(json.dumps(signatures, indent=2) + "\n", encoding="utf-8")
    return root


def hash_seed_plaintext(seed: str) -> str:
    """Hash a disclosed seed for post-lock verification."""
    return sha256_text(seed)
