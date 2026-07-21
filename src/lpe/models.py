from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def _coerce_finding_payload(value: Any) -> Any:
    from lpe.evidence.payloads import parse_finding_payload

    return parse_finding_payload(value)


SCHEMA_VERSION = "0.2.0"
# 0.1.0 remains readable (contracts, golden packets); writers emit SCHEMA_VERSION.
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"0.1.0", "0.2.0"})
LEGACY_SCHEMA_VERSION = "0.1.0"


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


class EvidenceBasis(StrEnum):
    """Discrete evidence production basis (CLOSURE-010 / spec §10)."""

    KERNEL_CHECKED = "KERNEL_CHECKED"
    ELABORATOR_EXTRACTED = "ELABORATOR_EXTRACTED"
    EXECUTED_TEST = "EXECUTED_TEST"
    STRUCTURAL_COMPARISON = "STRUCTURAL_COMPARISON"
    HEURISTIC_RETRIEVAL = "HEURISTIC_RETRIEVAL"
    HUMAN_ATTESTED = "HUMAN_ATTESTED"
    EXTERNAL_ASSERTION = "EXTERNAL_ASSERTION"


# Higher value = stronger basis. PASS with weaker basis cannot satisfy a stronger required basis.
BASIS_STRENGTH: dict[EvidenceBasis, int] = {
    EvidenceBasis.HEURISTIC_RETRIEVAL: 10,
    EvidenceBasis.EXTERNAL_ASSERTION: 20,
    EvidenceBasis.STRUCTURAL_COMPARISON: 30,
    EvidenceBasis.EXECUTED_TEST: 40,
    EvidenceBasis.ELABORATOR_EXTRACTED: 50,
    EvidenceBasis.KERNEL_CHECKED: 60,
    EvidenceBasis.HUMAN_ATTESTED: 70,
}


def basis_satisfies(actual: EvidenceBasis, required: EvidenceBasis) -> bool:
    """Return True when ``actual`` is at least as strong as ``required``."""
    return BASIS_STRENGTH[actual] >= BASIS_STRENGTH[required]


class EvidenceCoverage(StrictModel):
    """Declared-scope coverage for a finding (CLOSURE-010)."""

    requested_subject_count: int = Field(default=0, ge=0)
    evaluated_subject_count: int = Field(default=0, ge=0)
    excluded_subject_count: int = Field(default=0, ge=0)
    exclusion_reasons: list[str] = Field(default_factory=list)
    complete_for_declared_scope: bool = False
    # Explicit opt-in: incomplete coverage may PASS only when this is True.
    allows_partial_pass: bool = False


class SubjectReference(StrictModel):
    kind: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    ref: str = Field(min_length=1, max_length=1024)


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
                return [*path[path.index(node) :], node]
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
    def validate_graph(self) -> ObligationsFile:
        ids = [o.obligation_id for o in self.obligations]
        if len(ids) != len(set(ids)):
            raise ValueError("obligation IDs must be unique")
        known = set(ids)
        graph = {
            obligation.obligation_id: list(obligation.downstream) for obligation in self.obligations
        }
        for obligation in self.obligations:
            unknown = set(obligation.downstream) - known
            if unknown:
                raise ValueError(
                    f"{obligation.obligation_id} references unknown downstream IDs: "
                    f"{sorted(unknown)}"
                )
            if obligation.obligation_id in obligation.downstream:
                raise ValueError(f"{obligation.obligation_id} cannot depend downstream on itself")
        cycle = self._find_obligation_cycle(graph)
        if cycle is not None:
            raise ValueError("obligation downstream graph contains a cycle: " + " -> ".join(cycle))
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
    def validate_source(self) -> CandidateDescriptor:
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
    # ProvenanceV2 enrichment (CLOSURE-010); optional for 0.1.0 compatibility.
    producer_id: str | None = None
    producer_version: str | None = None
    run_manifest_hash: str | None = None
    environment_keys_forwarded: list[str] = Field(default_factory=list)
    image_digest: str | None = None
    toolchain_hash: str | None = None
    input_artifact_hashes: list[str] = Field(default_factory=list)
    output_artifact_hashes: list[str] = Field(default_factory=list)
    random_seed: str | None = None


