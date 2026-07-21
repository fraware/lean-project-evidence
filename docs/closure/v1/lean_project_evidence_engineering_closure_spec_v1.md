# Lean Project Evidence
# Engineering Closure Specification

**Specification version:** 1.0  
**Repository:** `fraware/lean-project-evidence`  
**Audited commit:** `412b380dacd6b33300ee1c007e0ec8aa2ab5fb1a`  
**Target release train:** `0.2.0` evidence integrity, `0.3.0` pilot readiness, `0.4.0` pilot completion  
**Governing North Star:** critical-path trusted Lean project progress per expert hour

---

## 1. Purpose

This document is the complete implementation contract for closing the remaining engineering and research-operational work in Lean Project Evidence.

The repository already contains a credible fixture-scoped implementation of project contracts, deterministic evidence compilation, sandboxed execution, Lean extraction, semantic checks, human review recording, a hash-chained utility ledger, TPPR computation, pilot instrumentation, anti-oversell controls, and extensive tests. The remaining work is concentrated in five boundaries:

1. every check for a candidate must evaluate the same immutable candidate snapshot;
2. the Lean extractor must work generically on arbitrary supported Lake projects;
3. evidence, review, acceptance, persistence, and TPPR must use typed state transitions;
4. R3 and R4 human acceptance must support independent semantic and repository attestations;
5. the partner pilot and ENGINEERING_SPEC §21 gates must become machine-enforced, reproducible research operations.

The implementation must preserve the product thesis:

> Lean Project Evidence is an evidence and control layer around existing provers and repositories. It does not replace the Lean kernel, mathematical experts, repository maintainers, or project governance.

The implementation must preserve the North Star:

\[
\operatorname{TPPR}
=
\frac{
\sum_i w_i F_i A_i S_i
}{
H_{\mathrm{spec}}+
H_{\mathrm{review}}+
H_{\mathrm{repair}}+
H_{\mathrm{integration}}
}.
\]

No feature is complete merely because it increases generated artifacts, compilation rate, benchmark throughput, test count, or model accuracy.

---

## 2. Current repository assessment

### 2.1 Current strengths

The audited repository has the following working foundations.

- Project contracts, obligation graphs, strict Pydantic models, schema validation, and contract migration are implemented.
- Evidence compilation fails closed on hard-check uncertainty.
- Git enrichment overrides self-declared candidate metadata.
- Docker execution uses network denial, capability dropping, no-new-privileges, memory limits, PID limits, and a scrubbed environment.
- Lean extraction distinguishes a toolchain-backed result from a regex fallback.
- Axiom checks never infer closure from an empty regex result.
- Impact-cone and import-edge semantics are documented.
- Semantic providers explicitly distinguish structural evidence from mathematical intent.
- Review authority comes from `review.yaml`, not the reviewer's self-declared roles.
- The utility ledger is append-only at the application/database layer, hash chained, exportable, verifiable, archivable, and externally sealable.
- Evidence packets carry an evidence fingerprint.
- Review questions carry `baseline_id=deterministic_baseline.v1`.
- Pilot instrumentation records conditions, expert time, wall-clock overhead, and descriptive TPPR.
- CLI and documentation contain explicit non-claims.
- The repository reports 583 non-slow tests at the audited commit.

### 2.2 Current release boundary

The current implementation is appropriately described as:

> Engineering fixture excellence with pilot instrumentation, not production semantic assurance and not a completed human study.

The current repository must not claim:

- causal TPPR improvement;
- Mathlib-scale elaborator completeness;
- production R3/R4 acceptance;
- a WORM ledger or external root of trust;
- learned routing;
- project-targeted synthesis;
- scientific clearance under ENGINEERING_SPEC §21.

### 2.3 Critical correctness defect

The current evidence compiler can build and extract inside an isolated candidate worktree, clean that worktree, and subsequently invoke semantic providers with the original `project_path`.

This permits one evidence packet to combine:

- build evidence from the candidate head;
- extraction evidence persisted from the candidate worktree;
- semantic fixture execution against the operator's original checkout;
- repository retrieval against a different filesystem state.

This violates the core invariant that all findings in a packet concern one candidate snapshot.

The first closure release must make this state impossible by construction.

### 2.4 Critical execution-policy defect

The current example and counterexample providers invoke host `lake env lean` directly when Lake is available.

This bypasses:

- the selected executor;
- the Docker network policy;
- the environment allowlist;
- worktree isolation;
- per-provider resource limits;
- execution provenance.

Every executable provider must use the same candidate workspace and executor selected by the evidence compiler.

### 2.5 Critical product-governance defect

The initial product wedge is statement, definition, and public API review, which naturally produces R3 and R4 candidates. The current CLI refuses to record R3/R4 acceptance entirely.

A production-quality human-controlled protocol must distinguish:

- automatic acceptance, which remains forbidden for R3/R4;
- qualified human acceptance, which must become possible through a multi-attestation quorum.

### 2.6 Critical metric-integrity defect

Current TPPR computation aggregates untyped event payloads by obligation ID. It does not enforce a lifecycle state machine, immutable obligation registration, one-time credit, persistence windows, correction application, or condition-specific reporting.

The metric must become an auditable derived view over typed lifecycle events.

---

## 3. Release train

### 3.1 Release `0.2.0` — Evidence Integrity

Release `0.2.0` closes all candidate-consistency, provenance, extraction, execution, and schema-integrity defects.

It is complete only when:

- every finding is tied to one immutable base/head workspace pair;
- every executable provider runs through the selected executor;
- a generic extractor works without a target repository defining `lpe_extract`;
- base and head declaration snapshots can be compared;
- evidence packets include complete run configuration and image/toolchain provenance;
- schema `0.2.0` and migration from `0.1.0` are complete;
- CI validates the package, types, style, schemas, Docker integration, and generic Lean extraction.

`0.2.0` remains an engineering release. It does not pass §21.

### 3.2 Release `0.3.0` — Pilot Readiness

Release `0.3.0` closes review quorum, typed lifecycle, protocol freezing, randomization, blinding, field instrumentation, and §21 gate computation.

It is complete only when:

- R3/R4 human acceptance is supported through independent, role-scoped attestations;
- the ledger uses typed event payloads and validated state transitions;
- TPPR v2 produces an auditable numerator and denominator;
- the pilot protocol is machine-readable and cryptographically frozen;
- assignment is reproducible and balanced;
- reviewer conflicts and comprehension are recorded;
- the partner pilot can be run without manual editing of generated packets or blank templates;
- a §21 gate report can be computed from sealed evidence.

`0.3.0` authorizes pilot execution. It does not establish causal utility.

### 3.3 Release `0.4.0` — Pilot Completion

Release `0.4.0` contains the completed prospective pilot dataset, sealed protocol, sealed ledger export, analysis output, limitations, and gate decision.

It is complete only when:

