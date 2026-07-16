# Month-one gate

This checklist implements the hard decision from [17_FIRST_30_DAYS.md](17_FIRST_30_DAYS.md). Continue to Lean extraction (M3 / EPIC-022) only when **all** criteria pass.

**Honesty note:** Clearing the month-one gate means automated scaffold criteria passed. It does **not** mean production-ready, elaborator-complete Lean evidence, or pilot authorization.

## Pass/fail criteria

| ID | Criterion | Pass condition |
| --- | --- | --- |
| `tests_pass` | Test suite green | `pytest` exits 0 on clean clone |
| `schema_stable` | Schema export present | All versioned JSON schemas under `schemas/` |
| `migration_protocol` | Contract migration documented | `docs/18_CONTRACT_MIGRATION.md` exists |
| `sandbox_design` | Execution isolation design | Importable `sandbox` + `allowlist` modules with network-none markers (not file existence alone) |
| `ledger_tppr_stable` | Ledger + TPPR semantics | Dedicated unit tests for ledger hash chain and TPPR matrix |
| `review_loop` | Human authority loop | Review decision recording under `src/lpe/review/` |
| `example_contract` | Reference contract | `examples/minimal-project` validates via real `load_contract` / `lpe contract validate` |

## Domain-lead qualitative gates (manual)

These are not automated; record the outcome in your pilot notes:

1. **Contract overhead acceptable** — loading and validating the project contract adds negligible friction for the domain lead.
2. **Deterministic packets useful** — dry-run reviewers find evidence packets actionable for R1–R3 decisions.
3. **Sandbox design approved** — security/design review accepts Docker `--network=none` with scrubbed environment as the default isolation backend.

## Evaluate from repository state

```bash
lpe gate month-one
```

Exit code 0 means all automated criteria pass. Exit code 1 lists failing criteria as JSON.

## Failure response

If any criterion fails:

- Do **not** start EPIC-022 (Lean extraction) or later ML milestones.
- Narrow the protocol or fix M0–M2 until the gate clears.
- Re-run `lpe gate month-one` after fixes.
