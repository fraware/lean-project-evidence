import LeanxmssProofs.Bytes

/-!
The guest's two 64-bit digest words and the specification's 16-byte digest
are represented in little-endian order. These lemmas establish the precise
byte-level relation for all guest word values, through the actual
`Statement.digest` function, with no admitted assumptions.

They do not yet equate `Internal.digestWord` to the original words: that
separate arithmetic bit-assembly correspondence is a remaining obligation.
-/

open Aeneas Aeneas.Std
namespace leanxmss.Proofs

/-- The specification-facing digest contains exactly the little-endian
    bytes of the two Aeneas-translated guest words, in their original order. -/
theorem digest_bytes_exact (lo hi : Std.U64) :
    (Statement.digest (Std.Array.make 2#usize [lo, hi])).toList =
      Bytes.le 8 lo.val ++ Bytes.le 8 hi.val := by
  change (Statement.bytes (Std.Array.make 2#usize [lo, hi]) 16).toList =
    Bytes.le 8 lo.val ++ Bytes.le 8 hi.val
  rw [Statement.bytes_toList _ 16 rfl]
  simp [Std.Array.make_val, Bytes.ofWords]

/-- The first eight specification bytes represent precisely the guest's
    low word, including leading-zero bytes. -/
theorem digest_low_half_exact (lo hi : Std.U64) :
    (Statement.digest (Std.Array.make 2#usize [lo, hi])).toList.take 8 =
      Bytes.le 8 lo.val := by
  rw [digest_bytes_exact]
  simp [Bytes.le_length]

/-- The second eight specification bytes represent precisely the guest's
    high word, including leading-zero bytes. -/
theorem digest_high_half_exact (lo hi : Std.U64) :
    (Statement.digest (Std.Array.make 2#usize [lo, hi])).toList.drop 8 =
      Bytes.le 8 hi.val := by
  rw [digest_bytes_exact]
  simp [Bytes.le_length]

end leanxmss.Proofs