- 30–50 prospective candidate-review episodes are complete;
- required condition quotas are met;
- field automation, reproduction, overhead, comprehension, and agreement are measured;
- persistence follow-up is complete for credited obligations;
- the §21 gate report is final;
- the report distinguishes descriptive, causal, and unsupported claims.

### 3.4 Release `1.0.0` — Production Evidence Service

Release `1.0.0` requires:

- successful prospective operation on at least three independent active Lean repositories;
- at least two mathematical domains;
- an external security review;
- an external methodology review;
- stable schema support and migration guarantees;
- measured reviewer-value improvement without a material safety regression;
- supported Lean compatibility matrix;
- documented operational ownership and incident response.

M6 learned routing and M7 synthesis do not block `1.0.0`. They are optional research capabilities gated by §21.

---

## 4. Non-negotiable invariants

### 4.1 Snapshot identity

Every packet must identify exactly one evaluated candidate snapshot.

The packet must contain:

- base commit SHA;
- head commit SHA or applied patch content hash;
- base tree hash;
- head tree hash;
- contract hash;
- obligation-freeze hash;
- toolchain file hash;
- Lake manifest hash;
- executor configuration hash;
- container image digest;
- provider-version map;
- compiler version;
- extraction protocol version.

A finding without a matching snapshot identity is invalid.

### 4.2 Workspace consistency

Build, extraction, examples, counterexamples, duplicate retrieval, downstream tests, and report rendering must consume the same `EvaluationWorkspace`.

Providers may consume read-only derived artifacts from that workspace. They may not reopen the operator's source checkout.

### 4.3 Evidence separability

The evidence vector remains:

- kernel;
- semantic;
- repository;
- downstream;
- persistence;
- uncertainty.

A universal scalar quality score remains prohibited.

### 4.4 Evidence basis

Every finding must declare one basis:

- `KERNEL_CHECKED`
- `ELABORATOR_EXTRACTED`
- `EXECUTED_TEST`
- `STRUCTURAL_COMPARISON`
- `HEURISTIC_RETRIEVAL`
- `HUMAN_ATTESTED`
- `EXTERNAL_ASSERTION`

A `PASS` with `STRUCTURAL_COMPARISON` cannot satisfy a contract condition requiring `HUMAN_ATTESTED`.

### 4.5 Human authority

R3 and R4 candidates can never be automatically accepted.

Human acceptance requires the quorum in Section 12.

### 4.6 Immutable project obligations

An obligation can contribute to TPPR only when it was frozen before candidate registration.

Weight, critical-path status, acceptance conditions, persistence rule, and milestone membership become immutable at freeze time.

### 4.7 Append-only lifecycle

Lifecycle facts are recorded as append-only events.

Corrections create new events. They never mutate history.

### 4.8 Fail-closed uncertainty

Missing, stale, contradictory, or incomplete evidence produces `UNKNOWN` or `FAIL` according to policy.

Absence never produces `PASS`.

### 4.9 External-provider disclosure

Any content sent outside the local execution boundary must be authorized by the project contract and recorded at field level.

### 4.10 Claim control

CLI output, reports, documentation, and releases must preserve the canonical non-claims until their corresponding gate is passed.

---

## 5. Target architecture

```text
Project Contract Freeze
          │
          ▼
Candidate Registration
          │
          ▼
EvaluationWorkspaceManager
  ├── BaseSnapshot
  ├── CandidateSnapshot
  ├── Executor
  ├── ArtifactStore
  └── RunManifest
          │
          ▼
Evidence Pipeline
  ├── Git/Lean declaration diff
  ├── Exact build
  ├── Generic Lean extraction
  ├── Kernel checks
  ├── Semantic fixtures
  ├── Repository checks
  └── Downstream replacement
          │
          ▼
Evidence Packet + Review Packet
          │
          ▼
Independent Attestations
          │
          ▼
Acceptance State Machine
          │
          ▼
Integration + Persistence
          │
          ▼
Typed Utility Ledger
          │
          ▼
TPPR v2 + §21 Gate Report
```

The implementation remains a modular monolith.

No microservice split is authorized during releases `0.2.0` or `0.3.0`.

---

## 6. Evaluation workspace specification

### 6.1 New module

Create:

```text
src/lpe/workspace/
├── __init__.py
├── manager.py
├── models.py
├── snapshots.py
└── artifacts.py
```

### 6.2 `EvaluationWorkspace`

Implement an immutable application-level object:

```python
@dataclass(frozen=True)
class EvaluationWorkspace:
    run_id: str
    repository_origin: Path
    base_path: Path
    candidate_path: Path
    base_commit: str
    head_commit: str | None
    patch_sha256: str | None
    base_tree_hash: str
    candidate_tree_hash: str
    contract_hash: str
    obligation_freeze_hash: str
    executor: LeanExecutor
    executor_descriptor: ExecutorDescriptor
    artifact_store: ArtifactStore
    cleanup_token: WorkspaceCleanupToken
```

The object must be created once and passed to every provider.

### 6.3 Workspace lifecycle

The lifecycle is exact:

1. validate contract and frozen obligations;
2. resolve canonical base and head;
3. create isolated base worktree;
4. create isolated candidate worktree;
5. apply the patch to the candidate worktree when the candidate is patch-based;
6. verify candidate tree cleanliness relative to its source;
7. calculate snapshot hashes;
8. select and validate the executor;
9. run base extraction when required;
10. run candidate build and extraction;
11. execute all providers;
12. persist content-addressed artifacts;
13. assemble and validate the packet;
14. append the evidence event when configured;
15. clean both worktrees;
16. verify cleanup.

Cleanup may occur only after the packet and all referenced artifacts are durably stored.

### 6.4 Patch-based candidates

Patch-based candidates must be applied with:

```bash
git apply --index --whitespace=error-all
```

The implementation must reject:

- an absolute patch path;
- parent traversal;
- binary patch content unless contract policy explicitly permits it;
- failed hunks;
- dirty files outside the patch;
- symlink escapes;
- submodule changes unless explicitly allowed.

The applied candidate tree must be committed to a temporary detached commit so that it has a stable tree hash and can be addressed like a commit candidate.

### 6.5 Workspace provenance

Create `RunManifest` with:

```python
class RunManifest(VersionedStrictModel):
    schema_version: Literal["0.2.0"]
    run_id: str
    project_id: str
    candidate_id: str
    base_commit: str
    candidate_commit: str
    base_tree_hash: str
    candidate_tree_hash: str
    patch_sha256: str | None
    contract_hash: str
    obligation_freeze_hash: str
    lean_toolchain_sha256: str
    lake_manifest_sha256: str | None
    compiler_version: str
    extraction_protocol_version: str
    provider_versions: dict[str, str]
    executor: ExecutorDescriptor
    created_at: datetime
```

The evidence fingerprint must hash the canonical `RunManifest` plus canonical findings.

### 6.6 Acceptance tests

The workspace implementation is complete when tests prove:

