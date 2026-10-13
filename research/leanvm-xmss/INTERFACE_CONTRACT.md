# leanVM XMSS correspondence — exact first proof boundary

Research baseline: `leanEthereum/leanVM@1f9e4c4f478038a95a2619009cb9cf654ae0824e`.
Open target: [leanVM issue #494](https://github.com/leanEthereum/leanVM/issues/494), updated 5 October 2026. The issue calls for proving that the leanXMSS guest agrees with the Lean cryptography specification, mentioning Aeneas.

## Observed code and formal definitions

| Role | Repository file | Git blob | Relevant symbols |
| --- | --- | --- | --- |
| Native Rust tweak serialization and hash | `crates/xmss/src/hash.rs` | `8db3bdbb864764e677acaea11f2d2c455ac66687` | `make_tweak`, `tweak_hash` |
| Rust WOTS operations | `crates/xmss/src/wots.rs` | `797c01f5e6feabe413f4f268a3b11c929078429e` | `chain_hash`, WOTS encoding and randomizer |
| Native Rust XMSS key / tree | `crates/xmss/src/xmss.rs` | `0ce36ec7b80a70019e5310532094d23aba4ed975` | `key_gen_from_seed`, restricted ranges |
| Lean 4 scheme | `formal/xmss/XmssSecurity/Scheme.lean` | `b648244bcf1c0399b4e4f9caa6df40f859574c70` | `bytesLE`, `fieldBytes`, `hashDomainFields`, `tweakableHashInput` |
| Aggregation verifier guest (zkDSL, **not Rust**) | `crates/rec_aggregation/guests/lean_ethereum.py` | `8185fa203fc9a09d74aff168739713fab49a5959` | `fill_xmss_leaf_index_tables`, `verify_sig`, `walk` |
| Formalization scope | `formal/xmss/README.md` | `057ad92765c89d04ebb213ed7035a05f9ee0432e` | Random-oracle security and full-tree scope |

The Rust serializer uses a 16-byte tweak with:
- byte 0 = protocol domain (0);
- byte 1 = tweak type/tag;
- bytes 2–3 = 0;
- bytes 4–7 = little-endian `sub_position : u32`;
- bytes 8–11 = 0;
- bytes 12–15 = little-endian `index : u32`.

The Lean specification's `fieldBytes` constructs the corresponding byte sequence from `TweakFields` and `bytesLE`. Its typed `HashDomain` selects tag 1 for chain, 2 for WOTS public key, 3 for Merkle, 4 for encoding; `KeygenDomain` uses tags 0 and 5. Rust `tweak_hash` hashes `tweak || parameter || payload` with BLAKE2s and truncates to 16 bytes.

These are **source-level correspondences**, not machine-checked implementation equivalence.

## Minimal theorem target (candidate)

For every `tag : UInt8` and `position, index : UInt32`, show that an Aeneas-generated semantic model of the actual Rust `make_tweak(tag, position, index)` produces a 16-byte output identical to `Scheme.fieldBytes (⟨tag, position, index⟩)`, with explicit casts from Rust unsigned integers to Lean `BitVec 8` / `BitVec 32`.

Next, lift byte equality to each typed hash-input constructor and establish equality of **serialized preimages** for chain, WOTS public-key hash, Merkle and encoding calls. This statement is independent of any claim that concrete BLAKE2s behaves as a random oracle. Test all domain tags and boundary values `0`, `2^32-1`, and varying index/position separately from a proof.

Proof prerequisites: identify the exact Aeneas-extracted Rust function and compiler settings; choose a representation for fixed-size Rust byte arrays; establish the `UInt32`/little-endian correspondence; and decide how external `primitives::hash::Hasher` will be abstracted. **No Aeneas extraction or Lean proof of this equality has been executed yet.**

## The architectural gap behind issue #494

The guest verifying aggregated XMSS claims is `lean_ethereum.py`, explicitly described as **zkDSL that is not runnable Python**. It uses host-provided tweak prefixes, converts tweak/index data into canonical field cells, and executes `fill_xmss_leaf_index_tables`, `verify_sig`, and `walk`. Aeneas Rust translation of `crates/xmss` alone would **not** establish that the zkDSL guest computes the same verifier.

A defensible program should separate these obligations:

1. **Rust/spec serialization:** formal equality of tweak and hash-preimage bytes.
2. **Rust/spec algorithmic correspondence:** bounded WOTS chain, target-sum encoding, Merkle authentication, then whole-signature verification, with hash calls abstracted consistently.
3. **Guest/native equivalence:** witness layout, host-provided constants, field-cell packing and `verify_sig` logic agree with the intended native verifier for valid and rejected inputs.
4. **Compilation/execution transport:** prove or independently validate the zkDSL → leanVM ISA → machine execution correspondence under a pinned compiler and VM. A Rust proof is not by itself a proof of the compiled guest.
5. **Cryptographic assumption boundary:** the Lean security model uses a consistent random oracle; the Rust implementation instantiates concrete BLAKE2s. Equality of algorithms under a hash abstraction is distinct from a theorem that BLAKE2s is a random oracle.

The formal security README explicitly limits the theorem to full-tree generation, while Rust also supports restricted leaf-index ranges. Restricting the first correspondence target to the overlapping supported input domain avoids changing the existing theorem's statement without review.

## Adoption criteria

A complete first milestone has an extracted Rust model (rather than a hand-written imitation), a kernel-checked theorem against the pinned Lean spec, a negative test catching deliberate byte-order/tag/index errors, exact source provenance and a real CI build. Until then, this document is a verified *interface inventory and candidate proof obligation*, not a completed formal proof.

Before attempting the large guest equivalence proof, ask leanVM maintainers which guest semantics and compiler correctness facts are already available and whether issue #494 intends a native-Rust equality theorem, a zkDSL-to-spec relation, or both. The issue text alone does not decide that.
