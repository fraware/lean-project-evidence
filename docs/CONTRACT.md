# Project contract

## Location

`.lean-project-contract/`

## Files

- `project.yaml`
- `intent/project.md`
- `terminology.yaml`
- `obligations.yaml`
- `policies.yaml`
- `review.yaml`
- `tests/`

## Contract-authoring rule

Record only information that changes an acceptance decision or makes a downstream milestone measurable.

Every minute of contract maintenance belongs in the TPPR denominator.

## Change control

Contract changes are reviewed separately from candidate changes.

A candidate cannot modify its own acceptance contract in the same evidence run.

Contract version and content hash are recorded in every packet.

## Migration protocol

This section defines how project contracts evolve across `schema_version` releases.

### Version policy

- Contract files use semantic versions (`MAJOR.MINOR.PATCH`).
- Every contract file includes `schema_version`.
- The loader accepts only versions listed in `SUPPORTED_SCHEMA_VERSIONS` in `src/lpe/models.py`.
- Backward-compatible field additions are allowed in minor releases.
- Field removals or meaning changes require a major release.
- Old schemas remain exported under `schemas/` so historical packets stay interpretable.

### Migration steps

1. Export the new schemas with `python scripts/export_schemas.py` and commit the updated `schemas/*.schema.json` files.
2. Bump `SCHEMA_VERSION` and `SUPPORTED_SCHEMA_VERSIONS` together in `src/lpe/models.py`.
3. Provide a migration script or documented manual edit for each breaking change.
4. Update `examples/minimal-project/.lean-project-contract/` to the new version before release.
5. Re-run `pytest`, `lpe contract validate`, and schema export checks in CI.

### Non-mutating rule

Existing ledger events and evidence packets are never rewritten. Contract migrations affect only future loads and compiles.

### Rollback

If a migration fails validation, restore the prior contract directory from version control and keep the previous `schema_version` until the migration is corrected.

### Validation gates

A migrated contract must pass:

- split-file presence checks;
- supported `schema_version` on every YAML file (`lpe contract schema-check PATH`);
- obligation reference integrity and acyclic downstream graph;
- review authority coverage for all human-required risk classes;
- non-empty intent markdown;
- deterministic `contract_hash` reproducibility from canonical JSON.

### Dry-run and apply helpers

Use `lpe contract migrate-dry-run PATH [--to VERSION]` to plan a rewrite
**without mutating files**. Behavior:

- target not in `SUPPORTED_SCHEMA_VERSIONS` → `would_refuse` (exit 1);
- all files already at target → `no_op`;
- otherwise → `would_rewrite` listing filenames (`mutated: false`).

Use `lpe contract migrate PATH [--to VERSION] --write` to apply a versioned
rewrite after the target is listed in `SUPPORTED_SCHEMA_VERSIONS`. Default is
still dry-run (`--dry-run`). Field-level transformers register in
`MIGRATION_REWRITERS` in `src/lpe/contract/migration.py`; absent a custom
handler, only `schema_version` is rewritten.

Refuse-unknown remains fail-closed for both commands.