- a dirty operator checkout does not affect evidence;
- base and candidate worktrees remain available through the final provider;
- a semantic fixture created only at head is executed at head;
- a semantic fixture removed at head is not read from base;
- a failed provider still triggers cleanup;
- a process interruption leaves recoverable content-addressed artifacts;
- identical snapshot inputs produce identical workspace fingerprints;
- changed Docker image digest changes the workspace fingerprint.

---

## 7. Unified executor and provider contract

### 7.1 New provider context

Replace provider signatures that receive `project_path` with:

```python
@dataclass(frozen=True)
class ProviderContext:
    workspace: EvaluationWorkspace
    contract: FrozenProjectContract
    candidate: CandidateDescriptorV2
    base_extraction: LeanExtractionResultV2 | None
    candidate_extraction: LeanExtractionResultV2 | None
    cancellation: CancellationToken
    provider_deadline: datetime
```

Every provider implements:

```python
class EvidenceProvider(Protocol):
    provider_id: str
    provider_version: str
    required_basis: EvidenceBasis

    def collect(self, context: ProviderContext) -> ProviderResult:
        ...
```

### 7.2 `ProviderResult`

```python
class ProviderResult(VersionedStrictModel):
    schema_version: Literal["0.2.0"]
    provider_id: str
    provider_version: str
    snapshot_fingerprint: str
    findings: list[EvidenceFindingV2]
    artifact_refs: list[ArtifactReference]
    started_at: datetime
    finished_at: datetime
    status: Literal["COMPLETED", "TIMED_OUT", "FAILED", "CANCELLED"]
```

### 7.3 Execution rule

A provider that executes Lean must invoke:

```python
context.workspace.executor.run(
    workspace=context.workspace,
    command=ValidatedCommand(...),
    resource_profile=ProviderResourceProfile(...),
)
```

Direct `subprocess.run` calls from semantic providers are forbidden.

### 7.4 Timeouts and resource profiles

Define:

```python
class ProviderResourceProfile(StrictModel):
    timeout_seconds: int
    max_stdout_bytes: int
    max_stderr_bytes: int
    memory_bytes: int
    pids_limit: int
    cpu_quota: float
```

Default profiles:

| Provider | Timeout | Memory | CPU | Output |
|---|---:|---:|---:|---:|
| statement diff | 60 s | 512 MiB | 1 | 256 KiB |
| examples | 300 s | 2 GiB | 2 | 1 MiB |
| counterexamples | 300 s | 2 GiB | 2 | 1 MiB |
| duplicate retrieval | 120 s | 1 GiB | 2 | 512 KiB |
| downstream replacement | 900 s | 4 GiB | 4 | 2 MiB |

A timeout produces `UNKNOWN` with provenance. It cannot silently skip a required check.

### 7.5 Artifact store

Logs must not be embedded wholesale in the evidence packet.

Create a content-addressed artifact store:

```text
.lpe/artifacts/sha256/<first-two>/<digest>
```

Each artifact reference includes:

```python
class ArtifactReference(StrictModel):
    sha256: str
    media_type: str
    byte_length: int
    logical_name: str
    redaction_applied: bool
    producer_id: str
```

The packet may include a redacted excerpt capped at 4 KiB.

### 7.6 Acceptance tests

- no provider invokes host `lake` when Docker is selected;
- every provider result carries the candidate snapshot fingerprint;
- provider timeout produces `UNKNOWN`;
- log secrets are redacted before storage;
- artifact digest mismatch fails packet validation;
- a provider cannot open files outside its workspace root through framework APIs.

---

## 8. Sandbox hardening

### 8.1 Required Docker invocation

The candidate executor must add:

```text
--read-only
--user "$(id -u):$(id -g)"
--cap-drop=ALL
--security-opt=no-new-privileges
--network=none
--memory=<configured>
--memory-swap=<same-as-memory>
--cpus=<configured>
--pids-limit=<configured>
--ulimit fsize=<configured>
--tmpfs /tmp:rw,noexec,nosuid,nodev,size=<configured>
--tmpfs /home/lpe:rw,noexec,nosuid,nodev,size=<configured>
```

The repository source mount must be read-only.

Writable paths must be separate ephemeral mounts:

- `/worktree-output`
- `/lake-cache`
- `/tmp`
- `/home/lpe`

The evaluated candidate source is copied or overlaid into an ephemeral writable layer. The host checkout is never mounted read-write.

### 8.2 Image identity

Mutable image tags are insufficient for packet provenance.

The executor descriptor must record:

```python
class ExecutorDescriptor(StrictModel):
    backend: Literal["docker", "host"]
    image_reference: str | None
    image_digest: str | None
    network_policy: Literal["deny", "allow"]
    uid: int | None
    gid: int | None
    memory_bytes: int
    cpu_quota: float
    pids_limit: int
    readonly_root: bool
    source_mount_readonly: bool
```

A Docker run with no resolved image digest produces `UNKNOWN` provenance and cannot support automatic acceptance.

### 8.3 Lean image

Publish a reproducible image recipe, not only a local tag.

The image build must:

- install elan from a pinned release checksum;
- support project-local `lean-toolchain`;
- install no project dependencies at image build time;
- generate an SBOM;
- run as an unprivileged user;
- contain the generic extraction driver;
- be built and scanned in CI;
- be published by digest.

### 8.4 Remove duplicate definitions

`src/lpe/execution/sandbox.py` currently contains two definitions of `isolation_status_for_executor`.

Retain one tested implementation.

### 8.5 Host execution

Host execution remains an explicit insecure diagnostic mode.

It must:

- require `--insecure-host-exec`;
- require contract `network_policy=allow`;
- print and record a warning;
- produce `execution.isolation=UNKNOWN`;
- disable automatic acceptance;
- never be used in pilot control or instrumented conditions.

---

## 9. Generic Lean extraction

### 9.1 Objective

LPE must extract declarations and dependency evidence from an arbitrary supported Lake project without requiring that project to define or commit an `lpe_extract` executable.

### 9.2 New package layout

```text
lean/
├── LpeExtract/
│   ├── Main.lean
│   ├── Protocol.lean
│   ├── Environment.lean
│   ├── Modules.lean
│   └── Json.lean
├── lakefile.toml
└── lean-toolchain
```

The Python wheel must include versioned extractor sources.

### 9.3 Injection method

For each evaluated snapshot:

1. discover the target Lake workspace;
2. discover project libraries and source roots;
3. generate an import aggregator in the ephemeral workspace;
4. create an ephemeral Lake package that depends on the target package by local path;
5. compile the extractor with the target project's `lean-toolchain`;
6. run the extractor inside the selected sandbox;
7. emit a protocol-validated JSON artifact.

No permanent target-repository file is modified.

### 9.4 Module discovery

Module discovery must use Lake workspace metadata where available.

Fallback filesystem discovery may be used only when:

- the project has one unambiguous Lean source root;
- module paths can be mapped bijectively;
- generated/build/vendor directories are excluded.

