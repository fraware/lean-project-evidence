import ByteNatOrFold

/-!
Connect the mathematical OR-fold to the actual `UInt64` shift-and-OR
operations used by the Ethereum XMSS digest decoder.

Crucially, the theorem accounts for overflow and proves the 64-bit
execution result equals the unbounded natural-number byte decoder
whenever the serialized input contains at most eight bytes.
-/

namespace leanxmss.Proofs

/-- Read a little-endian list of bytes into a machine word using only
    unsigned 64-bit OR and left shifts. -/
def uint64ByteOrFold : List UInt8 → UInt64
  | [] => 0
  | b :: bs => b.toUInt64 ||| (uint64ByteOrFold bs <<< 8)

/-- On at most eight bytes, machine-word assembly returns the exact
    mathematical little-endian value without overflow. -/
theorem uint64ByteOrFold_spec (bs : List UInt8) (hlen : bs.length ≤ 8) :
    (uint64ByteOrFold bs).toNat = Bytes.toNat bs := by
  induction bs with
  | nil => rfl
  | cons b tail ih =>
    have htailLen : tail.length ≤ 7 := by
      simp at hlen
      omega
    have htail : (uint64ByteOrFold tail).toNat = Bytes.toNat tail :=
      ih (by omega)
    have hbound : Bytes.toNat tail < 256 ^ 7 :=
      lt_of_lt_of_le (Bytes.toNat_lt tail)
        (Nat.pow_le_pow_right (by decide) htailLen)
    have hscaled : Bytes.toNat tail * 256 < 2 ^ 64 := by
      calc
        Bytes.toNat tail * 256 < 256 ^ 7 * 256 :=
          Nat.mul_lt_mul_of_pos_right hbound (by decide)
        _ = 2 ^ 64 := by decide
    have hshift :
        (uint64ByteOrFold tail <<< (8 : UInt64)).toNat =
          256 * Bytes.toNat tail := by
      calc
        (uint64ByteOrFold tail <<< (8 : UInt64)).toNat =
            (Bytes.toNat tail * 256) % 2 ^ 64 := by
          simp [UInt64.toNat_shiftLeft, htail, Nat.shiftLeft_eq,
            Nat.mul_comm]
        _ = 256 * Bytes.toNat tail := by
          rw [Nat.mod_eq_of_lt hscaled]
          omega
    have hnat : b.toNat ||| (256 * Bytes.toNat tail) =
        Bytes.toNat (b :: tail) := by
      have h := byteOrFold_eq_toNat (b :: tail)
      simpa only [byteOrFold, byteOrFold_eq_toNat] using h
    change (b.toUInt64 ||| (uint64ByteOrFold tail <<< (8 : UInt64))).toNat =
      Bytes.toNat (b :: tail)
    rw [UInt64.toNat_or, UInt8.toNat_toUInt64, hshift]
    exact hnat

end leanxmss.Proofs
