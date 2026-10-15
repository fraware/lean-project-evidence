# leanVM PR #533 — Verified digest byte representation

**Verification date:** 2026-10-15.
**Upstream source:** `leanEthereum/leanVM` PR #533, exact head
`4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.
**Toolchain:** Lean 4.31.0, `verification/leanxmss/lean-toolchain`.
**Research source:** `research/leanvm-pr533/DigestBytesBridge.lean`,
Git blob `e73c1e756b68ce4ae9183850dc452dabab1b532a`.
**Verified research commit:** `b4f624756b6a78c25c0dd8e9a4886f063bba248c`.
**Evidence:** [GitHub Actions #38777398342](https://github.com/fraware/lean-project-evidence/actions/runs/38777398342), successful.

## Checked declarations

The source-pinned workflow built 1,702 Lean jobs, compiled the three
declarations below, and audited each with `#print axioms`:

- `leanxmss.Proofs.digest_bytes_exact`: `Statement.digest` maps two
  guest `Std.U64` words to exactly their concatenated little-endian
  8-byte representations, without dropping the leading-zero bytes.
- `leanxmss.Proofs.digest_low_half_exact`: the first eight bytes are
  those of the low word.
- `leanxmss.Proofs.digest_high_half_exact`: the final eight bytes
  are those of the high word.

Each dependency closure is exactly
`[propext, Classical.choice, Quot.sound]`, with no `sorryAx`.
The workflow checks the proof file's exact Git blob and reconstructs
the pinned upstream tree before Lean runs.

## Precise limitation

The specification's `Internal.digestWord` explicitly reassembles
eight bytes using `UInt64` shifts and bitwise OR. The checked lemmas
above prove the **input byte representation**, not yet the numeric equality

```text
(Internal.digestWord (Statement.digest (Std.Array.make 2#usize [lo, hi])) 0).toNat = lo.val
(Internal.digestWord (Statement.digest (Std.Array.make 2#usize [lo, hi])) 1).toNat = hi.val
```

The two reconstruction equalities are universal *target statements*,
not established declarations in this handoff. A separate experimental
branch (`research/leanvm-pr533-digest-assembly-diagnostic-20261015`)
tries to discharge them and must pass source-pinned CI and independent
axiom checks before being promoted.

The upstream `encode_spec` theorem still depends on `sorryAx`.
Neither this byte-layout result nor the previously checked digit-sum
and padding lemmas provide compiled Rust correctness, Charon/Aeneas
translation correctness, or an end-to-end cryptographic implementation
guarantee.

## Next theorem

Prove a generic 8-byte little-endian reassembly identity matching the
specification's *exact* OR-and-shift expression, then specialize it to
the two halves using `digest_low_half_exact`,
`digest_high_half_exact`, and the existing `Bytes.word_le` theorem.
This keeps bitvector arithmetic separate from the digest mapping and
supports a compact, reviewable eventual upstream patch.