Ambiguity produces `UNKNOWN` and an actionable error.

### 9.5 Base and candidate extraction

The extractor runs separately on base and candidate snapshots.

The output must include:

```python
class LeanExtractionResultV2(VersionedStrictModel):
    schema_version: Literal["2.0"]
    snapshot_fingerprint: str
    lean_version: str
    lake_version: str
    toolchain_spec: str
    imported_modules: list[ModuleRecord]
    declarations: list[DeclarationRecord]
    declaration_dependency_edges: list[DeclarationEdge]
    import_edges: list[ImportEdge]
    axioms_by_declaration: dict[str, list[str]]
    placeholders: list[PlaceholderRecord]
    errors: list[ExtractionError]
    completeness: ExtractionCompleteness
```

### 9.6 Declaration record

```python
class DeclarationRecord(StrictModel):
    fqn: str
    kind: Literal[
        "axiom", "theorem", "opaque", "definition", "inductive",
        "constructor", "recursor", "instance", "abbrev", "structure", "class"
    ]
    module: str
    source_path: str | None
    source_start_line: int | None
    source_start_column: int | None
    public_visibility: Literal["public", "protected", "private", "internal", "unknown"]
    type_pretty: str
    type_expr_hash: str
    value_expr_hash: str | None
    universe_params: list[str]
    attributes: list[str]
    axioms_used: list[str]
```

### 9.7 Completeness

```python
class ExtractionCompleteness(StrictModel):
    environment_loaded: bool
    all_project_modules_imported: bool
    declaration_types_complete: bool
    declaration_values_available_where_exposed: bool
    axiom_collection_complete_for_loaded_environment: bool
    source_positions_complete: bool
    known_limitations: list[str]
```

The extractor may set `complete=true` only for explicitly named dimensions. A single global boolean is insufficient.

### 9.8 Declaration diff

Create:

```text
src/lpe/lean/declaration_diff.py
```

It compares base and candidate extractions and emits:

- added declarations;
- removed declarations;
- renamed candidates;
- type changes;
- body-only changes;
- visibility changes;
- attribute changes;
- axiom-set changes;
- dependency-edge changes;
- import changes.

Risk classification must consume this diff.

The lexical Git classifier becomes a fallback used only when generic extraction fails. It cannot produce `R0` automatic acceptance.

### 9.9 Risk rules from declaration diff

- body-only proof change under identical theorem type and identical public surface: `R0`;
- private helper addition or body change: `R1`;
- public theorem addition with no changed existing type: `R2`;
- changed theorem type, public definition, instance, structure, class, abbreviation, or axiom set: `R3`;
- foundational declarations, toolchain/Lake changes, broad import architecture, removed public declaration, or large impact cone above contract threshold: `R4`.

### 9.10 Compatibility matrix

Release `0.2.0` must support:

- Lean 4.14.x;
- one current stable Lean release used by a selected real project;
- Mathlib-backed project with cache;
- non-Mathlib Lake project.

Unsupported versions must fail with `UNSUPPORTED_TOOLCHAIN`, not silently use regex evidence.

### 9.11 Scale validation

Before `0.2.0` release, generic extraction must be tested on:

- the existing fixture;
- one small independent public Lean project;
- one medium project with at least 500 declarations;
- one Mathlib-backed downstream project;
- a bounded Mathlib module set containing at least 10,000 declarations.

The project names and commit SHAs belong in a versioned compatibility manifest committed after selection. The schema and acceptance conditions are fixed here; no blank document fields are required.

---

## 10. Evidence model `0.2.0`

### 10.1 Finding schema

Replace untyped finding details with a typed envelope:

```python
class EvidenceFindingV2(VersionedStrictModel):
    schema_version: Literal["0.2.0"]
    finding_id: str
    check_id: str
    check_version: str
    snapshot_fingerprint: str
    dimension: EvidenceDimension
    status: FindingStatus
    severity: Severity
    basis: EvidenceBasis
    coverage: EvidenceCoverage
    subject_refs: list[SubjectReference]
    summary: str
    payload: FindingPayload
    artifact_refs: list[ArtifactReference]
    provenance: ProvenanceV2
```

### 10.2 Coverage

```python
class EvidenceCoverage(StrictModel):
    requested_subject_count: int
    evaluated_subject_count: int
    excluded_subject_count: int
    exclusion_reasons: list[str]
    complete_for_declared_scope: bool
```

A provider cannot emit `PASS` when `complete_for_declared_scope=false` unless the check explicitly defines partial pass semantics.

### 10.3 Provenance

```python
class ProvenanceV2(StrictModel):
    producer_id: str
    producer_version: str
    run_manifest_hash: str
    command_argv: list[str]
    environment_keys_forwarded: list[str]
    image_digest: str | None
    toolchain_hash: str
    input_artifact_hashes: list[str]
    output_artifact_hashes: list[str]
    started_at: datetime
    finished_at: datetime
    elapsed_ms: int
    deterministic: bool
    random_seed: str | None
```

### 10.4 Packet identity

`EvidencePacketV2` must contain:

```python
class EvidencePacketV2(VersionedStrictModel):
    schema_version: Literal["0.2.0"]
    packet_id: str
    evidence_fingerprint: str
    run_manifest: RunManifest
    candidate: CandidateDescriptorV2
    risk_class: RiskClass
    findings: list[EvidenceFindingV2]
    coverage_summary: dict[EvidenceDimension, EvidenceCoverage]
    hard_gate: HardGateResult
    recommendation: Recommendation
    recommendation_policy_id: str
    recommendation_reasons: list[str]
    unresolved_uncertainty: list[UncertaintyRecord]
    review_request: ReviewRequest | None
    created_at: datetime
```

### 10.5 Deterministic identity

`packet_id` must be:

```text
packet_<sha256(canonical run manifest + canonical findings + policy id)>
```

Random finding IDs and timestamps must not affect the evidence fingerprint.

Use stable finding IDs:

```text
finding_<check_id>_<subject_hash>_<check_version>
```

### 10.6 Evidence synthesis

Canonical checks such as `repository.api_fit` and `downstream.declared_use` must be derived from provider outputs.

Do not emit generic `UNKNOWN` after a provider has produced a complete executed result.

Implement a synthesis registry:

```python
SYNTHESIS_RULES = {
    "repository.api_fit": [...],
    "downstream.declared_use": [...],
    "semantic.intent_support": [...],
}
```

The synthesis rule version is part of the recommendation policy ID.

---

## 11. Semantic and repository evidence protocols

### 11.1 Statement difference

Statement comparison must use base and candidate elaborated declaration types.

It must report:

- binder count and binder type changes;
- explicit/implicit/instance binder changes;
- universe parameter changes;
- domain changes;
- conclusion changes;
- typeclass assumption changes;
- proposition versus data-type changes;
- theorem-to-definition kind changes;
- axiom-set changes.

