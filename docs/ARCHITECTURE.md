# Architecture

## Primary user

A formalization lead or repository maintainer evaluating AI-assisted Lean work inside an active project.

## User job

Determine whether a candidate artifact should be accepted, rejected, repaired, or escalated, with less expert effort and stronger evidence.

## Required outcomes

- recover exact project context;
- show what changed semantically and architecturally;
- reveal hard verification failures;
- expose missing evidence;
- identify the smallest acceptance-controlling question;
- preserve the full lifecycle outcome;
- report progress per expert hour.

## Product constraints

- local-first;
- repository-native;
- exact-toolchain;
- model-independent;
- human-controlled for high-risk semantics;
- inspectable evidence;
- no scalar quality score in version 0.

## Decision

Use a modular monolith with hexagonal boundaries.

## Modules

- `contract` — load and validate project contracts.
- `git` — normalize commits and classify changes.
- `execution` — run exact-environment commands.
- `evidence` — compile findings and apply gates.
- `review` — select questions and record decisions.
- `ledger` — append lifecycle events.
- `metrics` — compute TPPR and guardrails.
- `providers` — protocols for external capabilities.
- `reporting` — JSON and Markdown output.

## Dependency direction

Domain models have no dependency on CLI, subprocess, SQLite, GitHub, or model providers.

Adapters depend on domain protocols.

Application services coordinate adapters and domain policy.

## Deployment

Version 0 is a local CLI and CI job.

A hosted service remains optional and cannot become required for local evidence compilation.

## Related

- Full product contract: [`ENGINEERING_SPEC.md`](ENGINEERING_SPEC.md)
- ADRs: [`adr/`](adr/)
