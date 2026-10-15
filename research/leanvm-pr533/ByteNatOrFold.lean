import LeanxmssProofs.Bytes

/-!
A generic connection from little-endian natural-number byte decoding to
bitwise concatenation. The actual Ethereum XMSS specification uses OR to
assemble eight byte lanes; this lemma establishes the matching mathematical
recurrence for arbitrary byte lists, without restricting the source to
particular example inputs.
-/

namespace leanxmss.Proofs

/-- A little-endian sequence reconstructed by joining eight-bit lanes with
    bitwise OR. -/
def byteOrFold : List UInt8 → Nat
  | [] => 0
  | b :: bs => b.toNat ||| (256 * byteOrFold bs)

/-- Bytewise OR with a disjoint eight-bit low field is the ordinary
    positional base-256 decoding already used by `leanxmss.Bytes`. -/
theorem byteOrFold_eq_toNat (bs : List UInt8) :
    byteOrFold bs = Bytes.toNat bs := by
  induction bs with
  | nil => rfl
  | cons b tail ih =>
    simp only [byteOrFold, Bytes.toNat_cons, ih]
    have hb : b.toNat < 2 ^ 8 := by
      have h := b.toNat_lt
      norm_num at *
      omega
    simpa [show (2 : Nat) ^ 8 = 256 by decide,
      Nat.add_comm, Nat.or_comm] using
      (Nat.two_pow_add_eq_or_of_lt (i := 8) hb (Bytes.toNat tail)).symm

end leanxmss.Proofs