The provider must never parse a single patch line as the authoritative candidate signature when elaborated snapshots exist.

### 11.2 Intent support

Automated evidence cannot certify mathematical intent.

Implement `semantic.intent_support` as an evidence bundle containing:

- source-intent reference;
- structural statement difference;
- project examples;
- counterexamples;
- terminology-policy findings;
- human semantic attestation status.

Only `HUMAN_ATTESTED` can satisfy final semantic fidelity for R3/R4.

### 11.3 Example fixture manifest

Replace directory-presence heuristics with a manifest:

```yaml
schema_version: 0.2.0
suite_id: examples-o01-v1
obligation_ids: [O-01]
fixtures:
  - fixture_id: comparison-functor-identity
    path: examples/comparison_functor_identity.lean
    expected_exit: 0
    expected_diagnostics: []
    basis: EXECUTED_TEST
```

Every fixture must declare:

- fixture ID;
- obligation binding;
- path;
- execution command kind;
- expected exit;
- expected diagnostic class;
- timeout;
- whether it runs on base, candidate, or both.

### 11.4 Counterexample fixture manifest

```yaml
schema_version: 0.2.0
suite_id: counterexamples-o01-v1
obligation_ids: [O-01]
fixtures:
  - fixture_id: rejects-stronger-assumption
    path: counterexamples/rejects_stronger_assumption.lean
    expected_exit: 1
    expected_diagnostic_regex: "failed to synthesize"
    semantic_interpretation: candidate must not require Preadditive
```

A counterexample test passes only when the expected failure class occurs. Any unrelated parser, import, or toolchain failure produces `UNKNOWN`.

### 11.5 Duplicate retrieval

Duplicate evidence must separate:

- exact elaborated type hash match;
- alpha-equivalent normalized type;
- mutual implication proof, when explicitly attempted;
- name/token similarity;
- repository-location similarity;
- human API-overlap judgment.

A token-similarity result remains `HEURISTIC_RETRIEVAL`.

### 11.6 Downstream successor contract

Each obligation requiring downstream value must declare successor tests:

```yaml
schema_version: 0.2.0
suite_id: downstream-o01-v1
obligation_ids: [O-01]
successors:
  - successor_id: O-02-naturality
    module: Example.Naturality
    declarations:
      - Example.comparisonFunctor_naturality
    command: ["lake", "env", "lean", "Example/Naturality.lean"]
    required: true
```

The provider runs the same successor suite on base and candidate.

It reports:

- base result;
- candidate result;
- newly enabled successors;
- regressed successors;
- unchanged successors;
- execution provenance.

### 11.7 API fit

Automated API evidence includes:

- public declaration additions/removals;
- visibility changes;
- namespace placement;
- duplicate candidates;
- import expansion;
- dependency expansion;
- nearby API patterns;
- naming-policy checks;
- impact-cone size.

Final repository acceptance for R2–R4 remains human-attested.

---

## 12. Human review and R3/R4 quorum

### 12.1 Attestation dimensions

Replace one undifferentiated review decision with:

- `SEMANTIC_FIDELITY`
- `REPOSITORY_FIT`
- `IMPLEMENTATION_QUALITY`
- `DOWNSTREAM_VALUE`
- `ADJUDICATION`

### 12.2 Review attestation

```python
class ReviewAttestationV2(VersionedStrictModel):
    schema_version: Literal["0.2.0"]
    attestation_id: str
    packet_id: str
    evidence_fingerprint: str
    reviewer_id: str
    reviewer_role: str
    dimension: ReviewDimension
    decision: Literal["ACCEPT", "REJECT", "REQUEST_REPAIR", "INDETERMINATE"]
    confidence: int
    rationale: str
    finding_refs: list[str]
    conflict_declaration_hash: str
    blinded_condition: str
    review_started_at: datetime
    review_submitted_at: datetime
    review_minutes: float
```

### 12.3 Conflict declaration

```python
class ReviewerConflictDeclaration(VersionedStrictModel):
    schema_version: Literal["0.2.0"]
    reviewer_id: str
    project_id: str
    candidate_id: str
    candidate_author: bool
    source_artifact_author: bool
    historical_reviewer: bool
    direct_collaborator: bool
    packet_constructor: bool
    outcome_seen_before_review: bool
    other_conflict: str | None
    eligible: bool
    signed_at: datetime
```

The system computes `eligible=false` when any disqualifying field is true.

### 12.4 Quorum

#### R0

- hard gates pass;
- complete required evidence;
- contract permits auto-accept;
- no human attestation required.

#### R1

- one eligible Lean/repository reviewer;
- `IMPLEMENTATION_QUALITY=ACCEPT`;
- hard gates pass.

#### R2

- one eligible repository maintainer;
- `REPOSITORY_FIT=ACCEPT`;
- semantic attestation required when the new theorem statement is project-authored or generated.

#### R3

Two distinct eligible reviewers are required:

1. domain reviewer with `SEMANTIC_FIDELITY=ACCEPT`;
2. repository maintainer with `REPOSITORY_FIT=ACCEPT`.

Both must reference the same evidence fingerprint.

#### R4

Three distinct eligible reviewers are required:

1. domain reviewer with `SEMANTIC_FIDELITY=ACCEPT`;
2. architecture maintainer with `REPOSITORY_FIT=ACCEPT`;
3. independent senior Lean reviewer with `IMPLEMENTATION_QUALITY=ACCEPT`.

### 12.5 Disagreement

Any `REJECT` blocks acceptance.

Any `REQUEST_REPAIR` creates a repair cycle.

Any `INDETERMINATE` blocks acceptance until the missing evidence is supplied or an adjudicator records a reasoned resolution.

Adjudication requires a reviewer who:

- was not an original reviewer;
- is conflict-free;
- has the configured adjudicator role;
- sees both attestations only after recording an independent provisional judgment.

### 12.6 Repair lineage

A repair creates a new candidate version:

```text
candidate_id = <root-candidate-id>.r<sequence>
```

The new candidate references:

- prior candidate ID;
- repair request IDs;
- applied change hash;
- new evidence fingerprint.

Prior attestations do not transfer automatically.

### 12.7 Acceptance aggregate

The system emits `ARTIFACT_ACCEPTED` only through a deterministic acceptance state machine.

The aggregate event contains:

- all attestation IDs;
- quorum policy ID;
- evidence fingerprint;
- semantic fidelity flag;
- repository acceptance flag;
- implementation acceptance flag;
- accepted obligation IDs;
- acceptance timestamp.

No individual review event may directly set both `semantic_fidelity` and `repository_accepted`.

---

## 13. Typed utility ledger `0.2.0`

### 13.1 Discriminated payloads

Replace `payload: dict[str, Any]` with a discriminated event union.

Required event payloads:

