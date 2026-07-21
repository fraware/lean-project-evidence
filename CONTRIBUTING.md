# Contributing

Read [`docs/ENGINEERING_SPEC.md`](docs/ENGINEERING_SPEC.md) and the relevant ADR
under [`docs/adr/`](docs/adr/) before implementation.

## Development

```bash
python -m pip install -e ".[dev]"
make check
lpe doctor
```

Verify a clean-clone bootstrap locally:

```bash
python scripts/verify_clean_clone.py
```

## Pull requests

Each pull request must:

- state its path to TPPR;
- include tests for behavior changes;
- preserve evidence and provenance;
- document uncertainty where providers return `UNKNOWN`.

Use `.github/PULL_REQUEST_TEMPLATE.md`. Changes to schemas, execution, ledger,
or ADRs require CODEOWNERS approval (see `.github/CODEOWNERS`).

## Changes that require an ADR

- schema semantics;
- decision authority;
- ledger mutability;
- execution isolation;
- provider disclosure;
- North Star calculation;
- service decomposition.

## Commit style

Use imperative, scoped messages such as:

```text
feat(contract): validate obligation references
fix(ledger): reject broken hash chains
test(evidence): cover unknown provider outcomes
```
