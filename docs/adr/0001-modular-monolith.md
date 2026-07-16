# ADR 0001 — Modular monolith

## Status

Accepted.

## Decision

Begin with a local Python modular monolith and SQLite event store.

## Rationale

The primary risk is scientific and semantic, not horizontal scale. A monolith preserves transactional integrity, reproducibility, and rapid iteration.

## Revisit

Revisit only when measured workloads or security boundaries require an independently deployable component.
