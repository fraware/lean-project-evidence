import Lean

/-!
# A minimal reservation contract for stateful XMSS keys

This is a model of a durably committed, per-key high-water mark.
It is deliberately separate from the implementation in leanSpec #1204.

Assumptions outside this Lean model:
* reserve is implemented as a linearizable transaction, including storage commit
  before any one-time signature is requested.
* Concurrent signers use the same serialized durable state and the same key identity.
* A restart recovers that committed state. Backups/rollback to older storage and
  split-brain replicas are outside this model.
* A single monotonically increasing slot for each key is the intended use policy;
  refusing older slots after signing a newer one is permitted.

The proofs concern this abstract state transition only; they do not verify any
Python, database, filesystem, or cryptographic implementation.
-/

namespace XmssReservation

/-- Each signing key has an optional highest committed signing slot. -/
abbrev Ledger := Nat → Option Nat

/-- Is this slot strictly newer than the highest recorded slot for the key? -/
def admissible (l : Ledger) (key slot : Nat) : Bool :=
  match l key with
  | none => true
  | some previous => decide (previous < slot)

/-- Model the state stored by a successful durable claim. -/
def record (l : Ledger) (key slot : Nat) : Ledger :=
  fun queried => if queried = key then some slot else l queried

/-- Refuse a stale reservation; otherwise return the committed next ledger. -/
def reserve (l : Ledger) (key slot : Nat) : Option Ledger :=
  if admissible l key slot then some (record l key slot) else none

@[simp] theorem record_self (l : Ledger) (key slot : Nat) :
    record l key slot key = some slot := by
  simp [record]

@[simp] theorem record_other (l : Ledger) (key slot other : Nat)
    (h : other ≠ key) : record l key slot other = l other := by
  simp [record, h]

/-- A successful claim commits the requested slot under exactly that key. -/
theorem success_commits (l next : Ledger) (key slot : Nat)
    (h : reserve l key slot = some next) : next key = some slot := by
  cases ha : admissible l key slot with
  | false => simp [reserve, ha] at h
  | true =>
      have heq : record l key slot = next := by
        simpa [reserve, ha] using h
      rw [← heq]
      simp

/-- The state is unchanged for any unrelated key. -/
theorem success_preserves_other (l next : Ledger) (key slot other : Nat)
    (h : reserve l key slot = some next) (hne : other ≠ key) :
    next other = l other := by
  cases ha : admissible l key slot with
  | false => simp [reserve, ha] at h
  | true =>
      have heq : record l key slot = next := by
        simpa [reserve, ha] using h
      rw [← heq]
      simp [hne]

/-- The same key-slot pair is refused after a successful commit. -/
theorem success_prevents_replay (l next : Ledger) (key slot : Nat)
    (h : reserve l key slot = some next) :
    reserve next key slot = none := by
  have hcommitted := success_commits l next key slot h
  simp [reserve, admissible, hcommitted]

/-- A committed slot also rules out every earlier slot for the same key. -/
theorem record_refuses_earlier (l : Ledger) (key slot earlier : Nat)
    (h : earlier ≤ slot) : reserve (record l key slot) key earlier = none := by
  have hn : ¬ slot < earlier := Nat.not_lt.mpr h
  simp [reserve, admissible, record, hn]

/-- Recovery is modeled as reading the latest durable ledger, unchanged. -/
def restart (persisted : Ledger) : Ledger := persisted

/-- A restart cannot permit a replay if it recovers the committed ledger. -/
theorem restart_refuses_replay (l : Ledger) (key slot : Nat) :
    reserve (restart (record l key slot)) key slot = none := by
  simp [restart, reserve, admissible, record]

/-- A successful claim after a prior one commits only strictly newer slots. -/
theorem success_is_strictly_newer (l next : Ledger) (key slot previous : Nat)
    (hprev : l key = some previous)
    (hsuccess : reserve l key slot = some next) : previous < slot := by
  cases ha : admissible l key slot with
  | false => simp [reserve, ha] at hsuccess
  | true => simpa [admissible, hprev] using ha

end XmssReservation

#print axioms XmssReservation.success_prevents_replay
#print axioms XmssReservation.record_refuses_earlier
#print axioms XmssReservation.restart_refuses_replay
#print axioms XmssReservation.success_preserves_other