- `ObligationFreezePayload`
- `CandidateRegisteredPayload`
- `EvidenceCompiledPayload`
- `ReviewAssignedPayload`
- `ReviewAttestationPayload`
- `RepairRequestedPayload`
- `RepairCompletedPayload`
- `AcceptanceAggregatedPayload`
- `IntegrationConfirmedPayload`
- `DownstreamEnabledPayload`
- `PersistenceConfirmedPayload`
- `RegressionDetectedPayload`
- `ExpertTimePayload`
- `OverheadSnapshotPayload`
- `CorrectionPayload`
- `ProtocolFrozenPayload`
- `ConditionAssignedPayload`

### 13.2 Event envelope

```python
class UtilityEventV2(VersionedStrictModel):
    schema_version: Literal["0.2.0"]
    event_id: str
    event_type: EventTypeV2
    project_id: str
    artifact_id: str
    obligation_ids: list[str]
    occurred_at: datetime
    recorded_at: datetime
    actor_id: str
    protocol_freeze_id: str | None
    condition_assignment_id: str | None
    payload: EventPayload
    supersedes_event_id: str | None
```

### 13.3 Lifecycle state machine

Implement one reducer per artifact and obligation.

Valid transitions:

```text
OBLIGATION_FROZEN
  → CANDIDATE_REGISTERED
  → EVIDENCE_COMPILED
  → REVIEW_ASSIGNED
  → REVIEW_ATTESTED*
  → ACCEPTANCE_AGGREGATED | REPAIR_REQUESTED | ARTIFACT_REJECTED
  → REPAIR_COMPLETED → new candidate lineage
  → INTEGRATION_CONFIRMED
  → DOWNSTREAM_ENABLED
  → PERSISTENCE_CONFIRMED | REGRESSION_DETECTED
```

Invalid transitions are rejected at append time.

### 13.4 Obligation immutability

Only one active freeze version may govern a candidate.

A later obligation revision creates a new freeze ID and cannot retroactively alter registered candidates.

### 13.5 Corrections

A correction must state:

- target event;
- correction reason;
- replacement typed payload or explicit invalidation;
- correcting actor;
- authorization role.

TPPR v2 applies corrections deterministically.

### 13.6 Seals

Retain external seal support.

Add:

- seal sequence number;
- prior seal hash;
- protocol freeze hash;
- event count;
- ledger export hash;
- per-project tips;
- optional HMAC key identifier;
- custody location descriptor.

The system must warn when the seal is co-located and writable.

### 13.7 Migration

Provide:

```bash
lpe ledger migrate \
  --source ledger-v01.sqlite3 \
  --target ledger-v02.sqlite3 \
  --mapping-report migration-report.json
```

Migration must:

- preserve every original event;
- assign typed legacy wrappers where exact typing is impossible;
- mark ambiguous records `LEGACY_UNRESOLVED`;
- never infer missing acceptance or persistence fields;
- verify source and target chains;
- emit source/target seals.

---

## 14. TPPR v2

### 14.1 Credit rule

An obligation receives credit once when all conditions hold:

1. the obligation was frozen before candidate registration;
2. the candidate was accepted through the correct quorum;
3. integration was confirmed;
4. declared downstream evidence passed;
5. the persistence rule elapsed;
6. no unresolved regression invalidates the obligation;
7. the obligation has not been credited under another candidate lineage.

### 14.2 Persistence rule

Every obligation freeze includes:

```python
class PersistenceRule(StrictModel):
    rule_id: str
    mode: Literal["calendar_days", "repository_commits", "release_boundary"]
    threshold: int | str
    required_downstream_suite_ids: list[str]
    regression_policy: Literal["revoke", "suspend", "retain_with_flag"]
```

Pilot default:

- mode: `calendar_days`;
- threshold: `30`;
- regression policy: `revoke`.

### 14.3 Denominator

The denominator includes:

- contract and obligation specification;
- review;
- repair;
- integration.

Every time record must include:

- actor;
- candidate;
- obligation IDs;
- category;
- minutes;
- condition;
- source of measurement;
- confidence: exact timer, contemporaneous entry, or retrospective estimate.

Retrospective estimates are reported separately and excluded from the primary TPPR unless the frozen protocol permits them.

### 14.4 Condition reporting

TPPR v2 reports:

- overall;
- control;
- instrumented;
- shadow;
- risk class;
- artifact type;
- reviewer;
- project milestone;
- prospective versus legacy.

### 14.5 Audit table

Every report contains a numerator audit table:

| Obligation | Weight | Freeze | Candidate | Quorum | Integration | Downstream | Persistence | Credited |
|---|---:|---|---|---|---|---|---|---|

Every denominator record appears in a time audit table.

### 14.6 Missing data

The report must compute:

- complete-case TPPR;
- conservative lower bound treating unresolved accepted work as zero credit and including known time;
- denominator completeness rate;
- number of missing persistence outcomes;
- number of unresolved legacy events.

### 14.7 Anti-gaming

The reducer rejects:

- multiple weights for one freeze;
- obligation registration after candidate registration;
- duplicate credit;
- candidate splitting without distinct predeclared obligations;
- persistence before integration;
- persistence before the rule threshold;
- acceptance without required attestations;
- time with an unknown category;
- anonymous actors.

---

## 15. Pilot protocol bundle

### 15.1 Replace editable Markdown blanks

Create a machine-readable protocol bundle:

```text
pilot-protocol/
├── protocol.yaml
├── endpoints.yaml
├── assignment.yaml
├── reviewer-roster.yaml
├── held-out-set.json
├── comprehension.yaml
├── analysis.yaml
└── signatures.json
```

The CLI validates every file and refuses to freeze an incomplete bundle.

### 15.2 Protocol schema

```python
class PilotProtocol(VersionedStrictModel):
    schema_version: Literal["0.3.0"]
    protocol_id: str
    project_id: str
    repository_remote: str
    repository_commit_at_freeze: str
    contract_freeze_id: str
    sample_size_min: int
    sample_size_max: int
    recruitment_window_start: date
    recruitment_window_end: date
    persistence_followup_days: int
    condition_design: ConditionDesign
    endpoints: EndpointPlan
    exclusion_rules: list[ExclusionRule]
    stopping_rules: list[StoppingRule]
    held_out_set_hash: str
    analysis_plan_hash: str
    reviewer_roster_hash: str
```

Dates and IDs are required command inputs at protocol creation. The repository must not ship blank partner values.

### 15.3 Condition design

Use a blocked 2:2:1 allocation:

- 40% `control`;
- 40% `instrumented`;
- 20% `shadow`.

Definitions:

- `control`: ordinary review; LPE execution occurs only after the reviewer outcome is sealed;
- `instrumented`: LPE executes before review and the packet is visible;
- `shadow`: LPE executes before review, the packet remains hidden, and ordinary review proceeds.

### 15.4 Assignment algorithm

Assignment is deterministic from the frozen seed.

1. Stratify by risk class and artifact type.
2. Create blocks of five.
3. Assign two control, two instrumented, one shadow within each block.
4. Shuffle within blocks using HMAC-SHA256:
   - key: frozen randomization seed;
   - message: protocol ID, stratum ID, candidate ID.
