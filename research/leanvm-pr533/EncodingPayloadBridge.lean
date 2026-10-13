import LeanxmssProofs.Encoding

/-!
An isolated, source-pinned step toward the remaining encode_spec obligation.
The payload passed into the translated Rust guest and the specification's
encodingPayload must have identical bytes. This file introduces no axioms.
-/

open Aeneas Aeneas.Std Result WP
open EthCryptographySpecs.Xmss EthCryptographySpecs.Xmss.Constants

namespace leanxmss.Proofs

open Bytes

private theorem zero_payload_word :
    toBA (ofWords ([0#u64] : List U64)) = ByteArray.mk (Array.replicate 8 0) := by
  apply ByteArray.ext
  decide

/-- The guest's 8-word input is exactly the spec's 64 encoding bytes. -/
theorem encoding_payload_words
    (msg : Std.Array U64 4#usize) (rnd : Std.Array U64 3#usize) :
    encodingPayload (Statement.message msg) (Statement.randomness rnd) =
      toBA (ofWords (msg.val ++ rnd.val ++ [0#u64])) := by
  unfold encodingPayload
  rw [packBytes_eq, packBytes_eq]
  rw [Statement.bytes_toList msg MESSAGE_LEN rfl, Statement.bytes_toList rnd RANDOMNESS_LEN rfl]
  simp only [ofWords_append, toBA_append]
  rw [zero_payload_word]

/-- The guest's encoded 8-word payload as a fixed-size array. -/
def encodingPayloadWords (msg : Std.Array U64 4#usize)
    (rnd : Std.Array U64 3#usize) : Std.Array U64 8#usize :=
  Std.Array.make 8#usize (msg.val ++ rnd.val ++ [0#u64]) (by simp)

/-- Hashing the guest's encoding payload gives the spec's encoding digest. -/
theorem encoding_tweak_digest (pp : Std.Array U64 2#usize) (leaf : Std.U32)
    (msg : Std.Array U64 4#usize) (rnd : Std.Array U64 3#usize) :
    ∃ d, leanxmss.tweak_hash pp (tyByte TweakType.encoding) 0#u32 leaf (encodingPayloadWords msg rnd) = ok d ∧
      Statement.digest d =
        tweakHash (Statement.digest pp) .encoding (u32 0#u32) (u32 leaf)
          (encodingPayload (Statement.message msg) (Statement.randomness rnd)) := by
  obtain ⟨d, hd, hspec⟩ := tweak_hash_spec
    (pp := pp) (t := TweakType.encoding) (pos := 0#u32) (idx := leaf)
    (payload := encodingPayloadWords msg rnd)
  refine ⟨d, hd, ?_⟩
  rw [encoding_payload_words]
  simpa only [encodingPayloadWords, Std.Array.make_val] using hspec

end leanxmss.Proofs

#print axioms leanxmss.Proofs.encoding_payload_words
#print axioms leanxmss.Proofs.encoding_tweak_digest
