from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION = "0.1.0"
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({SCHEMA_VERSION})


def parse_schema_version(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"schema_version must be semantic MAJOR.MINOR.PATCH, got {version!r}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def validate_supported_schema_version(version: str) -> str:
    parse_schema_version(version)
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_SCHEMA_VERSIONS))
        raise ValueError(f"unsupported schema_version {version!r}; supported: {supported}")
    return version


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class VersionedStrictModel(StrictModel):
    schema_version: str = SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def check_supported_schema_version(cls, value: str) -> str:
        return validate_supported_schema_version(value)


class ArtifactType(StrEnum):
    PROOF = "proof"
    THEOREM = "theorem"
    DEFINITION = "definition"
    INSTANCE = "instance"
    STRUCTURE = "structure"
    CLASS = "class"
    ABBREV = "abbrev"
    IMPORT = "import"
    REPOSITORY_PATCH = "repository_patch"


class ObligationStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RiskClass(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class EvidenceDimension(StrEnum):
    KERNEL = "kernel"
    SEMANTIC = "semantic"
    REPOSITORY = "repository"
    DOWNSTREAM = "downstream"
    PERSISTENCE = "persistence"
    UNCERTAINTY = "uncertainty"


class FindingStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Severity(StrEnum):
    INFO = "INFO"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class Recommendation(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class ReviewDecisionValue(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    REQUEST_REPAIR = "REQUEST_REPAIR"
    INDETERMINATE = "INDETERMINATE"


class EventType(StrEnum):
    OBLIGATION_REGISTERED = "OBLIGATION_REGISTERED"
    CANDIDATE_REGISTERED = "CANDIDATE_REGISTERED"
    EVIDENCE_COMPILED = "EVIDENCE_COMPILED"
    REVIEW_REQUESTED = "REVIEW_REQUESTED"
    REVIEW_SUBMITTED = "REVIEW_SUBMITTED"
    REPAIR_STARTED = "REPAIR_STARTED"
    REPAIR_COMPLETED = "REPAIR_COMPLETED"
    ARTIFACT_ACCEPTED = "ARTIFACT_ACCEPTED"
    ARTIFACT_REJECTED = "ARTIFACT_REJECTED"
    ARTIFACT_INTEGRATED = "ARTIFACT_INTEGRATED"
    DOWNSTREAM_ENABLED = "DOWNSTREAM_ENABLED"
    PERSISTENCE_CONFIRMED = "PERSISTENCE_CONFIRMED"
    REGRESSION_DETECTED = "REGRESSION_DETECTED"
    EXPERT_TIME_RECORDED = "EXPERT_TIME_RECORDED"
    CORRECTION_RECORDED = "CORRECTION_RECORDED"


class ExecutionPolicy(StrictModel):
    build_command: list[str] = Field(default_factory=lambda: ["lake", "build"])
    timeout_seconds: int = Field(default=1800, ge=1, le=86400)
    max_output_bytes: int = Field(default=2_000_000, ge=1024)
    # deny → Docker --network=none required; host subprocess refused (AUDIT-019).
    network_policy: str = Field(default="deny")
    # CI and secret-shaped names are denied even if listed (AUDIT-008).
    environment_allowlist: list[str] = Field(
        default_factory=lambda: ["PATH", "HOME", "USER", "TMPDIR"]
    )


class RepositoryConfig(StrictModel):
    remote: str
    default_branch: str = "main"
    public_api_paths: list[str] = Field(default_factory=list)
    protected_paths: list[str] = Field(default_factory=list)


class ProjectConfig(VersionedStrictModel):
    project_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    title: str
    repository: RepositoryConfig
    execution: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    allowed_axioms: list[str] = Field(default_factory=list)
    prohibited_tokens: list[str] = Field(default_factory=lambda: ["sorry", "admit"])


class TerminologyConcept(StrictModel):
    lean_names: list[str] = Field(min_length=1)
    prohibited_substitutions: list[str] = Field(default_factory=list)
    notes: str | None = None


class TerminologyFile(VersionedStrictModel):
    concepts: dict[str, TerminologyConcept] = Field(default_factory=dict)


class AcceptanceCondition(StrictModel):
    condition_id: str
    description: str
    required: bool = True


class Obligation(StrictModel):
    obligation_id: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{1,63}$")
    description: str
    artifact_type: ArtifactType
    weight: int = Field(ge=1, le=3)
    milestone: str
    status: ObligationStatus = ObligationStatus.PLANNED
    owner: str
    downstream: list[str] = Field(default_factory=list)
    acceptance_conditions: list[AcceptanceCondition] = Field(default_factory=list)


class ObligationsFile(VersionedStrictModel):
    obligations: list[Obligation] = Field(min_length=1)

    @staticmethod
    def _find_obligation_cycle(graph: dict[str, list[str]]) -> list[str] | None:
        visited: set[str] = set()

        def visit(node: str, visiting: set[str], path: list[str]) -> list[str] | None:
            if node in visiting:
                return path[path.index(node) :] + [node]
            if node in visited:
                return None
            visiting.add(node)
            path.append(node)
            for downstream_id in graph.get(node, []):
                cycle = visit(downstream_id, visiting, path)
                if cycle is not None:
                    return cycle
            path.pop()
            visiting.remove(node)
            visited.add(node)
            return None

        for obligation_id in graph:
            if obligation_id not in visited:
                cycle = visit(obligation_id, set(), [])
                if cycle is not None:
                    return cycle
        return None

    @model_validator(mode="after")
    def validate_graph(self) -> "ObligationsFile":
        ids = [o.obligation_id for o in self.obligations]
        if len(ids) != len(set(ids)):
            raise ValueError("obligation IDs must be unique")
        known = set(ids)
        graph = {
            obligation.obligation_id: list(obligation.downstream)
            for obligation in self.obligations
        }
        for obligation in self.obligations:
            unknown = set(obligation.downstream) - known
            if unknown:
                raise ValueError(
                    f"{obligation.obligation_id} references unknown downstream IDs: "
                    f"{sorted(unknown)}"
                )
            if obligation.obligation_id in obligation.downstream:
                raise ValueError(
                    f"{obligation.obligation_id} cannot depend downstream on itself"
                )
        cycle = self._find_obligation_cycle(graph)
        if cycle is not None:
            raise ValueError(
                "obligation downstream graph contains a cycle: " + " -> ".join(cycle)
            )
        return self


class RiskRule(StrictModel):
    require_human_acceptance: bool
    required_roles: list[str] = Field(default_factory=list)
    auto_accept_eligible: bool = False


class PoliciesFile(VersionedStrictModel):
    risk_rules: dict[RiskClass, RiskRule]
    changed_path_denylist: list[str] = Field(default_factory=list)
    external_provider_policy: str = "local_only"


class ReviewerAuthority(StrictModel):
    reviewer_id: str
    roles: list[str]
    scopes: list[str] = Field(default_factory=list)


class ReviewFile(VersionedStrictModel):
    authorities: list[ReviewerAuthority] = Field(default_factory=list)
    default_review_minutes: dict[RiskClass, int] = Field(default_factory=dict)


class ProjectContract(VersionedStrictModel):
    project: ProjectConfig
    intent_markdown: str
    terminology: TerminologyFile
    obligations: ObligationsFile
    policies: PoliciesFile
    review: ReviewFile
    contract_hash: str


class ChangedDeclaration(StrictModel):
    name: str
    kind: ArtifactType
    path: str
    signature_changed: bool = False
    public: bool = False
    foundational: bool = False


class GeneratorProvenance(StrictModel):
    generator_type: str
    name: str
    version: str | None = None
    model: str | None = None
    prompt_hash: str | None = None
    run_id: str | None = None


class CandidateDescriptor(VersionedStrictModel):
    candidate_id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,127}$")
    project_id: str
    obligation_ids: list[str] = Field(min_length=1)
    base_commit: str
    head_commit: str | None = None
    patch_path: str | None = None
    claimed_intent: str
    changed_paths: list[str] = Field(default_factory=list)
    changed_declarations: list[ChangedDeclaration] = Field(default_factory=list)
    patch_text: str | None = None
    generator: GeneratorProvenance

    @model_validator(mode="after")
    def validate_source(self) -> "CandidateDescriptor":
        if self.head_commit is None and self.patch_path is None and self.patch_text is None:
            raise ValueError("one of head_commit, patch_path, or patch_text is required")
        return self


class Provenance(StrictModel):
    tool: str
    tool_version: str
    command: list[str] = Field(default_factory=list)
    input_hash: str
    output_hash: str | None = None
    started_at: datetime
    finished_at: datetime
    elapsed_ms: int = Field(ge=0)
    deterministic: bool = True
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceFinding(StrictModel):
    finding_id: str
    check_id: str
    check_version: str
    dimension: EvidenceDimension
    status: FindingStatus
    severity: Severity
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance


class ReviewQuestion(StrictModel):
    question_id: str
    question: str
    decision_relevance: str
    answer_type: str
    required_roles: list[str]
    estimated_minutes: int = Field(ge=1, le=240)
    supporting_finding_ids: list[str] = Field(default_factory=list)


class EvidencePacket(VersionedStrictModel):
    packet_id: str
    run_id: str
    project_id: str
    contract_hash: str
    candidate: CandidateDescriptor
    risk_class: RiskClass
    findings: list[EvidenceFinding]
    hard_gate_passed: bool
    recommendation: Recommendation
    recommendation_reasons: list[str]
    unresolved_uncertainty: list[str] = Field(default_factory=list)
    review_question: ReviewQuestion | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewDecision(VersionedStrictModel):
    review_id: str
    packet_id: str
    reviewer_id: str
    reviewer_roles: list[str]
    decision: ReviewDecisionValue
    confidence: int = Field(ge=0, le=100)
    rationale: str
    answer: dict[str, Any] = Field(default_factory=dict)
    required_repair: str | None = None
    review_minutes: float = Field(gt=0)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UtilityEvent(VersionedStrictModel):
    event_id: str
    event_type: EventType
    project_id: str
    artifact_id: str
    obligation_id: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    supersedes_event_id: str | None = None

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value


class TPPRReport(VersionedStrictModel):
    project_id: str
    weighted_accepted_sustained_obligations: float
    specification_hours: float
    review_hours: float
    repair_hours: float
    integration_hours: float
    expert_hours_total: float
    tppr: float | None
    compute_cost_usd: float
    wall_clock_hours: float
    credited_obligations: list[str]
    pending_persistence_obligations: list[str]
    exclusions: list[str] = Field(default_factory=list)