class EvidenceFinding(StrictModel):
    """Evidence finding with additive 0.2.0 basis/coverage fields (CLOSURE-010)."""

    finding_id: str
    check_id: str
    check_version: str
    dimension: EvidenceDimension
    status: FindingStatus
    severity: Severity
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance
    basis: EvidenceBasis | None = None
    coverage: EvidenceCoverage | None = None
    subject_refs: list[SubjectReference] = Field(default_factory=list)
    # Typed FindingPayload union (spec §10.1) or legacy bare dict without discriminator.
    payload: Annotated[
        Any | None,
        BeforeValidator(_coerce_finding_payload),
    ] = None
    artifact_refs: list[str] = Field(default_factory=list)
    required_basis: EvidenceBasis | None = None
    # Spec §10.1 EvidenceFindingV2 — optional so historical packets still load.
    snapshot_fingerprint: str | None = None

    @model_validator(mode="after")
    def enforce_basis_and_coverage_rules(self) -> EvidenceFinding:
        if self.status is FindingStatus.PASS:
            if (
                self.coverage is not None
                and not self.coverage.complete_for_declared_scope
                and not self.coverage.allows_partial_pass
            ):
                raise ValueError(
                    f"incomplete coverage cannot silent-PASS (check_id={self.check_id!r})"
                )
            if (
                self.basis is not None
                and self.required_basis is not None
                and not basis_satisfies(self.basis, self.required_basis)
            ):
                raise ValueError(
                    f"PASS with basis {self.basis.value} cannot satisfy required "
                    f"basis {self.required_basis.value} (check_id={self.check_id!r})"
                )
        return self


class ReviewQuestion(StrictModel):
    question_id: str
    question: str
    decision_relevance: str
    answer_type: str
    required_roles: list[str]
    estimated_minutes: int = Field(ge=1, le=240)
    supporting_finding_ids: list[str] = Field(default_factory=list)
    # Explicit M6 comparison id (deterministic scaffold; no learning until §21).
    baseline_id: str = "deterministic_baseline.v1"


class UncertaintyRecord(StrictModel):
    """Typed unresolved uncertainty entry (spec §10.4 EvidencePacketV2)."""

    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4096)
    check_id: str | None = None
    dimension: EvidenceDimension | None = None


class HardGateResult(StrictModel):
    """Structured hard-gate outcome (spec §10.4); mirrors GateDecision fields."""

    passed: bool
    hard_failures: list[str] = Field(default_factory=list)
    unresolved_hard_checks: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


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
    # Stable content hash of contract+candidate+compiler (cross-link for ledger /
    # seal tip provenance). Optional so historical 0.1.0 packets still load.
    evidence_fingerprint: str | None = None
    # Optional ledger seal / chain tip recorded when the packet is linked to a
    # ledger snapshot (warehouse / review record). Not present at compile time.
    ledger_seal_tip: str | None = None
    # 0.2.0: synthesis/gates policy id joins recommendation policy (CLOSURE-015).
    recommendation_policy_id: str | None = None
    # EvidencePacketV2 additive fields (CLOSURE-010/011). ``run_manifest`` is a
    # canonical dump of workspace.RunManifest to avoid import cycles; readers
    # may re-validate via ``lpe.workspace.models.RunManifest``.
    run_manifest: dict[str, Any] | None = None
    coverage_summary: dict[str, EvidenceCoverage] = Field(default_factory=dict)
    hard_gate: HardGateResult | None = None
    uncertainty_records: list[UncertaintyRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FixtureEntry(StrictModel):
    """One executable or structural fixture in a suite manifest (CLOSURE-013)."""

    fixture_id: str
    path: str
    expected_exit: int = 0
    expected_diagnostics: list[str] = Field(default_factory=list)
    expected_diagnostic_regex: str | None = None
    basis: EvidenceBasis = EvidenceBasis.EXECUTED_TEST
    run_on: str = Field(default="candidate", pattern=r"^(base|candidate|both)$")
    timeout_seconds: int = Field(default=120, ge=1, le=86400)
    obligation_ids: list[str] = Field(default_factory=list)
    semantic_interpretation: str | None = None
    command_kind: str = "lake_env_lean"


class FixtureSuite(VersionedStrictModel):
    """YAML suite for examples / counterexamples (schema fixture-suite)."""

    suite_id: str
    obligation_ids: list[str] = Field(min_length=1)
    fixtures: list[FixtureEntry] = Field(min_length=1)
    suite_kind: str = Field(default="examples", pattern=r"^(examples|counterexamples)$")


class SuccessorEntry(StrictModel):
    """One downstream successor test (CLOSURE-014 / §11.6)."""

    successor_id: str
    command: list[str] = Field(min_length=1)
    module: str | None = None
    declarations: list[str] = Field(default_factory=list)
    required: bool = True
    path: str | None = None
    timeout_seconds: int = Field(default=300, ge=1, le=86400)


class SuccessorSuite(VersionedStrictModel):
    """Successor suite manifest for paired base/candidate runs."""

    suite_id: str
    obligation_ids: list[str] = Field(min_length=1)
    successors: list[SuccessorEntry] = Field(min_length=1)


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
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UtilityEvent(VersionedStrictModel):
    event_id: str
    event_type: EventType
    project_id: str
    artifact_id: str
    obligation_id: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
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
