import LeanxmssProofs.Hash

/-!
# The target-sum encoding

The guest's `encode` is the specification's `wotsEncode`: it rejects the same digests, and its digits are the
specification's.
-/

open Aeneas Aeneas.Std Result WP
open EthCryptographySpecs.Xmss EthCryptographySpecs.Xmss.Constants

namespace leanxmss.Proofs.Encoding

/-- Base-`B` digits, least significant first, xs a number. -/
def val (B : Nat) : List Nat → Nat
  | [] => 0
  | c :: cs => c + B * val B cs

@[simp] theorem val_nil (B : Nat) : val B [] = 0 := rfl
@[simp] theorem val_cons (B c : Nat) (cs : List Nat) : val B (c :: cs) = c + B * val B cs := rfl

/-- Masking splits at a field boundary. -/
theorem land_split (k a b c d : Nat) (ha : a < 2 ^ k) (hc : c < 2 ^ k) :
    (a + 2 ^ k * b) &&& (c + 2 ^ k * d) = (a &&& c) + 2 ^ k * (b &&& d) := by
  apply Nat.eq_of_testBit_eq
  intro j
  have hac : (a &&& c) < 2 ^ k := Nat.and_lt_two_pow _ hc
  rw [Nat.testBit_and, Nat.add_comm a, Nat.add_comm c, Nat.add_comm (a &&& c),
    Nat.testBit_two_pow_mul_add _ ha, Nat.testBit_two_pow_mul_add _ hc, Nat.testBit_two_pow_mul_add _ hac]
  split <;> simp

/-- Masking a number given by fields with a mask given by fields masks each field. -/
theorem val_land (k : Nat) : ∀ (xs ms : List Nat), (∀ a ∈ xs, a < 2 ^ k) → (∀ m ∈ ms, m < 2 ^ k) →
    val (2 ^ k) xs &&& val (2 ^ k) ms = val (2 ^ k) (List.zipWith (· &&& ·) xs ms)
  | [], _, _, _ => by simp
  | _ :: _, [], _, _ => by simp
  | a :: xs, m :: ms, ha, hm => by
    simp only [val_cons, List.zipWith_cons_cons]
    rw [land_split k _ _ _ _ (ha a (by simp)) (hm m (by simp)),
      val_land k xs ms (fun x hx => ha x (by simp [hx])) (fun x hx => hm x (by simp [hx]))]

/-- Dropping the lowest field. -/
theorem val_cons_div (k c : Nat) (cs : List Nat) (hc : c < 2 ^ k) :
    val (2 ^ k) (c :: cs) / 2 ^ k = val (2 ^ k) cs := by
  have : 0 < 2 ^ k := Nat.two_pow_pos k
  simp only [val_cons]
  rw [Nat.add_mul_div_left _ _ this, Nat.div_eq_of_lt hc, Nat.zero_add]

/-- Digit `r` of `x` in base eight. -/
def d (x r : Nat) : Nat := x / 8 ^ r % 8

theorem d_lt (x r : Nat) : d x r < 8 := Nat.mod_lt _ (by decide)

/-- The base-eight digits of `x`, from digit `r`, `n` of them. -/
def digs (x r : Nat) : Nat → List Nat
  | 0 => []
  | n + 1 => d x r :: digs x (r + 1) n

theorem val_digs (x : Nat) : ∀ n r, x / 8 ^ r < 8 ^ n → val 8 (digs x r n) = x / 8 ^ r
  | 0, r, h => by simp [digs] at *; omega
  | n + 1, r, h => by
    simp only [digs, val_cons]
    rw [val_digs x n (r + 1) (by rw [pow_succ, ← Nat.div_div_eq_div_mul]; rw [pow_succ] at h; omega)]
    simp only [d, pow_succ, ← Nat.div_div_eq_div_mul]
    omega


theorem d_land_seven (x r : Nat) : d x r &&& 7 = d x r := by
  rw [show (7 : Nat) = 2 ^ 3 - 1 from rfl, Nat.and_two_pow_sub_one_eq_mod, Nat.mod_eq_of_lt (d_lt x r)]

