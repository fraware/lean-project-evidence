# Repository launch checklist

Use this checklist with `docs/16_REPOSITORY_LAUNCH.md` and `TEAM_INSTRUCTIONS.md` when bringing the repository online.

## Pre-push

- [ ] **FAIL if skipped:** Confirm `.github/CODEOWNERS` has real `@user` / `@org/team` handles (no `REPLACE_WITH_*`). Run `python scripts/check_codeowners_placeholders.py` (must exit 0; CI is fail-closed).
- [ ] Confirm Apache-2.0 license and repository metadata
- [ ] Run clean-clone verification locally: `python scripts/verify_clean_clone.py`

## GitHub repository

- [ ] Create `lean-project-evidence` (public unless partner constraints require private)
- [ ] Push scaffold without re-initializing README, license, or `.gitignore`
- [ ] Enable secret scanning and dependency alerts

## Labels and milestones

- [ ] Create labels from `backlog/github_labels.txt` (`docs/19_GITHUB_LABELS.md`)
- [ ] Create milestones from `backlog/milestones.txt`

```bash
python scripts/github_launch.py labels --apply
python scripts/github_launch.py milestones --apply
```

## Backlog import

- [ ] Import `backlog/issues.csv` preserving `depends_on` in issue bodies

```bash
python scripts/github_launch.py import-issues --apply
```

Dry-run first (default):

```bash
python scripts/github_launch.py import-issues
```

## Branch protection (`main`)

- [ ] Require pull requests before merge
- [ ] Require the `python` CI job
- [ ] Require CODEOWNERS review for protected paths
- [ ] Require conversation resolution
- [ ] Dismiss stale approvals on new commits
- [ ] Block force pushes and branch deletion
- [ ] Require linear history (if organizational policy allows)

## Environments

- [ ] Create protected `release` environment
- [ ] Confirm fork pull requests receive no provider or cloud secrets

## Week 1 exit (EPIC-001)

- [ ] CI green on clean clone (`pip install -e ".[dev]"`, `pytest`, `lpe doctor`)
- [ ] Issues and milestones live on GitHub
- [ ] Named owners recorded in `MAINTAINERS.md` and `CODEOWNERS`
- [ ] Schema-version policy frozen (`docs/ENGINEERING_SPEC.md` section 19)
- [ ] First pilot Lean repository nominated (selection only; no extraction yet)

## Milestone tracking (M0–M7)

| Milestone | Title | Launch artifact |
|-----------|-------|-----------------|
| M0 | Foundation | Issues ISSUE-002–006 |
| M1 | Deterministic Evidence | EPIC-007 and ISSUE-008–016 |
| M2 | Review Operation | EPIC-017 and ISSUE-018–021 |
| M3 | Lean-Aware Evidence | EPIC-022 and ISSUE-023–027 |
| M4 | Semantic Evidence | EPIC-028 and ISSUE-029–033 |
| M5 | Shadow Pilot | EPIC-034 and ISSUE-035–038 |
| M6 | Learned Routing | EPIC-039 |
| M7 | Project-Targeted Synthesis | EPIC-040 |
