# System architecture

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
