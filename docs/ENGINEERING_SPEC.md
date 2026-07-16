# Lean Project Evidence — Standalone Engineering Specification

## 1. Executive decision

Build a project-grounded evidence compiler around existing Lean provers and repositories.

The system accepts a project contract, a predeclared obligation, an exact repository state, and a candidate Lean artifact. It produces a provenance-complete evidence packet and one of three recommendations:

- `ACCEPT`
- `REJECT`
- `ESCALATE`

The system does not attempt to become a universal theorem prover or a universal mathematical-quality oracle.

## 2. Product thesis

The missing capability in AI-assisted Lean development is a scalable signal for whether a kernel-valid artifact preserves intended mathematics, fits the repository, advances a real project obligation, and remains valuable after integration.

The product must make this signal explicit, inspectable, and measurable.

## 3. North Star

\[
\operatorname{TPPR}
=
\frac{
\sum_i w_i F_i A_i S_i
}{
H_{\text{spec}}+H_{\text{review}}+H_{\text{repair}}+H_{\text{integration}}
}.
\]

Each obligation is registered before candidate generation.

- \(w_i\) is the predeclared critical-path weight.
- \(F_i\) means semantic fidelity was accepted.
- \(A_i\) means the artifact was accepted in the exact repository.
- \(S_i\) means the artifact enabled its declared downstream use and remained integrated.
- The denominator measures all scarce expert time.

Compute, latency, and monetary cost are reported as guardrails.

## 4. Scope

### 4.1 In scope for version 0

- split project contracts stored in the target repository;
- contract validation and versioning;
- predeclared obligation management;
- Git change classification;
- exact-environment build execution;
- deterministic hard gates;
- evidence packet generation;
- risk classification from `R0` through `R4`;
- accept, reject, and escalate recommendations;
- structured review questions and decisions;
- append-only utility events;
- TPPR reporting;
- CLI and machine-readable JSON output;
- CI integration.

### 4.2 Deferred behind stable interfaces

- Lean declaration and dependency extraction;
- exact impact-cone construction;
- statement implication and equivalence checks;
- counterexample generation;
- repository semantic retrieval;
- successor-theorem replacement testing;
- model-assisted interpretation;
- GitHub App and hosted API;
- learned review routing;
- project-conditioned data synthesis.

### 4.3 Explicit non-goals

- replacing the Lean kernel;
- replacing Lake or elan;
- building another general theorem prover;
- auto-merging high-risk semantic changes;
- assigning one opaque universal quality score;
- training a quality model before utility-ledger data exists;
- optimizing benchmark pass rates detached from project progress.

## 5. Core invariants

1. Every candidate is bound to one project, one exact repository state, and at least one predeclared obligation.
2. Every evidence item records provenance, tool version, input hash, execution time, and status.
3. Evidence dimensions remain separate. The system never collapses them into a single scalar in version 0.
4. High-risk statement, definition, and public-API changes require human acceptance.
5. Hard failures are deterministic and reproducible.
6. The utility ledger is append-only and hash-chained.
7. Review, repair, and integration time are first-class data.
8. Accepted artifacts receive a later persistence event.
9. Candidate generation and proof search are replaceable providers.
10. The target repository's `lean-toolchain` and Lake configuration are authoritative.

## 6. Domain model

### 6.1 Project contract

A project contract contains:

- stable project identity;
- repository and execution policy;
- mathematical intent;
- terminology bindings;
- obligation graph;
- risk and acceptance policies;
- reviewer authority;
- test declarations.

The contract is stored in `.lean-project-contract/`.

### 6.2 Obligation

An obligation is a predeclared unit of project progress.

Required fields:

- stable ID;
- description;
- artifact type;
- weight from 1 to 3;
- status;
- milestone;
- downstream obligation IDs;
- acceptance conditions;
- owner.

### 6.3 Candidate

A candidate identifies:

- project;
- obligation IDs;
- base commit;
- head commit or patch;
- generator provenance;
- claimed intent;
- changed paths;
- optional prior declaration references.

### 6.4 Evidence finding

A finding has:

- category;
- check ID and version;
- status;
- severity;
- summary;
- structured details;
- provenance;
- input and output hashes;
- elapsed time.

### 6.5 Evidence packet

The packet contains:

- normalized project, obligation, repository, and candidate references;
- risk class;
- evidence vector;
- unresolved uncertainty;
- hard-gate outcome;
- recommended decision;
- one prioritized review question;
- estimated review effort;
- complete provenance.

### 6.6 Review decision

A review decision contains:

- reviewer identity or pseudonymous ID;
- authority scope;
- answer;
- confidence;
- rationale;
- elapsed review time;
- required repair;
- final decision.

### 6.7 Utility event

The ledger records lifecycle events such as:

- candidate registered;
- evidence compiled;
- review requested;
- review submitted;
- repair started;
- repair completed;
- accepted;
- rejected;
- integrated;
- downstream enabled;
- regression detected;
- persistence confirmed.

## 7. Risk model

