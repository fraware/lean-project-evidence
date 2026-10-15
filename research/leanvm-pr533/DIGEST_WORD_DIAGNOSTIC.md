# Exact digest-word reconstruction — diagnostic and next proof decomposition

Date: 2026-10-15. Target: `leanEthereum/leanVM` PR #533, exact
head `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`, Lean 4.31.0.

## Established prerequisite

[CI #38777398342](https://github.com/fraware/lean-project-evidence/actions/runs/38777398342)
passed for `digest_bytes_exact`, `digest_low_half_exact`, and
`digest_high_half_exact`. The corresponding exact source blob is
`e73c1e756b68ce4ae9183850dc452dabab1b532a`.
All three dependencies have only `propext`, `Classical.choice`, and
`Quot.sound`; no `sorryAx`.

## Failed diagnostic, correctly classified

[CI #38777441572](https://github.com/fraware/lean-project-evidence/actions/runs/38777441572)
executed `DigestWordAssemblyDiagnostic.lean` at pinned source and
compiled the byte-level prerequisite, then failed its *two new*
reconstruction theorem attempts. Lean reported, on lines 22 and 29:

```text
None of the hypotheses are in the supported BitVec fragment
after applying preprocessing.
```

The attempts expanded `Internal.digestWord`, `Statement.bytes`,
`Bytes.ofWords` and `Bytes.le`, then invoked `bv_decide` on the
whole composite expression. This exposed `Nat` division, list lookup,
vector indexing, and bitvector operations in one goal. The tactic did
not handle the expression as given. **No kernel-checked word-reassembly
theorem was produced.** This error does not establish that the target
proposition is false.

Do not re-run the same opaque automation unchanged.

## Decomposed proof plan

1. Work in a *pure* `BitVec 64` representation and prove the packing
   of eight disjoint 8-bit fields by 8-bit shifts and OR. Restrict
   `bv_decide` to operations it supports; audit the theorem's axioms.
2. Prove a separate shift/mod extraction lemma that relates
   `Bytes.le 8 w.val` to the eight bitvector fields of a
   `Std.U64` word. Use `Nat.div_div_eq_div_mul`,
   `Nat.shiftRight_eq_div_pow`, and proved range bounds. Reuse the
   already checked `Bytes.toNat_le` and `Bytes.word_le` lemmas.
3. Apply the packing lemma to the actual definition
   `EthCryptographySpecs.Xmss.Internal.digestWord`. Preserve the
   exact left-hand side of the original `encode_spec` model.
4. Specialize to the low and high words by rewriting with
   `digest_low_half_exact` and `digest_high_half_exact`.
5. Re-run source-pinned CI, `#print axioms`, and cross-check downstream
   `padded` and digit indexing, keeping `encode_spec` admitted until
   its exact theorem statement is proved.

**Research criterion:** the completed theorem must speak about the
actual `Internal.digestWord (Statement.digest ...)` expression. A
theorem about a separately invented decoder does not close this seam.

**Trust boundary:** even a successful exact model equality does not
prove the compiled guest, translation pipeline, or external SDK models.
Those remain separately identified obligations in the project's North
Star.
