# leanVM PR #533 — Exact `encode_spec` proof frontier

Date: 2026-10-15. Review basis: `leanEthereum/leanVM` PR #533
at `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d` and
`ethereum/cryptography-specs@d1331f02e308fe6d0aedda8601e4d5b0fc360318`.
Lean toolchain: 4.31.0. This dossier records proof applicability, not a
certification of the Rust binary or recursion machine.

## What is already checked together

The [source-pinned proof composition run](https://github.com/fraware/lean-project-evidence/actions/runs/38770808542)
passed with five kernel-checked declarations, all without `sorryAx`:
`leanxmss.Proofs.Encoding.digits_sum_impl_spec`,
`leanxmss.Proofs.encoding_payload_words`,
`leanxmss.Proofs.encoding_tweak_digest`,
`leanxmss.Proofs.Encoding.guest_padded_or_iff`, and
`leanxmss.Proofs.Encoding.get_ok`.
Its input overlay has exact Git blob checks and an independent axiom audit.

The [guard-to-range proof](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-guarded-digits-sum-20261015/research/leanvm-pr533)
adds `top_bit_zero_iff_lt`, `guest_guard_iff_digit_sum_bounds`, and
`digits_sum_succeeds_under_guest_guard`. The corrected source was verified at
research commit `f69726c2363c1e8e524278d83de0644679996735` in
[source-pinned run #38772517080](https://github.com/fraware/lean-project-evidence/actions/runs/38772517080):
all three declarations compiled and their independent axiom closures contained
only `propext`, `Classical.choice`, and `Quot.sound`, without `sorryAx`.
The proof file's exact Git blob is `0cf38f005a487cbddc4eb8aebf463dee959d4d03`.
Earlier failed diagnostic runs were not accepted as evidence.

The original `leanxmss.Proofs.encode_spec` still has `sorryAx`. Hence
`verify_spec`, `verify_ok_iff`, and higher guest claims cannot be reported
as fully proved. A successful build of `LeanxmssProofs.Encoding` is not
a substitute for checking the exact theorem's axiom dependencies.

## Exact missing correspondence: digest bytes to guest words

The [source-pinned digest-byte proof](https://github.com/fraware/lean-project-evidence/blob/research/leanvm-pr533-digest-bytes-handoff-20261015/research/leanvm-pr533/DIGEST_BYTES_HANDOFF.md) has now been checked in [CI #38777398342](https://github.com/fraware/lean-project-evidence/actions/runs/38777398342): `digest_bytes_exact`, `digest_low_half_exact`, and `digest_high_half_exact` match the exact serialized low/high halves, with no `sorryAx`. These results establish byte ordering, not yet full numeric word reconstruction.

The specification's `Internal.digestWord` reconstructs each `UInt64` from
eight little-endian bytes. The guest's Aeneas model uses `Std.U64` words.
The next theorem must establish (for every pair `lo hi : Std.U64`):

```lean
let ws := Std.Array.make 2#usize [lo, hi]
(Internal.digestWord (Statement.digest ws) 0).toNat = lo.val
(Internal.digestWord (Statement.digest ws) 1).toNat = hi.val
```

The first direct `Internal.digestWord` experiment has now been evaluated. [CI #38777441572](https://github.com/fraware/lean-project-evidence/actions/runs/38777441572) failed because the expanded goal was outside the fragment supported by `bv_decide`. The [exact diagnostic and modular proof route](https://github.com/fraware/lean-project-evidence/blob/research/leanvm-pr533-digest-bytes-handoff-20261015/research/leanvm-pr533/DIGEST_WORD_DIAGNOSTIC.md) records the evidence without treating this tactic limitation as a mathematical counterexample.

These are *target statements*, not checked declarations. The exact binder
syntax and elaboration must be validated against the pinned Lean source.
They must be proved through `Statement.bytes`, `Bytes.ofWords`, and the
specification's `Internal.digestWord`. A manually postulated equality
would silently consume the essential implementation-correspondence obligation.

This is the semantic boundary connecting the guest's guard, digit sum,
and digit retrieval to the spec's `Internal.padded`, `Internal.onTarget`,
and `Internal.digits`.

## Completing `encode_spec`

1. **Digest binding** — prove the word/byte equalities above without extra axioms.
   The existing `tweak_hash_spec` and `encoding_tweak_digest` already connect
   the modeled hash request and response to the spec's digest.
2. **Padding correspondence** — prove
   `Internal.padded (Statement.digest ws) = true` iff the guest high-bit
   guard accepts, using the new word/byte bridge and checked bitvector
   lemmas. The source guard is evaluated before the digit sum.
3. **Target-sum correspondence** — prove that the
   `(Internal.digits digest).foldl` from `Internal.onTarget`
   equals the sum of the 21 base-eight digits in each of the two
   corresponding words. Use the already-checked source-level `Digits.sum`
   theorem; do not assume this equality without a proof.
4. **Per-index encoding relation** — apply `get_ok` and the word/byte bridge
   to connect every guest digit with the `wotsEncode` vector entry.
5. **Result and control-flow refinement** — prove both `none` and `some`
   branches, including the `Result` success/panic conditions, the guest's
   `then_some`, and `U64` conversion of `TARGET_SUM`.
6. **Kernel and applicability audit** — report the axioms of `encode_spec`,
   `verify_spec`, `verify_ok_iff` and relevant `main` theorems,
   from the exact revisions. Identify external SDK models, Charon/Aeneas
   translation, guest I/O transcription, and compiled executable binding
   as separate premises. No end-to-end operational-security claim follows
   from the kernel audit alone.

## North Star and integration decision

The output sought is an independently checkable relation about a *specific
guest and specification*, whose assumptions identify the remaining route
to an actual executable claim. This work is upstream-useful if it removes
the admitted `encode_spec` obligation without changing its semantics.

Keep the proof at the leanVM verification boundary. Integrate by the smallest
maintainer-reviewable source diff; preserve independent theorem identities
and document generated translation inputs. Do not extract a general
verification platform from this exercise. A reusable evidence-transport
mechanism becomes justified only when a second independently maintained
application exercises the same formal checking semantics.

Upstream review and adoption remain unverified and require maintainer
coordination. The installed GitHub connection currently has read permission
but has returned HTTP 403 on writing to the upstream PR.