- `R0` — proof-only change under an unchanged trusted statement.
- `R1` — private helper lemma or local implementation change.
- `R2` — public theorem or low-scope API addition.
- `R3` — theorem-statement, definition, assumption, or public-interface change.
- `R4` — foundational definition, architecture, imports, or broad public-API redesign.

Default authority:

- `R0` may become eligible for automatic acceptance after deterministic evidence is complete.
- `R1` requires lightweight repository review.
- `R2` requires repository review.
- `R3` requires semantic and repository review.
- `R4` requires project-lead and architecture review.

Version 0 automatically accepts no `R3` or `R4` candidate.

## 8. Evidence compiler pipeline

### 8.1 Normalize inputs

- resolve absolute target repository path;
- read contract;
- validate schemas;
- verify candidate project and obligation IDs;
- resolve exact base and head commits;
- compute immutable content hashes.

### 8.2 Classify the change

Identify:

- changed Lean files;
- changed declarations;
- declaration kinds;
- proof-only versus signature change;
- imports;
- public paths;
- possible architecture changes.

The version 0 lexical classifier is conservative. Unknown changes escalate.

### 8.3 Execute the exact environment

- create an isolated Git worktree;
- disable network access when the execution backend supports it;
- use the target repository's toolchain;
- run the configured build command;
- capture stdout, stderr, exit code, duration, and command hash;
- enforce timeout and output limits;
- preserve logs as content-addressed artifacts.

### 8.4 Run deterministic gates

Initial gates:

- contract valid;
- obligation exists and was predeclared;
- base and head resolve;
- build succeeds;
- no prohibited placeholders;
- no prohibited axiom finding;
- changed paths respect policy;
- declared evidence artifacts are present.

### 8.5 Compile evidence

Evidence dimensions:

- `kernel`
- `semantic`
- `repository`
- `downstream`
- `persistence`
- `uncertainty`

Every dimension may contain `PASS`, `FAIL`, `WARN`, `UNKNOWN`, or `NOT_APPLICABLE`.

### 8.6 Select recommendation

- Any hard failure produces `REJECT`.
- Complete evidence for an eligible low-risk change may produce `ACCEPT`.
- High risk, unknown evidence, conflicting evidence, or insufficient contract information produces `ESCALATE`.

### 8.7 Select one review question

The review router prioritizes the unresolved issue with the largest expected effect on the decision.

Version 0 uses deterministic priority:

1. mathematical intent;
2. definition or assumption choice;
3. public API and abstraction fit;
4. dependency or import architecture;
5. downstream behavior;
6. naming or placement;
7. proof maintainability.

## 9. Architecture

Use a modular monolith.

### 9.1 Python orchestration core

Responsibilities:

- contracts and schemas;
- candidate normalization;
- Git inspection;
- subprocess execution;
- evidence assembly;
- decision policy;
- review routing;
- utility ledger;
- metrics;
- reporting.

### 9.2 Lean adapter boundary

The Lean adapter must run inside the target repository's toolchain and communicate through JSON files or stdout.

Planned commands:

- declaration metadata;
- declaration signature hash;
- axiom dependencies;
- direct declaration dependencies;
- transitive dependency closure;
- direct downstream users;
- transitive impact cone;
- placeholder report;
- generated probe compilation.

The adapter is versioned separately from the Python protocol.

### 9.3 Storage

Version 0 uses SQLite for the append-only event ledger.

Reasons:

- local-first operation;
- transactional writes;
- simple inspection and export;
- no service deployment dependency;
- adequate scale for research pilots.

Large logs and build artifacts remain in a content-addressed filesystem store. The ledger stores hashes and paths.

### 9.4 Provider interfaces

External capabilities implement stable protocols:

- `LeanExecutor`
- `RepositoryRetriever`
- `SemanticChecker`
- `CounterexampleProvider`
- `InterpretationProvider`
- `ReviewQuestionProvider`
- `ArtifactStore`

Provider failures become explicit evidence findings and never silently change the decision.

## 10. CLI

Canonical commands:

```text
lpe doctor
lpe contract validate PROJECT
lpe candidate validate CANDIDATE.json
lpe evidence compile --project PROJECT --candidate FILE --output FILE
lpe ledger init PATH
lpe ledger append PATH EVENT.json
lpe ledger verify PATH
lpe tppr compute PATH
```

Every command supports JSON output and nonzero exit codes.

## 11. API

Version 0 is CLI-first. A future service interface is frozen in `openapi/openapi.yaml`.

The API must remain a thin wrapper around application services. Business logic never lives in HTTP handlers.

## 12. Repository scaffold

```text
lean-project-evidence/
├── .github/
├── backlog/
├── docs/
├── examples/
├── openapi/
├── schemas/
├── scripts/
├── src/lpe/
├── tests/
├── pyproject.toml
├── Makefile
└── README.md
```

## 13. Security model

Target repositories and generated code are untrusted.

Required controls:

