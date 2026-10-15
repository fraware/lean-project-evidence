import DigestBytesBridge
import Mathlib.Tactic

/-!
Diagnostic, on an isolated branch, attempting the exact missing
byte-to-word reconstruction theorem from the pinned XMSS definitions.
A successful kernel/axiom check is mandatory before any proof claim.
-/

open Aeneas Aeneas.Std
open EthCryptographySpecs.Xmss
namespace leanxmss.Proofs

set_option maxRecDepth 2000
set_option maxHeartbeats 2000000

theorem digest_low_word_model_exact (lo hi : Std.U64) :
    (Internal.digestWord
      (Statement.digest (Std.Array.make 2#usize [lo, hi])) 0).toNat = lo.val := by
  simp [Internal.digestWord, Statement.digest, Statement.bytes,
    Std.Array.make_val, Bytes.ofWords, Bytes.le]
  all_goals bv_decide

theorem digest_high_word_model_exact (lo hi : Std.U64) :
    (Internal.digestWord
      (Statement.digest (Std.Array.make 2#usize [lo, hi])) 1).toNat = hi.val := by
  simp [Internal.digestWord, Statement.digest, Statement.bytes,
    Std.Array.make_val, Bytes.ofWords, Bytes.le]
  all_goals bv_decide

end leanxmss.Proofs
