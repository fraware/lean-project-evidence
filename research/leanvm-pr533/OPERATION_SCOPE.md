# Actual Aeneas operation-level proof handoff

Pinned LeanVM PR #533 head `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`
(Lean 4.31.0). This branch combines the separately checked mathematical
SWAR42/range lemmas with the first three checked `Std.U64` additions, the
first three prefix bounds, the exact right-shift by `W=3`, and EVEN/LOW6
mask operations.

Separate successful kernel/axiom checks:
- [Aeneas checked additions and prefixes](https://github.com/fraware/lean-project-evidence/actions/runs/38521837459).
- [Aeneas shifts and bitwise masks](https://github.com/fraware/lean-project-evidence/actions/runs/38522147744).
- [Mathematical SWAR and range results](https://github.com/fraware/lean-project-evidence/actions/runs/38519333671).

The same-source integration job on this branch is an **additional** gate.
Until it reports success, do not claim the combined overlay has been checked.

This work does not change the guest implementation or
`leanxmss.Proofs.encode_spec`. It is not yet an end-to-end proof of
`leanxmss.Digits.sum`. Its seven checked-addition overflow obligations and one final
value-equivalence obligation were identified by a direct-source diagnostic; see
[CI #38521214202](https://github.com/fraware/lean-project-evidence/actions/runs/38521214202).

No SDK/VM model soundness or Charon/Aeneas extraction correctness is
implied by checking these library-driven operation lemmas.
