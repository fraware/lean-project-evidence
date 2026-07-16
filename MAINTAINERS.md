# Maintainers and code ownership

GitHub handles in `.github/CODEOWNERS` are assigned to the repository owner.
CI runs `python scripts/check_codeowners_placeholders.py` and **fails** if any
`@REPLACE_WITH_*` placeholder remains (no escape env in default CI).

## Role assignments

| Role | Scope | GitHub handle |
|------|-------|----------------|
| Research lead | North Star, ADRs, pilot selection | `@fraware` |
| Schema owner | JSON Schemas, domain models, contract types | `@fraware` |
| Lean systems owner | Git adapters, Lean/Lake execution, extraction | `@fraware` |
| Data owner | Append-only ledger, TPPR, utility metrics | `@fraware` |
| Security owner | Sandboxing, execution isolation, CI secrets policy | `@fraware` |

Single-owner scaffold: all roles map to `@fraware` until an org governance
project splits them. Replace with `@org/team` handles when that happens.

## Review policy

Per `TEAM_INSTRUCTIONS.md`:

- one approval for most changes;
- two approvals (including CODEOWNERS) for changes touching schemas, execution, ledger, or ADRs when multiple maintainers exist.

## Pilot repository

Nominate the first active pilot Lean repository when reopening the partner
workflow (`docs/17_FIRST_30_DAYS.md`, `docs/24_PARTNER_PILOT_READY.md`).
Lean extraction tooling already exists for declared fixture projects; the
month-one / partner gate is about *pilot readiness* and human protocol, not
whether extraction may begin in the engineering scaffold.
