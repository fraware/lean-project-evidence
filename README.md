# LPE.

**L E A N &nbsp; P R O J E C T &nbsp; E V I D E N C E**

*Project-grounded evidence for Lean development.*

&nbsp;

**Lean Project Evidence** (`lean-project-evidence`, CLI: `lpe`) turns project intent and repository state into structured evidence for accepting, rejecting, or escalating Lean candidates.

A kernel check establishes that a term has a proposition as its type. It does not establish that the proposition captures the intended mathematics, respects the chosen abstractions, or advances a project's critical path. LPE records evidence relevant to those judgments. High-risk semantic decisions remain under human authority.

<sub>[SOURCE](https://github.com/fraware/lean-project-evidence) &nbsp;·&nbsp; [CI](https://github.com/fraware/lean-project-evidence/actions/workflows/ci.yml) &nbsp;·&nbsp; [APACHE 2.0](LICENSE) &nbsp;·&nbsp; [PYTHON ≥3.12](pyproject.toml) &nbsp;·&nbsp; [CLI REFERENCE](docs/CLI.md)</sub>

---

<details>
<summary><strong>Index</strong> &nbsp;—&nbsp; open the contents</summary>

&nbsp;

|  |  |
| :-- | :-- |
| 01 &nbsp; [Why it matters](#why-it-matters) | 06 &nbsp; [Honesty bounds](#honesty-bounds) |
| 02 &nbsp; [Who it is for](#who-it-is-for) | 07 &nbsp; [Documentation](#documentation) |
| 03 &nbsp; [Quickstart](#quickstart) | 08 &nbsp; [Contributing](#contributing) |
| 04 &nbsp; [Core concepts](#core-concepts) | 09 &nbsp; [License](#license) |
| 05 &nbsp; [CLI highlights](#cli-highlights) | |

</details>

&nbsp;

<sub>01 &nbsp;/&nbsp; 09</sub>


## Why it matters

**TPPR** measures sustained critical-path progress per expert hour.

$$
\mathrm{TPPR} = \frac{P_{\mathrm{sustained}}}{H_{\mathrm{expert}}}
$$

**Progress** · The weighted critical-path obligations accepted and sustained.  
**Time** · The expert hours spent on specification, review, repair, and integration.

The measure asks a single question: how much of the work that advances the formalization stays accepted, relative to the expert effort invested?

Compilation rates, generated declarations, and synthetic-data volume are diagnostics. They are not the objective.

---

<sub>02 &nbsp;/&nbsp; 09</sub>

## Who it is for

| Reader | Decision or task |
| :-- | :-- |
| **Formalization leads** | Decide whether an AI-assisted statement, definition, or patch belongs in the project |
| **Repository maintainers** | Bind review to exact Lean/Lake state, architecture, and downstream risk |
| **Pilot partners** | Instrument review workflows without prematurely claiming causal utility |
| **Contributors** | Extend contracts, evidence gates, CLI surfaces, and tests |

Version 0 focuses on AI-generated or AI-modified theorem statements, definitions, public APIs, imports, and repository patches. Proof generation stays external.

&nbsp;

<sub>03 &nbsp;/&nbsp; 09</sub>

## Quickstart

**Requirements** &nbsp; Python 3.12+ and the project's development dependencies.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
make check
```

**I. Validate the project contract.**

```bash
lpe contract validate examples/minimal-project
```

**II. Compile evidence for a candidate.**

```bash
lpe evidence compile \
  --project examples/minimal-project \
  --candidate examples/candidates/R3-definition-change.json \
  --output .lpe/evidence/example.json
```

**III. Inspect the environment and research gates.**

```bash
lpe doctor
lpe research status
```

&nbsp;

<sub>04 &nbsp;/&nbsp; 09</sub>

## Core concepts

LPE proceeds through four records. Each record has a distinct role; none substitutes for an expert's judgment about mathematical intent.

|  | Record | Function |
| :-- | :-- | :-- |
| `I` | **Project contract** | Versioned intent, obligations, policies, and review rules for a Lean repository |
| `II` | **Evidence packet** | Deterministic findings from exact-environment Lean/Lake runs and gates |
| `III` | **Review decision** | Acceptance-controlling questions and human attestation for high-risk paths |
| `IV` | **Utility ledger** | Append-only SQLite lifecycle history for TPPR and subsequent analysis |

The evidence compiler interprets the contract and candidate against the repository's exact toolchain and state. The review router identifies the smallest set of acceptance-controlling questions. The ledger retains the resulting lifecycle history.

**Design constraints** &nbsp; Local-first. Repository-native. Exact-toolchain. Model-independent. Inspectable evidence. Human-controlled high-risk semantics. No opaque quality scalar in version 0.

Every feature faces one test: *does it increase critical-path, semantically faithful, repository-accepted, sustained Lean progress per expert hour?*

&nbsp;

<sub>05 &nbsp;/&nbsp; 09</sub>

## CLI highlights

| Command | Function |
| :-- | :-- |
| `lpe contract validate` | Load and validate a project contract |
| `lpe evidence compile` | Build an evidence packet for a candidate |
| `lpe review ...` | Record decisions; high-risk paths require human attestation |
| `lpe ledger verify` / `archive` / `seal` | Verify integrity and export ledger records |
| `lpe doctor` | Check local toolchain and honesty surfaces |
| `lpe pilot ...` | Instrument partner workflows, without implying scientific clearance |

Human-readable output by default; `--json` for machine consumers. Invalid input and hard execution failures produce nonzero exit codes.

Full reference: [`docs/CLI.md`](docs/CLI.md).

&nbsp;

<sub>06 &nbsp;/&nbsp; 09</sub>

## Honesty bounds

An evidence instrument is only useful to the extent that its claims stay within the evidence.

- Instrumentation and dry-runs **do not establish causal improvement** in TPPR.
- High-risk (`R3`/`R4`) acceptance remains under **human authority**; there is no production auto-`ACCEPT`.
- Fixture and project extractors are **not Mathlib-scale elaborator-complete kernel truth**.
- Learned routing and synthesis training remain blocked pending scientific clearance.

The authoritative list is [`docs/NON_CLAIMS.md`](docs/NON_CLAIMS.md).

**Version 0.2.0** denotes an engineering release. It is not a production-readiness or scientific-clearance designation.

&nbsp;

<sub>07 &nbsp;/&nbsp; 09</sub>

## Documentation

| Document | Subject |
| :-- | :-- |
| [`ENGINEERING_SPEC.md`](docs/ENGINEERING_SPEC.md) | Product engineering specification |
| [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Modules and deployment model |
| [`CONTRACT.md`](docs/CONTRACT.md) | Project contract and schema migration |
| [`EVIDENCE_AND_REVIEW.md`](docs/EVIDENCE_AND_REVIEW.md) | Evidence compiler and review router |
| [`CLI.md`](docs/CLI.md) | CLI conventions and workflows |
| [`LEDGER_AND_TPPR.md`](docs/LEDGER_AND_TPPR.md) | Utility ledger, seals, and TPPR |
| [`SECURITY_AND_PRIVACY.md`](docs/SECURITY_AND_PRIVACY.md) | Threat model and controls |
| [`NON_CLAIMS.md`](docs/NON_CLAIMS.md) | Claims excluded by the current evidence |
| [`PILOT.md`](docs/PILOT.md) | Partner instrumentation protocol |
| [`adr/`](docs/adr/) | Architecture decision records |

**Repository anatomy** &nbsp; `docs/` · `schemas/` · `src/lpe/` · `examples/` · `openapi/` · `scripts/` · `.github/workflows/`

&nbsp;

<sub>08 &nbsp;/&nbsp; 09</sub>

## Contributing

Contributions are welcome. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md).

Promising entry points include improving examples under `examples/`, extending unit tests around contracts and evidence gates, clarifying documentation that reflects shipped behavior, and correcting schema or validation edge cases with regression tests.

**Local verification**

```bash
python -m pip install -e ".[dev]"
make check
lpe doctor
pytest -q
```

Pull requests should explain their connection to TPPR, include tests for behavior changes, preserve evidence provenance, and document uncertainty where providers return `UNKNOWN`. Schema, execution, ledger, and ADR changes need CODEOWNERS review.

Security reports: [`SECURITY.md`](SECURITY.md).

&nbsp;

<sub>09 &nbsp;/&nbsp; 09</sub>

## License

Apache License 2.0. See [`LICENSE`](LICENSE).

