# Engineering checkpoint — XMSS adoption and fixed-width proof frontier

**Recorded:** October 13, 2026, local time (UTC workflows may be dated October 14).  
**Project mission:** independently checkable evidence across real implementation
boundaries. Keep upstream utility and semantic correspondence primary.

## Finished and directly reproducible

### leanSpec XMSS signer

**Combined eight-file candidate** at pinned parent
`leanEthereum/leanSpec@e8f9c29da3c2b725b988ed85dac8dce3d89d0012`:

- [Native test/lint/type CI #38484185368](https://github.com/fraware/lean-project-evidence/actions/runs/38484185368): **success**, 110 focused, 2,976 full-suite tests, 91.80% measured coverage.
- [Independent macOS three-node interop #38485973305](https://github.com/fraware/lean-project-evidence/actions/runs/38485973305): **success**, one scenario, four declared phases, 36.51 seconds.
- [Standalone local-key-identity check #38485502716](https://github.com/fraware/lean-project-evidence/actions/runs/38485502716): **success**, 34 native registry tests plus Ruff, type checking, exact source hashes. Two-file patch separately staged.
- [Prior initial six-file source/review pack](https://github.com/fraware/lean-project-evidence/tree/research/ethereum-xmss-durability-handoff-20261013/handoff_xmss_durability) remains available.

**No upstream merge.** Parent [leanSpec PR #1204](https://github.com/leanEthereum/leanSpec/pull/1204)
is still open. The key-identity addition checks **declared local public keys**
in the manifest, not loaded secret-key correspondence, cross-host duplication,
or anti-rollback. Stronger deployment policy needs maintainer approval.

### leanVM arithmetic proof

Exact upstream [leanVM PR #533](https://github.com/leanEthereum/leanVM/pull/533)
head `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`:

- [`fold6` and `fold12` checked together #38479742934](https://github.com/fraware/lean-project-evidence/actions/runs/38479742934).
- [`swar21_spec` checked #38483944815](https://github.com/fraware/lean-project-evidence/actions/runs/38483944815).
- [`swar42_nat_spec` checked #38484404732](https://github.com/fraware/lean-project-evidence/actions/runs/38484404732).
- Theorems' reported axiom closures: `[propext, Classical.choice, Quot.sound]`, **without `sorryAx`**.
- [Clean-room reapplication for 42-digit proof #38485329036](https://github.com/fraware/lean-project-evidence/actions/runs/38485329036) and reviewer note in the [SWAR42 handoff branch](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-swar42-handoff-20261013/handoff_leanvm_533).
- The original `encode_spec` theorem, and hence `verify_spec`/main correctness, still depends on `sorryAx`. No Rust/VM end-to-end equivalence claim.

## New proofs in execution, **not accepted yet**

Pursuing the fixed-width semantics and top-bit admissibility premises using
source-pinned Lean 4.31.0 runs:

| Branch suffix | Target | Latest acceptance run at checkpoint |
|---|---|---|
| `swar42-modular-u64-bound-20261013` | Generic eleven-field bound and initial SWAR sum below `2^64` | [#38515941088](https://github.com/fraware/lean-project-evidence/actions/runs/38515941088) |
| `swar42-stage1-u64-bound-20261013` | Monolithic initial-sum bound | [#38515930381](https://github.com/fraware/lean-project-evidence/actions/runs/38515930381) |
| `packed12-stage-bounds-20261013` | Packed 12-bit base-field headroom | [#38515935816](https://github.com/fraware/lean-project-evidence/actions/runs/38515935816) |
| `fold-intermediates-u64-20261013` | Intermediate shift/add bounds | [#38515937316](https://github.com/fraware/lean-project-evidence/actions/runs/38515937316) |
| `padding-bitvector-bridge-20261013` | 64-bit top-bit clearance and OR predicate equivalence | [#38515722655](https://github.com/fraware/lean-project-evidence/actions/runs/38515722655) |

**No success is presumed for these runs.** Check their final conclusions,
then their exact job logs, before reporting a new proof.

The first monolithic bound run [#38514649484](https://github.com/fraware/lean-project-evidence/actions/runs/38514649484)
failed the default 200,000-heartbeat normalization limit. A subsequent
generation incorrectly placed a `set_option` command between a doc comment
and its theorem, which caused a parser error; the source layout was corrected
in the latest reruns. The modular eleven-field proof is preferred because
it isolates the 64-bit bound from expensive normalization of 42 digits.

The initial bitvector attempt [#38514973847](https://github.com/fraware/lean-project-evidence/actions/runs/38514973847)
was rejected by `bv_decide`'s supported fragment because it mixed
BitVec shifts with `toNat` inequalities. The updated branch tests two
*BitVec-only* propositions and deliberately defers their Nat correspondence.

## Checked arithmetic reference values

The symbolic maximum of the initial four-mask sum is
`16,653,310,622,098,900,764 < 2^64`, based on ten base-64 fields bounded
by 28 and the final field bounded by 14. The packed 12-bit value has upper
envelope `16,156,667,512,422,105,144 < 15*2^60`. The final shift/add
intermediate's envelope is `16,160,612,974,574,100,774 < 2^64`.
[Full derivation and explicitly unproved refinement obligations](./2026-10-13-xmss-fixed-width-arithmetic-bounds.md).

These exact integer calculations are **not** yet a kernel-checked U64
implementation refinement and do not discharge any pending Lean tests.

## Next operations

1. Read the five running-workflow final outcomes, fix actual errors at exact source revisions, consolidate only passing U64/padding lemmas.
2. Connect the verified natural-number SWAR sum to the guest's `U64` operations, then prove little-endian digest-word correspondence and both `encode_spec` branches.
3. Independently audit `encode_spec`, `verify_spec`, `verify_ok_iff`, and guest main theorem axiom closures.
4. Use the pinned maintainer review handoff only through an authorized contributor session. The GitHub connector returned HTTP 403 on upstream commenting and neither `fraware/leanVM` nor `fraware/leanSpec` currently exists as an accessible fork. No upstream comment, PR, or merge was created by this checkpoint.
