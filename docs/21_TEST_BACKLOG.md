# Remaining integration / security / performance test backlog

Short backlog of tests **not** covered by the current suite (**480 tests** as of 2026-07-16 redaction/archive/cone cut; prior Week 2 baseline was 328). Actionable schedule, capability matrix, and exit criteria live in **[22_COMPREHENSIVE_TEST_PLAN.md](22_COMPREHENSIVE_TEST_PLAN.md)**. Progress: **[23_TEST_EXECUTION_LOG.md](23_TEST_EXECUTION_LOG.md)**.

## Integration

- [x] Contract/candidate CLI smoke + compile→review→ledger→TPPR (skip-build) — Week 1 `tests/integration/`
- [x] Ledger export verify + tamper detection (integration) — Week 1
- [x] Git-candidate E2E from real commits + invalid rev — Week 2 `test_git_candidate.py`
- [x] Docker evidence build (`@pytest.mark.docker`) isolation PASS / allowlist / skip honesty — Week 2
- [x] Lean toolchain JSON ingest + regex honesty (no Lake required) — Week 2 `test_evidence_lean_repo.py`
- [x] Worktree dirty-tree safety + cleanup-on-error — Week 2 `test_worktree_isolation.py`
- [x] End-to-end `lpe evidence compile` against fixture Lean repo in Docker when `lpe-lean:4.14` is present (`test_e2e_docker_lean_image_isolation_and_toolchain`); Mathlib-scale / cache policy still open.
- [ ] GitHub Check submission to a throwaway repo (API auth, required-check fail-closed ESCALATE).
- [x] Multi-writer ledger under process crash / power-loss (SQLite WAL durability) — `test_ledger_wal_durability.py` (mid-txn rollback + multiprocess).
- [x] Contract migration dry-run from `0.1.0` → next minor with `lpe contract migrate-dry-run` / `schema-check` gate.
- [x] Pilot instrumentation → optional ledger snapshot → TPPR report on a frozen fixture corpus.

## Security

- [x] Adversarial `build_command` and env denylist / redaction corpus smoke — Week 1 `tests/security/`
- [x] Path traversal REG suite — Week 1
- [x] Fuzz / property tests for `assert_safe_repo_relative` (Unicode, NTFS alternate streams, symlink escapes) — `test_path_adversarial_fuzz.py`.
- [x] Secret-redaction corpus expansion (JWT, PEM/OpenSSH, Slack, GitLab, npm, Stripe, OpenAI/Anthropic, HF) + Lean-log non-over-redact — `test_redaction_corpus.py`.
- [x] Supply-chain: Dependabot for pinned Actions SHAs + drift note (`docs/09`, `SECURITY.md`); periodic `pip-audit` in CI. Ongoing: review Dependabot Action PRs.
- [x] CODEOWNERS fail-closed CI (placeholders removed; `@fraware`; no `LPE_CODEOWNERS_PLACEHOLDERS_OK` in CI).
- [x] Ledger threat model tabletop: compromised host FS vs export verify — `docs/25_LEDGER_THREAT_MODEL.md`.

## Performance / longevity

- [x] Ledger append latency budget under N=10k / 100k events; export/verify wall time. — Week 3/4 (100k `@slow`).
- [x] Evidence compile memory/time with large impact cones (synthetic graphs) — `test_impact_cone_scale.py` soft budgets.
- [x] Retention/compaction policy prototype (export → verify → archive; never rewrite live chain) — `lpe ledger archive` + `docs/06`.
- [x] Schema longevity: load historical packets from `schemas/` after a minor bump. — Week 4
- [x] Cost model: Docker cold start vs host insecure path; combined vs sequential starts documented (`docs/benchmarks/week3_baseline.md`).

## Explicit non-goals for this backlog doc

- Do not treat month-one gate or `fixture_harness_ok` as production or §21 clearance.
- Do not add training loops for M6/M7 until science gates are explicitly opened.
