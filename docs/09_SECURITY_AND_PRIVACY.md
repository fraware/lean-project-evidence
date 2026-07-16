# Security and privacy

## Threat model

Generated patches and target repositories may execute arbitrary build code.

Project contracts may contain confidential mathematics.

External model providers may retain submitted content.

## Mandatory controls

- isolated worktree or container (`lpe evidence compile --worktree` by default);
- Docker sandbox preferred for builds; host subprocess requires `--insecure-host-exec` and `network_policy: allow`;
- Prefer Lean-capable `LPE_DOCKER_IMAGE=lpe-lean:4.14` (see `docker/lpe-lean/`) for isolation PASS that also typechecks; default `ubuntu:22.04` has no Lean;
- explicit command allowlist (`lake` / `lean` / `elan` only);
- environment-variable allowlist plus secret-name denylist (`*_TOKEN`, `*_SECRET`, `*_PASSWORD`, `GITHUB_*`, `AWS_*`, `CI`);
- no CI secrets in build environment;
- network disabled by default (`network_policy: deny` → Docker `--network=none`);
- time and output limits;
- provider disclosure policy;
- structured redaction of build logs before evidence embedding;
- content hashing;
- immutable logs;
- dependency vulnerability scanning;
- protected release workflow;
- review authority from `review.yaml` only (decision JSON roles are not trusted).
- Lean extraction defaults to `regex-stub`; toolchain completeness requires Lean/Lake JSON ingest.
- `hard_gate_passed` is false when hard-relevant checks are UNKNOWN (not axiom-safe by implication).

## Ledger trust boundary (AUDIT-017)

The utility ledger is **append-only SQLite on the local filesystem**. SQLite triggers block UPDATE/DELETE on `events`, and each row carries a per-artifact hash chain (`previous_hash` / `event_hash`). `lpe ledger verify` and export JSONL verification recompute that chain.

This is **not** a WORM device or tamper-evident root of trust: anyone with filesystem access can replace the database file, drop triggers, or rewrite bytes outside the application. Treat exports as audit artifacts; protect the host and backup policy accordingly. Retention/compaction prototype: `lpe ledger archive` (verify → verified JSONL; live chain untouched) then optional `lpe ledger init` for a fresh working set — see [06_UTILITY_LEDGER_SPEC.md](06_UTILITY_LEDGER_SPEC.md) and [25_LEDGER_THREAT_MODEL.md](25_LEDGER_THREAT_MODEL.md).

## Supply-chain notes (AUDIT-024)

- GitHub Actions in `.github/workflows/ci.yml` are pinned to **full commit SHAs** with version comments for Dependabot.
- `.github/dependabot.yml` opens weekly PRs for `pip` and `github-actions`. When Dependabot bumps an Action, review the new SHA against the upstream release tag before merge (SHA drift = expected Dependabot churn, not silent floating majors).
- `pip-audit` runs in CI; treat new advisories as merge blockers until waived with rationale.

## Incident rule

Any evidence packet produced after a sandbox, provenance, or ledger-integrity failure is invalid and must be superseded.
