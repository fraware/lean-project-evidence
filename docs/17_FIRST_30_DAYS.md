# First 30 days

## Week 1 — Foundation and ownership

- create and protect repository;
- assign owners;
- import milestones and issues;
- verify clean-clone setup;
- review all ADRs;
- freeze schema-version policy;
- select first active pilot repository.

Exit condition: Milestone 0 work has named owners and no architecture ambiguity.

## Week 2 — Contract and ledger hardening

- add negative contract fixtures;
- add cycle detection to obligation graph;
- define contract migration protocol;
- add ledger concurrency tests;
- add correction-event tests;
- formalize TPPR event semantics;
- author the first real Project Contract with the domain lead.

Exit condition: one real project contract validates and its overhead is measured.

## Week 3 — Deterministic evidence

- implement Git revision normalization;
- improve declaration classification;
- design sandbox backend;
- implement exact build logs and artifact storage;
- add hard-gate error taxonomy;
- render the first real evidence packet manually and through the CLI.

Exit condition: a real candidate produces a provenance-complete packet.

## Week 4 — Review operation

- implement reviewer authority validation;
- record review decisions and minutes;
- implement question-routing tests;
- create GitHub Check mock;
- conduct internal dry runs;
- freeze the shadow-pilot instrumentation.

Exit condition: one candidate completes the lifecycle from obligation registration through review and persistence placeholder.

## Month-one decision

Lean extraction tooling for **declared** fixture / helper projects already
exists in the scaffold (`lake exe lpe_extract`, committed `.lpe` JSON,
optional `lpe-lean:4.14` Docker). The month-one gate is about **pilot
readiness**, not whether extraction may begin in engineering:

Continue to a partner / field pilot only when:

- contract overhead is acceptable;
- deterministic evidence is useful to reviewers;
- execution security has an approved design;
- the ledger and TPPR semantics are stable;
- human protocol and §21 scientific clearance path are agreed (see
  `docs/24_PARTNER_PILOT_READY.md`).
