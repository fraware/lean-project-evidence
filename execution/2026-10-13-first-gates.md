# XMSS independent acceptance run: October 13, 2026

This branch validates the **already CI-green** six-file candidate from
`fraware/lean-project-evidence@79b27bba5154298de32681dcadcc8ec8628de54b`
against upstream `leanEthereum/leanSpec` PR #1204 head
`e8f9c29da3c2b725b988ed85dac8dce3d89d0012`.

The handoff script is copied unchanged from
`research/ethereum-xmss-durability-handoff-20261013`
(blob SHA `af38be25f97a1f11813db42e5817b850e9289202`).

## Independent gates

1. `cleanroom-interop`: in a clean macOS environment, run the handoff
   script as-is, check six Git blob hashes, generate the diff, then run
   the upstream multi-node interop test with Python 3.14 and `LEAN_ENV=test`.
   The **standard** 2,971-test run excluded `tests/interop` via pytest's
   `--ignore` option. A separate interop result is necessary and does not
   prove multi-writer durable-key safety.
2. `leanvm-proof-baseline`: pin leanVM #533 exact source and Lean 4.31.0,
   confirm exactly the identified `fold6`, `fold12`, `encode_spec` admits,
   compile the existing Lean project with cached Mathlib, and print the
   theorem axiom closure. This job EXPECTS `sorryAx`: success means accurate
   diagnosis, not a completed correspondence proof.

**Important:** the two jobs are independent. Neither passes the other merely
because the original standard suite was green. This branch creates no
upstream PR or comment and does not alter signing or proof source files.
