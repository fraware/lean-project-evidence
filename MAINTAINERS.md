# Maintainers and code ownership

Replace placeholder GitHub handles in `.github/CODEOWNERS` with real usernames or organization teams before the first engineering pull request merges.

## BLOCKED — merge FAIL until placeholders removed

Until every `@REPLACE_WITH_*` handle in `.github/CODEOWNERS` is replaced:

- **Do not merge** engineering PRs that touch protected paths (schemas, execution, ledger, ADRs, workflows).
- CI runs `python scripts/check_codeowners_placeholders.py` — **fails by default** when placeholders remain.
- Local warning-only mode: `LPE_CODEOWNERS_PLACEHOLDERS_OK=1 python scripts/check_codeowners_placeholders.py`
- Pre-push checklist: `docs/20_LAUNCH_CHECKLIST.md` (first item).

## Role assignments

| Role | Scope | GitHub handle (placeholder) |
|------|-------|----------------------------|
| Research lead | North Star, ADRs, pilot selection | `@REPLACE_WITH_RESEARCH_LEAD` |
| Schema owner | JSON Schemas, domain models, contract types | `@REPLACE_WITH_SCHEMA_OWNER` |
| Lean systems owner | Git adapters, Lean/Lake execution, extraction | `@REPLACE_WITH_LEAN_SYSTEMS_OWNER` |
| Data owner | Append-only ledger, TPPR, utility metrics | `@REPLACE_WITH_DATA_OWNER` |
| Security owner | Sandboxing, execution isolation, CI secrets policy | `@REPLACE_WITH_SECURITY_OWNER` |

## Review policy

Per `TEAM_INSTRUCTIONS.md`:

- one approval for most changes;
- two approvals (including CODEOWNERS) for changes touching schemas, execution, ledger, or ADRs.

## Pilot repository

Nominate the first active pilot Lean repository during Week 1 (`docs/17_FIRST_30_DAYS.md`). Record the selection in the pilot issue body when opening ISSUE-035; do not begin Lean extraction until Milestone 0 passes and the month-one gate clears.
