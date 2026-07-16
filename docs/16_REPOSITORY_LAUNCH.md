# Repository launch procedure

## 1. Create the GitHub repository

Recommended metadata:

- Name: `lean-project-evidence`
- Description: `Project-grounded evidence and review infrastructure for AI-assisted Lean development`
- Topics: `lean4`, `formal-methods`, `theorem-proving`, `ai-for-math`, `software-assurance`
- License: Apache-2.0
- Default branch: `main`

## 2. Push the scaffold

Use the commands in `TEAM_INSTRUCTIONS.md`.

## 3. Configure labels

Canonical names: `backlog/github_labels.txt` and `docs/19_GITHUB_LABELS.md`.

```bash
python scripts/github_launch.py labels          # dry-run
python scripts/github_launch.py labels --apply  # requires authenticated gh
```

## 4. Create milestones

Canonical titles: `backlog/milestones.txt`.

```bash
python scripts/github_launch.py milestones --apply
```

## 5. Import backlog

Use `backlog/issues.csv` as the canonical issue list.

```bash
python scripts/github_launch.py import-issues          # dry-run
python scripts/github_launch.py import-issues --apply
```

Dependencies are preserved in each issue body when GitHub cannot represent them as native links.

## 5a. Verify clean clone

Before tagging or enabling branch protection:

```bash
python scripts/verify_clean_clone.py
```

This runs `pip install -e ".[dev]"`, `pytest`, and `lpe doctor`.

## 5b. Launch checklist

Track remaining launch steps in `docs/20_LAUNCH_CHECKLIST.md`.

## 6. Configure protections

Require:

- passing CI;
- signed or verified commits where organizational policy supports it;
- approval from CODEOWNERS for schemas, execution, ledger, and ADRs;
- linear history;
- resolved conversations.

## 7. Configure environments

Create a protected `release` environment.

No provider API secret should be available to pull-request builds from forks.

The exact Lean execution job should receive no repository or cloud credentials.

## 8. First release

Tag `v0.1.0` only after:

- clean-clone bootstrap succeeds;
- examples validate;
- tests pass;
- package builds;
- security boundaries are documented;
- first pilot repository has been selected.
