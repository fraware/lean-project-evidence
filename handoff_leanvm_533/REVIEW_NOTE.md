<!-- leanvm-pr533-swar42-reviewed-20261013-v1 -->
I reproduced the leanXMSS verification project at PR #533 head `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d` (Lean 4.31.0) and completed the two admitted arithmetic folding lemmas, `Encoding.fold6` and `Encoding.fold12`, without changing their statements or any other source. I also proved a new 42-digit arithmetic lemma, `Encoding.swar42_nat_spec`.

The new theorem relates the *natural-number* version of the guest's two-half EVEN-mask, LOW6-mask, and shift/add folding algorithm to the sum of exactly 42 base-eight XMSS chain digits, under the condition that each digest half is below `2^63`. The result uses the checked fold lemmas with explicit field bounds.

All three theorems passed in the **same** 1,713-job Lean build, and `#print axioms` returned `[propext, Classical.choice, Quot.sound]` for each. None depends on `sorryAx`. The higher-level `encode_spec` and `verify_spec` remain admitted. In particular, fixed-width `U64` arithmetic refinement, digest byte/word correspondence, and encoding acceptance/rejection branches must be proved separately. I am not claiming guest or VM equivalence.

I prepared a source-pinned patch, then independently re-applied it and verified that it produces the exact source blob that passed the Lean build.

- [Minimal patch and reconstruction](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-swar42-handoff-20261013/handoff_leanvm_533)
- [Full pinned Lean build and axiom report](https://github.com/fraware/lean-project-evidence/actions/runs/38484404732)
- [Independent patch-identity job](https://github.com/fraware/lean-project-evidence/actions/runs/38485329036)

These verified proof bodies are available for integration into #533 if they align with the current Rust-guest proof architecture.