theorem digs_lt (x r n : Nat) : ∀ a ∈ digs x r n, a < 2 ^ 3 := by
  induction n generalizing r with
  | zero => simp [digs]
  | succ n ih =>
    intro a ha
    simp only [digs, List.mem_cons] at ha
    rcases ha with rfl | ha
    · exact d_lt x r
    · exact ih (r + 1) a ha

/-- The 21 digits of a word below `2^63`. -/
theorem val_digs21 (x : Nat) (hx : x < 2 ^ 63) : val (2 ^ 3) (digs x 0 21) = x := by
  have := val_digs x 21 0 (by simpa using hx)
  simpa using this

/-- The 20 digits of such a word shifted by one digit. -/
theorem val_digs20 (x : Nat) (hx : x < 2 ^ 63) : val (2 ^ 3) (digs x 1 20) = x >>> 3 := by
  have := val_digs x 20 1 (by rw [Nat.div_lt_iff_lt_mul (by decide)]; simpa using hx)
  rw [Nat.shiftRight_eq_div_pow]
  simpa using this

/-- The digit mask `EVEN`. -/
theorem even_val : (8198552921648689607 : Nat) =
    val (2 ^ 3) [7, 0, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, 7, 0, 7] := by
  simp [val]

/-- The even digits of a word, each in a 6-bit field. -/
theorem land_even (x : Nat) (hx : x < 2 ^ 63) :
    x &&& 8198552921648689607 = val 64 [d x 0, d x 2, d x 4, d x 6, d x 8, d x 10, d x 12, d x 14, d x 16,
      d x 18, d x 20] := by
  conv_lhs => rw [← val_digs21 x hx, even_val]
  rw [val_land 3 _ _ (digs_lt x 0 21) (by simp)]
  simp only [digs, List.zipWith_cons_cons, List.zipWith_nil_right, d_land_seven,
    Nat.and_zero, val_cons, val_nil, Nat.reduceAdd, Nat.reducePow]
  omega

/-- The odd digits of a word, each in a 6-bit field. -/
theorem land_odd (x : Nat) (hx : x < 2 ^ 63) :
    x >>> 3 &&& 8198552921648689607 = val 64 [d x 1, d x 3, d x 5, d x 7, d x 9, d x 11, d x 13, d x 15, d x 17,
      d x 19] := by
  conv_lhs => rw [← val_digs20 x hx, even_val]
  rw [val_land 3 _ _ (digs_lt x 1 20) (by simp)]
  simp only [digs, List.zipWith_cons_cons, List.zipWith_nil_left, d_land_seven,
    Nat.and_zero, val_cons, val_nil, Nat.reduceAdd, Nat.reducePow]
  omega

/-- The field mask `LOW6`. -/
theorem low6_val : (17311559823019733055 : Nat) =
    val (2 ^ 6) [63, 0, 63, 0, 63, 0, 63, 0, 63, 0, 15] := by
  simp [val]

theorem land_63 {c : Nat} (h : c < 64) : c &&& 63 = c := by
  rw [show (63 : Nat) = 2 ^ 6 - 1 from rfl, Nat.and_two_pow_sub_one_eq_mod, Nat.mod_eq_of_lt h]

theorem land_15 {c : Nat} (h : c < 16) : c &&& 15 = c := by
  rw [show (15 : Nat) = 2 ^ 4 - 1 from rfl, Nat.and_two_pow_sub_one_eq_mod, Nat.mod_eq_of_lt h]

