<!-- leanvm-pr533-two-folds-reviewed-20261013-v1 -->
I reproduced the leanXMSS verification project at PR #533 head `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d` and completed both of its admitted arithmetic folding lemmas, `Encoding.fold6` and `Encoding.fold12`, without changing their statements or any other source.

Both proofs pass together in a fresh Lean 4.31.0 build (1,713 build jobs). The independent axiom report for **each** is:

```text
[propext, Classical.choice, Quot.sound]
```

Neither depends on `sorryAx`. The higher-level `encode_spec` theorem remains admitted, so `verify_spec` still reports `sorryAx`. I am not claiming complete guest equivalence.

I prepared a minimal source-pinned patch and independently checked that it applies to this exact PR head and reconstructs the Lean-checked source blob.

- [Two-lemma patch and reproduction](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-both-folds-handoff-20261013/handoff_leanvm_533)
- [Both lemmas kernel-checked in the same build](https://github.com/fraware/lean-project-evidence/actions/runs/38479742934)
- [Independent patch reapplication and exact Git blob](https://github.com/fraware/lean-project-evidence/actions/runs/38480309105)

These lemma bodies are available to integrate directly into #533 if useful for the intended verification path. The remaining encoding correspondence, SDK/VM model assumptions, and guest source translation remain separate proof obligations.
