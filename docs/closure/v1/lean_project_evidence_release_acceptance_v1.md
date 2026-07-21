# Lean Project Evidence Closure Release Checklist

## Release 0.2.0 — Evidence Integrity

- [ ] CLOSURE-001 through CLOSURE-017 closed.
- [ ] One immutable candidate snapshot is used by every finding.
- [ ] No semantic provider invokes host Lake directly.
- [ ] Generic extraction works without a target-defined `lpe_extract`.
- [ ] Base and candidate extractions exist and declaration diff is elaborator-backed.
- [ ] Evidence basis, coverage, provenance, and artifact references validate.
- [ ] Docker source mount is read-only and image digest is recorded.
- [ ] Schema 0.2.0 migration from 0.1.0 passes.
- [ ] Python/OS, Docker/Lean, package, typing, lint, security, and schema CI pass.
- [ ] README, package version, changelog, validation report, tree, and manifest agree.
- [ ] Explicit non-claims remain intact.

## Release 0.3.0 — Pilot Readiness

- [ ] CLOSURE-018 through CLOSURE-032 closed.
- [ ] Utility events use typed payloads.
- [ ] Lifecycle reducers reject invalid transitions.
- [ ] R3/R4 auto-accept remains impossible.
- [ ] R3/R4 qualified human acceptance works through quorum.
- [ ] Conflict, blinding, repair, and adjudication are enforced.
- [ ] TPPR v2 produces numerator and denominator audit tables.
- [ ] Pilot protocol freezes only when every required field is supplied.
- [ ] Condition assignment is reproducible from the frozen seed.
- [ ] Reviewer comprehension gates are executable.
- [ ] Data lock verifies protocol, ledger, seal, held-out set, and analysis image.
- [ ] §21 evaluator fails closed on missing gates.
- [ ] Live GitHub Check E2E passes in the dedicated test repository.
- [ ] Pilot readiness is described as authorization to instrument and execute, not evidence of causal utility.

## Release 0.4.0 — Pilot Completion

- [ ] CLOSURE-033 through CLOSURE-036 closed.
- [ ] 30–50 prospective episodes complete.
- [ ] Condition quotas met.
- [ ] R3/R4 coverage met.
- [ ] Reviewer comprehension completed.
- [ ] Automation and exact-environment reproduction measured.
- [ ] Instrumentation overhead measured in the field.
- [ ] Review, repair, specification, and integration time complete.
- [ ] Accepted obligations have integration and persistence outcomes.
- [ ] Ledger and off-host seal verify.
- [ ] Data lock is final.
- [ ] Analysis reproduces in the recorded container.
- [ ] §21 gate report is final.
- [ ] Report distinguishes descriptive, causal, and unsupported statements.
- [ ] M6/M7 authorization matches the gate report.

## Production Readiness

- [ ] Three active repositories validated.
- [ ] Two mathematical domains validated.
- [ ] Lean compatibility matrix published.
- [ ] External security review closed.
- [ ] External methodology review closed.
- [ ] Incident response and operational ownership documented.
- [ ] Stable migration and deprecation policy published.
- [ ] No open P0 or P1 issue.
