# Lean Project Evidence

**Lean Project Evidence** (`lpe`) is a project-grounded evidence and review layer for AI-assisted Lean development.

The system evaluates a candidate statement, definition, proof, or repository patch against:

- the mathematical intention of the project;
- the exact Lean repository and dependency state;
- a predeclared critical-path obligation;
- repository architecture and downstream uses;
- later persistence and repair outcomes.

The product is designed around one North Star:

\[
\text{TPPR}
=
\frac{\text{weighted critical-path obligations accepted and sustained}}
{\text{expert specification, review, repair, and integration hours}}.
\]

## Problem

Kernel verification establishes that a proof term proves a proposition in an environment. It does not establish that the proposition expresses the intended mathematics, fits the repository's abstractions, advances the project milestone, or deserves to become training data.

`lpe` compiles project intent and repository requirements into structured evidence for an accept, reject, or escalate decision.

## First wedge

Version 0 targets AI-generated or AI-modified:

- theorem statements;
- definitions;
- public API additions;
- imports and dependency changes;
- repository patches with downstream consequences.

Proof generation remains external.

## Architecture

```text
Project Contract
      │
      ▼
Evidence Compiler ──► Evidence Packet
      │                    │
      ▼                    ▼
Review Router ──────► Expert Decision
      │
      ▼
Utility Ledger ─────► TPPR and learning data
```

The initial implementation is a modular Python application with:

- versioned JSON/YAML contracts;
- exact-environment subprocess adapters for Lean and Lake;
- deterministic evidence gates;
- a CLI-first workflow;
- an append-only SQLite utility ledger;
- provider interfaces for later semantic and retrieval systems.

## Repository layout

- `docs/ENGINEERING_SPEC.md` — complete standalone specification.
- `docs/` — focused subsystem and operating documents.
- `schemas/` — canonical JSON Schemas.
- `src/lpe/` — Python orchestration package.
- `examples/` — example project contract and candidate.
- `backlog/issues.csv` — issue-importable engineering plan.
- `openapi/openapi.yaml` — future service interface.
- `.github/workflows/` — CI.
- `scripts/` — bootstrap, checks, demo, and GitHub launch helpers (`github_launch.py`, `verify_clean_clone.py`).

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
make check
```

Run the example:

```bash
lpe contract validate examples/minimal-project
lpe evidence compile \
  --project examples/minimal-project \
  --candidate examples/candidates/R3-definition-change.json \
  --output .lpe/evidence/example.json
```

## Engineering rule

Every feature must answer the same question:

> Does it increase critical-path, semantically faithful, repository-accepted, sustained Lean project progress per expert hour?

Metrics such as generated declarations, compilation rate, proofs completed, review-model accuracy, and synthetic-data volume remain diagnostic only.

## Status

This repository is an engineering scaffold and specification for the first implementation. The deterministic contract, evidence, ledger, and TPPR core are executable. Lean semantic extraction, dependency impact analysis, downstream replacement testing, and model-assisted checks are defined behind interfaces and belong to the staged backlog.

**Partner shadow-pilot instrumentation:** engineering-ready via `docs/24_PARTNER_PILOT_READY.md` and `lpe pilot init-partner` — ready to *instrument*, not ready to *claim* §21 / causal utility. See also `docs/pilot_analysis_plan_template.md` (UNFROZEN until partner signs).

**Explicit non-claims:** see [`docs/28_NON_CLAIMS.md`](docs/28_NON_CLAIMS.md) (canonical). M6/M7 training is blocked until §21 (`lpe research status`).
