```text
                              _     ____  _____
                             | |   |  _ \| ____|
                             | |   | |_) |  _|
                             | |___|  __/| |___
                             |_____|_|   |_____|

                            LEAN PROJECT EVIDENCE
                Project-grounded evidence for Lean development
```

<p align="center">
  <a href="https://github.com/fraware/lean-project-evidence/actions/workflows/ci.yml"><img src="https://github.com/fraware/lean-project-evidence/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License: Apache 2.0" /></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-%3E%3D3.12-blue.svg" alt="Python >= 3.12" /></a>
</p>

**Lean Project Evidence** (`lean-project-evidence`, CLI: `lpe`) turns project intent and repository state into structured evidence for accept, reject, or escalate decisions on Lean candidates.

Kernel checks prove a term matches a proposition. They do not prove the proposition matches the mathematics you meant, fits the abstractions you chose, or advances the milestone you care about. LPE closes that gap with contracts, evidence packets, and an append-only utility ledger.

---

## Contents

- [Why it matters](#why-it-matters)
- [Who it is for](#who-it-is-for)
- [Quickstart](#quickstart)
- [Core concepts](#core-concepts)
- [CLI highlights](#cli-highlights)
- [Honesty bounds](#honesty-bounds)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Why it matters

The North Star is **TPPR**: sustained critical-path progress per expert hour.

In plain language: of the obligations that actually move the project forward, how many are accepted and stay accepted — relative to the expert time spent specifying, reviewing, repairing, and integrating?

\[
\text{TPPR}
=
\frac{\text{weighted critical-path obligations accepted and sustained}}
{\text{expert specification, review, repair, and integration hours}}
\]

Compilation rates, generated declarations, and synthetic-data volume are diagnostics. They are not the goal.

---

## Who it is for

| Audience | Job |
| --- | --- |
| Formalization leads | Decide whether an AI-assisted statement, definition, or patch belongs in the project |
| Repository maintainers | Bind review to exact Lean/Lake state, architecture, and downstream risk |
| Pilot partners | Instrument review workflows without claiming causal utility prematurely |
| Contributors | Extend contracts, evidence gates, CLI surfaces, and tests |

Version 0 focuses on AI-generated or AI-modified theorem statements, definitions, public APIs, imports, and repository patches. Proof generation stays external.

---

## Quickstart

Requires **Python 3.12+**.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
make check
```

Validate the example contract and compile evidence:

```bash
lpe contract validate examples/minimal-project

lpe evidence compile \
  --project examples/minimal-project \
  --candidate examples/candidates/R3-definition-change.json \
  --output .lpe/evidence/example.json
```

Environment health and research-gate honesty:

```bash
lpe doctor
lpe research status
```

---

## Core concepts

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

| Concept | Role |
| --- | --- |
| **Project contract** | Versioned intent, obligations, policies, and review rules for a Lean repo |
| **Evidence packet** | Deterministic findings from exact-environment Lean/Lake runs and gates |
| **Review router** | Selects the smallest acceptance-controlling questions; records decisions |
| **Utility ledger** | Append-only SQLite history of lifecycle outcomes for TPPR |

Design constraints: local-first, repository-native, exact-toolchain, model-independent, human-controlled for high-risk semantics, inspectable evidence. No opaque quality scalar in version 0.

Every feature should answer: *does this increase critical-path, semantically faithful, repository-accepted, sustained Lean progress per expert hour?*

---

## CLI highlights

| Command | Purpose |
| --- | --- |
| `lpe contract validate` | Load and validate a project contract |
| `lpe evidence compile` | Build an evidence packet for a candidate |
| `lpe review …` | Record decisions; high-risk paths require human attestation |
| `lpe ledger verify` / `archive` / `seal` | Integrity checks and export for the utility ledger |
| `lpe doctor` | Local toolchain and honesty-surface checks |
| `lpe pilot …` | Partner instrumentation (not scientific clearance) |

Human-readable output by default; `--json` for machines. Nonzero exit on invalid input or hard execution failure.

Full reference: [`docs/CLI.md`](docs/CLI.md).

---

## Honesty bounds

LPE is careful about what it claims. In short:

- Instrumentation and dry-runs do **not** prove causal improvement in TPPR.
- High-risk (R3/R4) acceptance stays under human authority; there is no production auto-ACCEPT.
- Fixture and project extractors are **not** Mathlib-scale elaborator-complete kernel truth.
- Learned routing and synthesis training remain blocked until scientific clearance criteria are met.

Canonical list: [`docs/NON_CLAIMS.md`](docs/NON_CLAIMS.md).

Package version **0.2.0** is an engineering release tag, not a production-readiness or scientific-clearance claim.

---

## Documentation

| Doc | Purpose |
| --- | --- |
| [`docs/ENGINEERING_SPEC.md`](docs/ENGINEERING_SPEC.md) | Full product engineering specification |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Modules and deployment model |
| [`docs/CONTRACT.md`](docs/CONTRACT.md) | Project contract and schema migration |
| [`docs/EVIDENCE_AND_REVIEW.md`](docs/EVIDENCE_AND_REVIEW.md) | Evidence compiler and review router |
| [`docs/CLI.md`](docs/CLI.md) | CLI conventions and workflows |
| [`docs/LEDGER_AND_TPPR.md`](docs/LEDGER_AND_TPPR.md) | Utility ledger, seals, TPPR |
| [`docs/SECURITY_AND_PRIVACY.md`](docs/SECURITY_AND_PRIVACY.md) | Threat model and controls |
| [`docs/NON_CLAIMS.md`](docs/NON_CLAIMS.md) | Anti-oversell list |
| [`docs/PILOT.md`](docs/PILOT.md) | Partner instrumentation protocol |
| [`docs/adr/`](docs/adr/) | Architecture decision records |

Repository layout: `docs/`, `schemas/`, `src/lpe/`, `examples/`, `openapi/`, `scripts/`, `.github/workflows/`.

---

## Contributing

Contributions are welcome. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md).

**Good first paths**

- Improve examples under `examples/`
- Add unit tests around contracts, evidence gates, or CLI surfaces
- Clarify docs that already match shipped behavior
- Fix small schema or validation edge cases with tests

**Local loop**

```bash
python -m pip install -e ".[dev]"
make check
lpe doctor
pytest -q
```

Pull requests should state a path to TPPR, include tests for behavior changes, preserve evidence provenance, and document uncertainty where providers return `UNKNOWN`. Schema, execution, ledger, and ADR changes need CODEOWNERS review.

Security reports: [`SECURITY.md`](SECURITY.md).

---

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
