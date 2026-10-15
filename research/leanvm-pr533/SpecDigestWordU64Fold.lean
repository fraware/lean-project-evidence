import UInt64ByteOrFold
import EthCryptographySpecs.Xmss.Encoding
import Mathlib.Tactic

/-!
The actual Ethereum XMSS `Internal.digestWord` operation reconstructs a
64-bit word using eight byte values and seven OR/shift operations. These
lemmas identify that exact source expression with the already kernel-
checked general unsigned-word byte decoder, without changing either
implementation or the specification.

This source is an experiment until its source-pinned CI and axiom report
pass; no `sorry`, `axiom`, or native SAT calculation is introduced.
-/

open EthCryptographySpecs.Xmss

namespace leanxmss.Proofs

/-- The literal eight-byte OR/shift expression in the specification is
    equal to the recursive UInt64 assembly. -/
theorem eight_byte_layout_eq_fold
    (b0 b1 b2 b3 b4 b5 b6 b7 : UInt8) :
    (b0.toUInt64 ||| (b1.toUInt64 <<< 8) |||
     (b2.toUInt64 <<< 16) ||| (b3.toUInt64 <<< 24) |||
     (b4.toUInt64 <<< 32) ||| (b5.toUInt64 <<< 40) |||
     (b6.toUInt64 <<< 48) ||| (b7.toUInt64 <<< 56)) =
       uint64ByteOrFold [b0, b1, b2, b3, b4, b5, b6, b7] := by
  apply UInt64.toBitVec_inj.mp
  ext i hi
  interval_cases i <;> simp [uint64ByteOrFold]

private def halfByte (d : Digest) (half : Fin 2) (k : Fin 8) : UInt8 :=
  d[8 * half.val + k.val]'(by simp only [EthCryptographySpecs.Xmss.Constants.DIGEST_LEN]; omega)

private def halfByteList (d : Digest) (half : Fin 2) : List UInt8 :=
  [halfByte d half 0, halfByte d half 1,
   halfByte d half 2, halfByte d half 3,
   halfByte d half 4, halfByte d half 5,
   halfByte d half 6, halfByte d half 7]

/-- `Internal.digestWord` is definitionally the eight-byte machine
    decoder proved correct by `uint64ByteOrFold_spec`. -/
theorem digestWord_eq_machine_fold (d : Digest) (half : Fin 2) :
    Internal.digestWord d half = uint64ByteOrFold (halfByteList d half) := by
  simpa only [Internal.digestWord, halfByteList, halfByte] using
    (eight_byte_layout_eq_fold
      (halfByte d half 0) (halfByte d half 1)
      (halfByte d half 2) (halfByte d half 3)
      (halfByte d half 4) (halfByte d half 5)
      (halfByte d half 6) (halfByte d half 7))

end leanxmss.Proofs