5. Enforce reviewer workload balance.
6. Prevent a candidate author from reviewing their candidate.
7. Prevent a reviewer from seeing both original and repaired versions when blinding would be compromised.
8. Record the assignment artifact before review.

The seed is stored encrypted during operation and disclosed after data lock.

### 15.5 Minimum sample

The pilot requires:

- 30–50 prospective candidate-review episodes;
- at least 12 control episodes;
- at least 12 instrumented episodes;
- at least 6 shadow episodes;
- at least 8 R3/R4 episodes;
- at least two reviewers;
- at least one domain reviewer and one repository maintainer.

The pilot remains calibration-scale. It does not support broad population claims.

### 15.6 Primary endpoints

Primary operational endpoint:

\[
\frac{
\text{weighted accepted obligations with complete quorum}
}{
H_{\mathrm{review}} + H_{\mathrm{repair}}
}
\]

Primary safety endpoint:

- proportion of adjudicated L2/L3 defects identified before integration.

Primary North-Star endpoint after follow-up:

- TPPR v2 by condition.

### 15.7 Secondary endpoints

- median review minutes;
- median repair minutes;
- packet automation rate;
- exact-environment reproduction rate;
- escalation precision;
- indeterminate rate;
- reviewer agreement;
- instrumentation overhead;
- evidence-dimension comprehension;
- downstream regression rate;
- packet construction manual-intervention minutes.

### 15.8 Reviewer comprehension

Before pilot review, each reviewer completes five external calibration cases.

Pass criteria:

- at least four of five material-defect judgments match the adjudicated label;
- no systematic semantic-to-proof-search confusion;
- at least four of five evidence-basis questions correct;
- conflict and blinding acknowledgment signed.

A failing reviewer may repeat once after training. A second failure excludes them from primary analysis.

### 15.9 Data lock

Data lock requires:

- all expected candidate episodes complete;
- all review attestations submitted;
- condition assignments verified;
- ledger chain verified;
- off-host seal verified;
- exclusions resolved;
- analysis container digest recorded;
- protocol hash matched;
- held-out set hash matched.

After data lock, corrections require a signed correction event and a new analysis version.

---

## 16. Statistical and gate specification

### 16.1 Descriptive analysis

Report by condition:

- count;
- risk distribution;
- artifact-type distribution;
- reviewer distribution;
- median and interquartile range of time;
- acceptance, repair, rejection, and indeterminate rates;
- L2/L3 defect recovery;
- automation and reproduction;
- TPPR and bounds.

### 16.2 Agreement

Compute:

- Cohen's kappa for two reviewers;
- Fleiss' kappa when more than two;
- Gwet AC1 as a prevalence-robust companion;
- bootstrap 95% confidence intervals.

### 16.3 Pilot success gates

The pilot passes the shadow-pilot gate only when all are true:

1. packet automation rate is at least 80%;
2. exact-environment reproduction is at least 90%;
3. median instrumentation overhead is below 10% of expert review time;
4. 90th-percentile instrumentation overhead is below 20%;
5. reviewer comprehension pass rate is at least 80%;
6. primary-category agreement is at least 0.70 by Cohen/Fleiss kappa or Gwet AC1;
7. instrumented median review-plus-repair time per accepted weighted obligation is at least 20% lower than control;
8. instrumented L2/L3 defect sensitivity is no more than five percentage points below control;
9. no additional integrated L3 defect occurs in the instrumented condition;
10. the protocol, ledger export, analysis, and report are sealed and reproducible.

The 20% efficiency threshold is a pilot advancement threshold. It is not a claim of population effect.

### 16.4 §21 gate report

Implement:

```bash
lpe research evaluate-gates \
  --protocol pilot-protocol/protocol.yaml \
  --ledger locked-ledger.jsonl \
  --seal locked-ledger.seal.json \
  --analysis analysis-output.json \
  --output section21-gates.json
```

The output is:

```python
class Section21GateReport(VersionedStrictModel):
    schema_version: Literal["0.3.0"]
    protocol_id: str
    data_lock_hash: str
    gates: list[GateEvaluation]
    shadow_pilot_passed: bool
    learned_routing_authorized: bool
    synthesis_authorized: bool
    blocking_reasons: list[str]
    generated_at: datetime
    evaluator_version: str
```

The evaluator authorizes learned routing only when the shadow-pilot gate passed and the dataset sufficiency requirements in Section 17 are met.

---

## 17. Learned routing specification

This section remains blocked until `learned_routing_authorized=true`.

### 17.1 Objective

Predict the next review question that resolves the largest acceptance-controlling uncertainty per expert minute.

The model does not predict automatic acceptance.

### 17.2 Training unit

One training record contains:

- project and contract context;
- candidate evidence vector;
- unresolved findings;
- deterministic baseline question;
- human-selected or adjudicated question;
- answer;
- time to answer;
- whether the answer changed the decision;
- downstream outcome.

### 17.3 Leakage controls

Exclude from features:

- final decision;
- future repair outcome;
- persistence outcome;
- reviewer rationale written after the answer;
- condition label when it reveals intervention;
- any post-review evidence.

### 17.4 Splits

Use:

- project-held-out split;
- time-held-out split;
- repaired-lineage grouping;
- reviewer-held-out sensitivity analysis.

No candidate lineage may cross train and test.

### 17.5 Baseline

The required baseline is `deterministic_baseline.v1`.

### 17.6 Offline metrics

- top-1 match with adjudicated question;
- normalized discounted cumulative gain over useful questions;
- predicted versus actual review minutes;
- decision-changing question recall;
- abstention calibration;
- L2/L3 safety stratification.

### 17.7 Advancement

A learned router advances to prospective testing only when:

- held-out expected review minutes fall by at least 15%;
- decision-changing question recall does not decrease;
- L2/L3 strata show no safety degradation;
- calibration error is within the preregistered bound;
- model card, data lineage, and reproducible training container are complete.

---

## 18. Project-targeted synthesis specification

This section remains blocked until `synthesis_authorized=true`.

### 18.1 Objective

Generate or select Lean training data that increases TPPR on fresh project obligations.

### 18.2 Candidate sources

- helper lemmas for unresolved obligations;
- alternative statements;
- proof decompositions;
- premise sets;
- counterexamples;
- repair trajectories;
- generalizations;
- repository API alternatives.

### 18.3 Selection arms

Compare equal-budget datasets selected by:

- random kernel-valid sampling;
- difficulty;
- novelty;
- model confidence;
- project-conditioned utility.

### 18.4 Equal-budget constraints

Every arm receives the same:

- generated token budget;
- verification compute budget;
- accepted example count or weighted example count;
- training token budget;
- optimizer schedule;
- evaluation budget.

### 18.5 Evaluation

Train from the same base model and evaluate on:

