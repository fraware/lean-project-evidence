# Engineering team instructions

## Mission

Build the smallest trustworthy system that increases critical-path, semantically faithful, repository-accepted, sustained Lean project progress per expert hour.

## Repository name

`lean-project-evidence`

## CLI and package name

- CLI: `lpe`
- Python package: `lpe`

## First action

Create a new GitHub repository and push this scaffold without modifying its architecture.

Do not begin Lean extraction, model integration, or hosted-service work until Milestone 0 passes.

## Required reading order

1. `README.md`
2. `docs/ENGINEERING_SPEC.md`
3. `docs/adr/0001-modular-monolith.md`
4. `docs/adr/0002-evidence-vector.md`
5. `docs/adr/0003-human-authority.md`
6. `docs/adr/0004-append-only-ledger.md`
7. `docs/16_REPOSITORY_LAUNCH.md`
8. `docs/17_FIRST_30_DAYS.md`
9. `backlog/issues.csv`

## Repository creation

Create the repository as public under the chosen organization unless unpublished implementation or partner constraints require a temporary private repository.

Use Apache-2.0.

Do not initialize a separate README, license, or `.gitignore` in GitHub because this scaffold already contains them.

```bash
cd lean-project-evidence
git init
git add .
git commit -m "chore: initialize Lean Project Evidence"
git branch -M main
git remote add origin git@github.com:ORGANIZATION/lean-project-evidence.git
git push -u origin main
```

## Mandatory GitHub settings

- protect `main`;
- require pull requests;
- require one approval initially and two for schemas, execution, ledger, and ADR changes;
- require the `python` CI job;
- dismiss stale approvals after new commits;
- require conversation resolution;
- block force pushes and branch deletion;
- enable secret scanning and dependency alerts;
- configure CODEOWNERS before the first engineering PR;
- restrict release permissions.

## Work policy

Each pull request must:

- link one backlog issue;
- state its path to TPPR;
- include tests;
- preserve evidence and provenance;
- document uncertainty;
- avoid unrelated infrastructure.

## Milestone discipline

### Milestone 0

Finish and harden:

- contracts;
- schemas;
- stable hashing;
- append-only ledger;
- TPPR;
- packaging;
- CI.

### Milestone 1

Build deterministic evidence:

- Git classification;
- isolated build runner;
- hard gates;
- evidence packets;
- risk and decision policy.

### Milestone 2

Build human review:

- authority validation;
- review question;
- decision recording;
- GitHub Check output.

No learned model work begins before the shadow pilot produces sufficient utility-ledger data.

## Engineering defaults

- Python 3.12.
- Pydantic for typed contracts.
- SQLite for version 0 ledger.
- JSON Schema 2020-12 for interchange.
- CLI-first.
- local-only providers by default.
- target repository `lean-toolchain` is authoritative.
- no network in production build sandboxes.
- high-risk semantic changes remain human-controlled.

## Immediate ownership assignments

Assign named owners for:

- research and North Star;
- schemas and domain model;
- Lean execution and extraction;
- ledger and metrics;
- security and sandboxing;
- first pilot repository.

Replace placeholders in `.github/CODEOWNERS` before the first merge. Role assignments are documented in `MAINTAINERS.md`.

## First sprint deliverables

- repository settings and labels;
- passing CI from a clean clone;
- schema compatibility policy;
- complete ledger tests;
- CLI error contract;
- sandbox design review;
- selection of the first active pilot repository;
- approved Project Contract for its current milestone.

## Stop conditions

Pause implementation and escalate when:

- a design requires changing the North Star;
- evidence is being collapsed into an opaque scalar;
- an automatic decision is proposed for `R3` or `R4`;
- generated code would receive CI secrets;
- a provider sends project data externally without explicit policy;
- a schema meaning changes without a major version;
- a feature has no credible path to TPPR.