- execute in an isolated worktree;
- allow a container or sandbox backend;
- default to no network for builds;
- pass an explicit environment allowlist;
- enforce wall-clock timeout;
- enforce output-size limits;
- never forward repository content to an external model without policy authorization;
- never expose CI secrets to target build commands;
- hash all inputs and outputs;
- record the executed command and toolchain;
- redact configured secrets from logs;
- pin GitHub Actions by major version initially and by commit for production.

## 14. Privacy

Contracts may contain unpublished mathematics.

The default provider policy is local-only.

External provider calls require:

- an explicit project policy;
- a field-level disclosure record;
- provider identity and model version;
- retention-policy acknowledgement;
- redaction rules;
- event-ledger record.

## 15. Testing

### Unit tests

- schema and model validation;
- risk classification;
- hard gates;
- decision policy;
- review-question priority;
- hash-chain ledger;
- TPPR calculation.

### Contract tests

Every provider has a protocol conformance suite.

### Golden tests

Evidence packets for fixed fixtures are snapshot-tested.

### Integration tests

- temporary Git repository;
- deterministic diff;
- mock Lean build;
- timeout and failure behavior;
- ledger persistence;
- CLI end-to-end execution.

### Lean compatibility tests

The eventual Lean adapter is tested against a declared matrix of historical toolchains and target projects. Compatibility is reported, never inferred.

### Research validation

A software test does not establish scientific validity. Shadow-mode experiments compare ordinary review, evidence-assisted review, and evidence-plus-question review.

## 16. Observability

Every pipeline run receives:

- `run_id`;
- `project_id`;
- `candidate_id`;
- `contract_version`;
- `compiler_version`;
- timestamps;
- stage durations;
- input and output hashes;
- provider versions;
- decision;
- error status.

Version 0 emits structured JSON logs.

## 17. Performance targets

Initial operational targets:

- contract validation under one second;
- diff classification under five seconds for a normal PR;
- orchestration overhead below 10% of Lean build time;
- idempotent evidence compilation;
- evidence packet under 1 MB excluding logs;
- ledger append under 100 ms;
- review packet generation under 30 seconds after evidence completes.

Lean build time is excluded from orchestration latency.

## 18. Failure behavior

- Invalid contract stops the run.
- Unresolvable repository state stops the run.
- Build failure produces deterministic rejection.
- Provider timeout produces `UNKNOWN` evidence and escalation unless it is a required hard gate.
- Schema-version mismatch stops the run.
- Ledger verification failure blocks metric reporting.
- Missing persistence data prevents sustained credit.

## 19. Versioning

- schemas use semantic versions;
- every serialized object includes `schema_version`;
- backward-compatible fields may be added in minor versions;
- removals or meaning changes require a major version;
- evidence check IDs include a check version;
- old evidence remains interpretable through retained schemas.

## 20. Definition of done for version 0.1

Version 0.1 is complete when:

1. an example project contract validates;
2. a real Git candidate is classified;
3. an exact build can be invoked through the executor interface;
4. deterministic gates create a valid evidence packet;
5. an `R3` candidate is escalated with one structured question;
6. a review decision can be recorded;
7. acceptance and persistence events can be appended;
8. the ledger hash chain verifies;
9. TPPR can be computed;
10. CI, tests, documentation, and examples pass.

## 21. Scientific release gate

The product may advance from scaffold to shadow pilot when:

- packet construction is at least 80% automated;
- exact-environment reproduction succeeds on at least 90% of selected cases;
- reviewers understand the evidence dimensions;
- instrumentation overhead remains below 10% of expert time;
- the study protocol and analysis are frozen.

The product may advance to learned routing when:

- enough accepted, revised, rejected, and persistence outcomes exist;
- held-out evaluation is available;
- deterministic baselines are established;
- learning demonstrably improves TPPR or a preregistered short-horizon proxy.

## 22. Team responsibilities

### Research lead

- owns problem definition and TPPR;
- controls scope and scientific gates;
- approves contract semantics and evaluation design.

### Lean systems engineer

- owns exact-toolchain execution;
- owns Lean extraction protocol;
- owns compatibility testing and impact analysis.

### Research software engineer

- owns Python application, schemas, CLI, ledger, packaging, and CI.

### ML engineer

- initially owns provider interfaces and evaluation harnesses;
- begins learned systems only after utility data exists.

### Project domain lead

- authors intent and obligations;
- accepts high-risk semantic changes;
- validates downstream project value.

## 23. Implementation order

1. repository and CI;
2. schemas and models;
3. contract loader;
4. stable IDs and hashing;
5. append-only ledger;
6. TPPR;
7. Git change classifier;
8. exact-environment executor;
9. deterministic gates;
10. evidence packet renderer;
11. risk and decision policy;
12. review routing;
13. example project;
14. first real repository integration;
15. Lean extraction adapter;
16. downstream tests;
17. semantic checks;
18. shadow pilot.

## 24. Governing principle

The team should reject any implementation proposal that primarily increases generated artifacts, model throughput, or benchmark scores without a causal path to higher TPPR.
