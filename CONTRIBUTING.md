# Contributing

Read `docs/ENGINEERING_SPEC.md` and the relevant ADR before implementation.

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

- link one backlog issue from `backlog/issues.csv`;
- state its path to TPPR;
- include tests for behavior changes;
- preserve evidence and provenance;
- document uncertainty where providers return `UNKNOWN`.

Use `.github/PULL_REQUEST_TEMPLATE.md` and follow `docs/13_DEFINITION_OF_DONE.md`.

## Code ownership

Update `.github/CODEOWNERS` placeholders before the first engineering merge (`MAINTAINERS.md`). Changes to schemas, execution, ledger, or ADRs require CODEOWNERS approval.

## Repository launch

For initial GitHub setup (labels, milestones, backlog import, branch protection), follow:

- `docs/16_REPOSITORY_LAUNCH.md`
- `docs/20_LAUNCH_CHECKLIST.md`
- `scripts/github_launch.py` (dry-run by default; pass `--apply` when `gh` is authenticated)

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