/-- Adding neighbouring 6-bit fields into 12-bit fields (`Digits::sum`'s second step). UNFINISHED. -/
theorem fold6 (c0 c1 c2 c3 c4 c5 c6 c7 c8 c9 c10 : Nat) (h0 : c0 < 64) (h1 : c1 < 64) (h2 : c2 < 64)
    (h3 : c3 < 64) (h4 : c4 < 64) (h5 : c5 < 64) (h6 : c6 < 64) (h7 : c7 < 64) (h8 : c8 < 64) (h9 : c9 < 64)
    (h10 : c10 < 16) :
    (val 64 [c0, c1, c2, c3, c4, c5, c6, c7, c8, c9, c10] &&& 17311559823019733055) +
      (val 64 [c0, c1, c2, c3, c4, c5, c6, c7, c8, c9, c10] >>> 6 &&& 17311559823019733055) =
    val 4096 [c0 + c1, c2 + c3, c4 + c5, c6 + c7, c8 + c9, c10] := by
  have hc : ∀ a ∈ [c0, c1, c2, c3, c4, c5, c6, c7, c8, c9, c10], a < 2 ^ 6 := by
    intro a ha
    simp only [List.mem_cons, List.not_mem_nil, or_false] at ha
    rcases ha with rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl <;> omega
  have hm : ∀ m ∈ [63, 0, 63, 0, 63, 0, 63, 0, 63, 0, 15], m < 2 ^ 6 := by
    simp
  have heven :
      val 64 [c0, c1, c2, c3, c4, c5, c6, c7, c8, c9, c10] &&& 17311559823019733055 =
        val 64 [c0, 0, c2, 0, c4, 0, c6, 0, c8, 0, c10] := by
    rw [low6_val]
    have h := val_land 6 [c0, c1, c2, c3, c4, c5, c6, c7, c8, c9, c10]
      [63, 0, 63, 0, 63, 0, 63, 0, 63, 0, 15] hc hm
    simpa only [show (2 : Nat) ^ 6 = 64 by decide, List.zipWith_cons_cons,
      List.zipWith_nil_left, List.zipWith_nil_right, Nat.and_zero,
      land_63 h0, land_63 h2, land_63 h4, land_63 h6, land_63 h8, land_15 h10] using h
  have hshift :
      val 64 [c0, c1, c2, c3, c4, c5, c6, c7, c8, c9, c10] >>> 6 =
        val 64 [c1, c2, c3, c4, c5, c6, c7, c8, c9, c10] := by
    rw [Nat.shiftRight_eq_div_pow]
    simpa only [show (2 : Nat) ^ 6 = 64 by decide] using
      (val_cons_div 6 c0 [c1, c2, c3, c4, c5, c6, c7, c8, c9, c10] (by omega))
  have hc' : ∀ a ∈ [c1, c2, c3, c4, c5, c6, c7, c8, c9, c10], a < 2 ^ 6 := by
    intro a ha
    simp only [List.mem_cons, List.not_mem_nil, or_false] at ha
    rcases ha with rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl | rfl <;> omega
  have hodd :
      (val 64 [c0, c1, c2, c3, c4, c5, c6, c7, c8, c9, c10] >>> 6 &&&
          17311559823019733055) =
        val 64 [c1, 0, c3, 0, c5, 0, c7, 0, c9, 0] := by
    rw [hshift, low6_val]
    have h := val_land 6 [c1, c2, c3, c4, c5, c6, c7, c8, c9, c10]
      [63, 0, 63, 0, 63, 0, 63, 0, 63, 0, 15] hc' hm
    simpa only [show (2 : Nat) ^ 6 = 64 by decide, List.zipWith_cons_cons,
      List.zipWith_nil_left, List.zipWith_nil_right, Nat.and_zero,
      land_63 h1, land_63 h3, land_63 h5, land_63 h7, land_63 h9] using h
  rw [heven, hodd]
  simp only [val_cons, val_nil]
  ring

/-- Folding the six 12-bit fields into the lowest (`Digits::sum`'s last steps). UNFINISHED. -/
theorem fold12 (e0 e1 e2 e3 e4 e5 : Nat) (h0 : e0 ≤ 56) (h1 : e1 ≤ 56) (h2 : e2 ≤ 56) (h3 : e3 ≤ 56)
    (h4 : e4 ≤ 56) (h5 : e5 ≤ 56) :
    let s1 := val 4096 [e0, e1, e2, e3, e4, e5]
    let s2 := s1 + s1 >>> 12
    let s3 := s2 + s2 >>> 24
    (s3 + s3 >>> 48) &&& 4095 = e0 + e1 + e2 + e3 + e4 + e5 := by
  dsimp
  rw [show (4095 : Nat) = 2 ^ 12 - 1 by decide, Nat.and_two_pow_sub_one_eq_mod]
  simp only [Nat.shiftRight_eq_div_pow]
  norm_num [val]
  have hd1 :
      (e0 + 4096 * (e1 + 4096 * (e2 + 4096 * (e3 + 4096 * (e4 + 4096 * e5))))) /
          4096 =
        e1 + 4096 * (e2 + 4096 * (e3 + 4096 * (e4 + 4096 * e5))) := by
    omega
  rw [hd1]
  have hlow2 : e0 + e1 + 4096 * (e1 + e2) < 16777216 := by omega
  have hd2 :
      (e0 + 4096 * (e1 + 4096 * (e2 + 4096 * (e3 + 4096 * (e4 + 4096 * e5)))) +
          (e1 + 4096 * (e2 + 4096 * (e3 + 4096 * (e4 + 4096 * e5))))) /
          16777216 =
        (e2 + e3) + 4096 * ((e3 + e4) + 4096 * ((e4 + e5) + 4096 * e5)) := by
    omega
  rw [hd2]
  have hlow4 :
      (e0 + e1 + e2 + e3) +
          4096 * (e1 + e2 + e3 + e4) +
          16777216 * (e2 + e3 + e4 + e5) +
          68719476736 * (e3 + e4 + e5) <
        281474976710656 := by
    omega
  have hd3 :
      (e0 + 4096 * (e1 + 4096 * (e2 + 4096 * (e3 + 4096 * (e4 + 4096 * e5)))) +
          (e1 + 4096 * (e2 + 4096 * (e3 + 4096 * (e4 + 4096 * e5)))) +
          ((e2 + e3) + 4096 * ((e3 + e4) + 4096 * ((e4 + e5) + 4096 * e5)))) /
          281474976710656 =
        (e4 + e5) + 4096 * e5 := by
    omega
  rw [hd3]
  have hsum : e0 + e1 + e2 + e3 + e4 + e5 < 4096 := by omega
  omega

/-- `Digits::get` of a digit index is that digit of its word, in base eight. -/
theorem get_ok (lo hi : Std.U64) (i : Std.Usize) (hlt : i.val < 42) :
    ∃ v, leanxmss.Digits.get (Std.Array.make 2#usize [lo, hi]) i = ok v ∧
      v.val = ([lo, hi][i.val / 21]'(by simp; omega)).val / 8 ^ (i.val % 21) % 8 := by
  apply exists_ok_of_spec
  unfold leanxmss.Digits.get
  simp only [lift, leanxmss.V, leanxmss.W, leanxmss.CHAIN_LENGTH]
  have hn : 32 ≤ System.Platform.numBits := by cases System.Platform.numBits_eq <;> simp [*]
  have h8 : 1 <<< 3 % Usize.size = 8 := by
    rw [Usize.size_def, Usize.numBits_def, UScalarTy.Usize_numBits_eq, Nat.mod_eq_of_lt]; rfl
    exact lt_of_lt_of_le (by decide) (Nat.pow_le_pow_right (by decide) hn)
  step*
  have h8 : i8.val = 8 := by rw [i8_post, h8]
  rw [UScalar.val_and, UScalar.cast_val_eq, i9_post, h8, show 8 - 1 = 2 ^ 3 - 1 from rfl,
    Nat.and_two_pow_sub_one_eq_mod, i6_post, i5_post, i4_post, i1_post, i3_post]
  simp only [Std.Array.make_val, UScalarTy.Usize_numBits_eq, i2_post, i1_post]
  rw [Nat.mod_mod_of_dvd _ (Nat.pow_dvd_pow 2 (by omega)), Nat.shiftRight_eq_div_pow, pow_mul]
  rfl
/-! ## Encoding admissibility and capacity bridge obligations
These lemmas stand independently of the still-admitted `encode_spec`. -/

/-- No top bit is set in an OR iff no top bit is set in either 64-bit input. -/
theorem encoding_top_bit_or (low high : BitVec 64) :
    ((low ||| high) >>> 63 = 0#64) ↔
      ((low >>> 63 = 0#64) ∧ (high >>> 63 = 0#64)) := by
  rw [BitVec.ushiftRight_or_distrib]
  have eq_zero (v : BitVec 64) : (v = 0#64) ↔ v.toNat = 0 := by
    constructor
    · rintro rfl
      rfl
    · intro h
      apply BitVec.eq_of_toNat_eq
      simpa using h
  rw [eq_zero, eq_zero, eq_zero]
  rw [BitVec.toNat_or]
  have hor_small (a b : Nat) (ha : a < 2) (hb : b < 2) :
      (a ||| b = 0 ↔ a = 0 ∧ b = 0) := by
    rcases (show a = 0 ∨ a = 1 by omega) with h | h <;>
      rcases (show b = 0 ∨ b = 1 by omega) with h' | h' <;>
      simp [h, h']
  have hl : (low >>> 63).toNat < 2 := by
    have h := BitVec.toNat_ushiftRight_lt low 63 (by decide)
    norm_num at h
    exact h
  have hh : (high >>> 63).toNat < 2 := by
    have h := BitVec.toNat_ushiftRight_lt high 63 (by decide)
    norm_num at h
    exact h
  exact hor_small _ _ hl hh

/-- Equivalently, failure of the shared guard means a half has a high bit. -/
theorem encoding_top_bit_reject (low high : BitVec 64) :
    ((low ||| high) >>> 63 ≠ 0#64) ↔
      ((low >>> 63 ≠ 0#64) ∨ (high >>> 63 ≠ 0#64)) := by
  simpa only [not_and_or] using not_congr (encoding_top_bit_or low high)

theorem encoding_sum_stages_below_u64 (e0 e1 e2 e3 e4 e5 : Nat)
    (h0 : e0 ≤ 56) (h1 : e1 ≤ 56) (h2 : e2 ≤ 56)
    (h3 : e3 ≤ 56) (h4 : e4 ≤ 56) (h5 : e5 < 16) :
    let s1 := val 4096 [e0, e1, e2, e3, e4, e5]
    let s2 := s1 + (s1 >>> 12)
    let s3 := s2 + (s2 >>> 24)
    s1 < 2 ^ 64 ∧ s2 < 2 ^ 64 ∧ s3 < 2 ^ 64 ∧
      s3 + (s3 >>> 48) < 2 ^ 64 := by
  dsimp
  simp only [Nat.shiftRight_eq_div_pow]
  norm_num [val]
  omega

/-- A digit-sum accumulator of ten complete six-bit fields and one
partial high field cannot wrap a 64-bit machine word, provided its lower
fields are sums of at most four three-bit digits (0..28 each). -/
set_option maxHeartbeats 2000000 in
theorem encoding_initial_sum_below_u64
    (c0 c1 c2 c3 c4 c5 c6 c7 c8 c9 c10 : Nat)
    (h0 : c0 ≤ 28) (h1 : c1 ≤ 28) (h2 : c2 ≤ 28)
    (h3 : c3 ≤ 28) (h4 : c4 ≤ 28) (h5 : c5 ≤ 28)
    (h6 : c6 ≤ 28) (h7 : c7 ≤ 28) (h8 : c8 ≤ 28)
    (h9 : c9 ≤ 28) (h10 : c10 < 16) :
    val 64 [c0, c1, c2, c3, c4, c5, c6, c7, c8, c9, c10] < 2 ^ 64 := by
  norm_num [val]
  omega

end leanxmss.Proofs.Encoding

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
  simp only [Statement.message, Statement.randomness]
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


/-- `encode` panics on no input, finds no encoding exactly where `wotsEncode` finds none, and otherwise gives digits
whose `Digits::get` is the specification's digit `i`, for each chain `i`. -/
theorem encode_spec (pp : Std.Array U64 2#usize) (leaf : Std.U32) (msg : Std.Array U64 4#usize)
    (rnd : Std.Array U64 3#usize) :
    match wotsEncode (Statement.digest pp) (Statement.message msg) (Statement.randomness rnd) (u32 leaf) with
    | none => leanxmss.encode pp leaf msg rnd = ok none
    | some x => ∃ d, leanxmss.encode pp leaf msg rnd = ok (some d) ∧
        ∀ i : Std.Usize, (hi : i.val < Constants.V) → ∃ v, leanxmss.Digits.get d i = ok v ∧ v.val = (x[i.val]'hi).val := by
  sorry

end leanxmss.Proofs
