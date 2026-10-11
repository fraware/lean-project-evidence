import Lean

/-!
# Bounded radix arithmetic for Ethereum leanXMSS

This experiment targets the exact `fold12` identity from leanVM PR #533.
All claims require a green pinned Lean 4.31.0 CI build. The full XMSS
equivalence proof is separately incomplete.
-/

namespace XmssProofLab

theorem sanity_arithmetic (n : Nat) : n + 0 = n := by simp

theorem div_radix_4096 (low high : Nat) (hlow : low < 4096) :
    (low + 4096 * high) / 4096 = high := by omega

theorem mod_radix_4096 (low high : Nat) (hlow : low < 4096) :
    (low + 4096 * high) % 4096 = low := by omega

def val (B : Nat) : List Nat → Nat
  | [] => 0
  | c :: cs => c + B * val B cs

theorem val_cons_div4096 (c : Nat) (cs : List Nat) (hc : c < 4096) :
    val 4096 (c :: cs) / 4096 = val 4096 cs := by
  simpa [val] using div_radix_4096 c (val 4096 cs) hc

theorem val_shift_one (c : Nat) (cs : List Nat) (hc : c < 4096) :
    val 4096 (c :: cs) >>> 12 = val 4096 cs := by
  rw [Nat.shiftRight_eq_div_pow]
  rw [show (2 : Nat) ^ 12 = 4096 by decide]
  exact val_cons_div4096 c cs hc

theorem val_shift_two (a b : Nat) (cs : List Nat)
    (ha : a < 4096) (hb : b < 4096) :
    val 4096 (a :: b :: cs) >>> 24 = val 4096 cs := by
  rw [Nat.shiftRight_eq_div_pow]
  rw [show (2 : Nat) ^ 24 = 4096 * 4096 by decide]
  rw [← Nat.div_div_eq_div_mul]
  rw [val_cons_div4096 a (b :: cs) ha]
  exact val_cons_div4096 b cs hb

theorem val_shift_four (a b c d : Nat) (cs : List Nat)
    (ha : a < 4096) (hb : b < 4096)
    (hc : c < 4096) (hd : d < 4096) :
    val 4096 (a :: b :: c :: d :: cs) >>> 48 = val 4096 cs := by
  rw [Nat.shiftRight_eq_div_pow]
  rw [show (2 : Nat) ^ 48 = 4096 * (4096 * (4096 * 4096)) by decide]
  rw [← Nat.div_div_eq_div_mul]
  rw [val_cons_div4096 a (b :: c :: d :: cs) ha]
  rw [← Nat.div_div_eq_div_mul]
  rw [val_cons_div4096 b (c :: d :: cs) hb]
  rw [← Nat.div_div_eq_div_mul]
  rw [val_cons_div4096 c (d :: cs) hc]
  exact val_cons_div4096 d cs hd

set_option maxHeartbeats 2000000 in
theorem fold12 (e0 e1 e2 e3 e4 e5 : Nat) (h0 : e0 ≤ 56) (h1 : e1 ≤ 56)
    (h2 : e2 ≤ 56) (h3 : e3 ≤ 56) (h4 : e4 ≤ 56) (h5 : e5 ≤ 56) :
    let s1 := val 4096 [e0, e1, e2, e3, e4, e5]
    let s2 := s1 + s1 >>> 12
    let s3 := s2 + s2 >>> 24
    (s3 + s3 >>> 48) &&& 4095 = e0 + e1 + e2 + e3 + e4 + e5 := by
  let s1 := val 4096 [e0, e1, e2, e3, e4, e5]
  let s2 := s1 + s1 >>> 12
  let s3 := s2 + s2 >>> 24
  change (s3 + s3 >>> 48) &&& 4095 = e0 + e1 + e2 + e3 + e4 + e5
  have hs2 : s2 = val 4096 [e0+e1,e1+e2,e2+e3,e3+e4,e4+e5,e5] := by
    dsimp [s2]
    rw [val_shift_one e0 [e1,e2,e3,e4,e5] (by omega)]
    simp [s1,val]
    omega
  have hs3 : s3 = val 4096 [e0+e1+e2+e3,e1+e2+e3+e4,e2+e3+e4+e5,e3+e4+e5,e4+e5,e5] := by
    dsimp [s3]
    rw [hs2, val_shift_two (e0+e1) (e1+e2) [e2+e3,e3+e4,e4+e5,e5] (by omega) (by omega)]
    simp [val]
    omega
  have hshift3 :
    s3 >>> 48 = val 4096 [e4+e5,e5] := by
    rw [hs3]
    exact val_shift_four (e0+e1+e2+e3) (e1+e2+e3+e4)
       (e2+e3+e4+e5) (e3+e4+e5) [e4+e5,e5]
       (by omega) (by omega) (by omega) (by omega)
  rw [show (4095 : Nat) = 2 ^ 12 - 1 by decide,
      Nat.and_two_pow_sub_one_eq_mod]
  rw [hshift3, hs3]
  have hlow : e0 + e1 + e2 + e3 + e4 + e5 < 4096 := by omega
  have heq :
    val 4096 [e0+e1+e2+e3,e1+e2+e3+e4,e2+e3+e4+e5,e3+e4+e5,e4+e5,e5] +
        val 4096 [e4+e5,e5] =
    (e0+e1+e2+e3+e4+e5) +
        4096 * (e1+e2+e3+e4+e5+4096*(e2+e3+e4+e5+4096*(e3+e4+e5+4096*(e4+e5+4096*e5)))) := by
    simp [val]
    omega
  rw [heq]
  exact mod_radix_4096 _ _ hlow

end XmssProofLab
