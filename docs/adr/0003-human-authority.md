# ADR 0003 — Human authority for high-risk semantics

## Status

Accepted.

## Decision

`R3` and `R4` artifacts require authorized human acceptance. Automatic
acceptance for `R3`/`R4` remains impossible.

Single-reviewer `lpe review record` refuses `R3`/`R4` ACCEPT.

Qualified human acceptance for `R3`/`R4` is allowed only through the
multi-attestation quorum path (`lpe review attest` + `lpe review accept-quorum`)
with distinct eligible reviewers per dimension.

## Rationale

Definitions and statements determine the mathematical object and project architecture. Current automated evidence is incomplete.

## Revisit

Only after prospective evidence shows calibrated, low-risk automatic decisions on held-out projects.
