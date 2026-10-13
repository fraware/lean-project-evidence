# leanVM #533 `fold12` experimental attempt

Exact parent: `leanEthereum/leanVM@4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.
Only the admitted `fold12` proof body in `LeanxmssProofs/Encoding.lean`
is replaced. The `fold6` and `encode_spec` admissions deliberately remain.

The attempt normalizes the low-12-bit mask into remainder, translates shifts
into division by powers of two, normalizes the six-position base-4096 polynomial,
and asks Lean's Presburger solver to establish the bounded sum identity.

**Status: experimental until the source-pinned GitHub Actions build succeeds
and `#print axioms` for `fold12` excludes `sorryAx`.** No local Python spot
check, successful source text comparison, or partial compilation counts as
proof. No upstream PR is created by the workflow.