- held-out obligations in the same project;
- later repository snapshots;
- held-out repositories;
- held-out mathematical domains.

The primary endpoint is change in TPPR or the preregistered trusted-progress proxy.

Compilation rate and proof success remain secondary.

---

## 19. CI, quality, and release engineering

### 19.1 Default pull-request CI

Run:

- Python 3.12 and 3.13 on Ubuntu;
- Python 3.12 on macOS and Windows for pure-Python tests;
- Ruff formatting and lint;
- strict MyPy;
- schema export drift;
- unit, integration, security, and property tests;
- package build;
- wheel installation smoke;
- dependency audit;
- CODEOWNERS validation;
- documentation-link validation;
- manifest/tree freshness validation.

### 19.2 Scheduled CI

Run weekly:

- Lean compatibility matrix;
- Docker generic extractor;
- bounded Mathlib-backed extraction;
- 100k ledger longevity;
- performance baselines;
- image build and vulnerability scan;
- live GitHub Check test against a dedicated test repository.

### 19.3 Coverage

Set:

- overall line coverage at least 90%;
- policy, gate, review, ledger, TPPR, and protocol modules at least 95%;
- branch coverage at least 85%.

Coverage cannot replace semantic test quality.

### 19.4 Static checks

`make check` must include:

```bash
ruff format --check .
ruff check .
mypy src/lpe
python scripts/export_schemas.py --check
python scripts/validate_examples.py
pytest
python -m build
python scripts/verify_wheel.py dist/*.whl
```

### 19.5 Releases

Each release must publish:

- source archive;
- wheel;
- generated schemas;
- SBOM;
- build provenance;
- checksums;
- changelog;
- migration notes;
- validation report;
- compatibility matrix;
- explicit non-claims.

### 19.6 Documentation consistency

Automate checks that:

- package version, changelog, validation report, and audit report agree;
- test counts are generated, not hand-copied;
- `REPOSITORY_TREE.txt` and `MANIFEST.sha256` are current;
- M0–M7 status appears in one canonical machine-readable file;
- README status does not describe implemented M3/M4 work as merely deferred.

---

## 20. Repository governance

### 20.1 GitHub configuration

- protect `main`;
- require pull requests;
- require current CI checks;
- require CODEOWNER approval for schemas, execution, review, ledger, metrics, protocol, and ADRs;
- require two approvals for security and schema changes;
- dismiss stale approvals;
- require conversation resolution;
- block force pushes and branch deletion;
- enable secret scanning and dependency alerts;
- enable auto-merge after all required checks;
- permit squash merge as the default history policy.

### 20.2 Current Dependabot PR

Review and merge or supersede PR #1 only after:

- updating the pinned full commit SHA;
- verifying Node runtime compatibility;
- running the complete CI matrix;
- preserving the version comment.

### 20.3 GitHub issues

The repository currently has no open implementation issues.

Import the closure backlog supplied with this specification and assign milestones before starting the closure work.

### 20.4 Decision ownership

- research lead owns North Star, protocol, §21, and claims;
- Lean systems owner owns extractor correctness and compatibility;
- platform owner owns workspace, executor, artifacts, and CI;
- data owner owns typed ledger, migration, and TPPR;
- review-methods owner owns quorum, blinding, and adjudication;
- security owner approves sandbox, seals, releases, and incidents.

One person may hold multiple ownership roles, but approvals for R4 protocol or security changes require a second reviewer.

---

## 21. Implementation sequence

### Phase A — Immediate integrity corrections

1. create `EvaluationWorkspace`;
2. keep worktrees alive through all providers;
3. remove host subprocess calls from semantic providers;
4. pass executor and snapshot context to providers;
5. harden Docker mounts and identity;
6. fix evidence fingerprint completeness;
7. remove duplicate sandbox function;
8. add regression tests.

No pilot work begins before Phase A passes.

### Phase B — Generic extraction and paired snapshots

1. ship generic extractor package;
2. extract base and candidate;
3. implement declaration diff;
4. switch risk classification to elaborated diff;
5. create compatibility matrix;
6. validate real repositories.

### Phase C — Schema and ledger v2

1. add schema `0.2.0`;
2. implement typed event union;
3. implement lifecycle reducers;
4. implement migration;
5. implement TPPR v2;
6. retain legacy read support.

### Phase D — Human review protocol

1. implement conflict declarations;
2. implement dimension-specific attestations;
3. implement R3/R4 quorum;
4. implement repair lineage;
5. implement adjudication;
6. implement acceptance aggregate.

### Phase E — Pilot operation

1. implement protocol bundle;
2. implement freeze and signatures;
3. implement assignment;
4. implement reviewer calibration;
5. implement field instrumentation;
6. implement data lock;
7. implement analysis and §21 gates.

### Phase F — Prospective execution

1. select the partner repository and domain lead;
2. create and freeze its contract and obligations;
3. freeze protocol;
4. execute 30–50 episodes;
5. complete persistence;
6. lock data;
7. run analysis;
8. publish engineering and methodological results.

### Phase G — Post-gate research

Implement M6 and M7 only after machine-readable authorization.

---

## 22. Definition of done

The closure program is complete when all of the following are true.

### Evidence integrity

- every finding has one snapshot fingerprint;
- all executable providers use the selected executor;
- no semantic provider reads the operator checkout;
- base/head paired extraction is generic;
- packet identity includes complete run provenance;
- evidence basis and coverage are explicit.

### Human control

- R3/R4 auto-accept remains impossible;
- qualified R3/R4 human acceptance works through quorum;
- conflict, blinding, repair, and adjudication are enforced;
- acceptance events derive from attestations.

### Metric integrity

- obligation freezes are immutable;
- typed events validate lifecycle transitions;
- TPPR credit is unique, sustained, and auditable;
- corrections are applied;
- condition and missing-data reports exist.

### Pilot readiness

- protocol bundles contain no blank required fields;
- freeze and assignment are reproducible;
- reviewer comprehension is validated;
- data lock and seals work;
- §21 gate output is machine-readable.

### Operational quality

- CI matrix and scheduled compatibility jobs pass;
- package and image artifacts are reproducible;
- release documents agree;
- no open P0 or P1 closure issue remains;
- security and methodology reviews sign off.

### Scientific honesty

- the repository continues to distinguish engineering validation from causal evidence;
- M6/M7 remain blocked until gate authorization;
- reports preserve the canonical non-claims;
- every positive claim cites the exact sealed dataset and analysis version.

---

## 23. Final engineering directive

The engineering team should treat candidate-consistent evidence as the immediate product.

The next release must not add more heuristics, model providers, dashboards, or generated data until the following sentence is mechanically true:

> Every finding, review question, attestation, acceptance decision, persistence record, and TPPR credit can be traced to one immutable project contract, one predeclared obligation freeze, one exact candidate snapshot, one executor configuration, and one auditable event lineage.

That invariant is the foundation required for a credible pilot and for every later learned or synthetic-data capability.
