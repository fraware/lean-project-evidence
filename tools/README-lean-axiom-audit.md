# Strict Lean proof-axiom audit

`tools/lean_axiom_audit.py` parses the **entire** multiline
`#print axioms Namespace.theorem` output, rather than grepping only
the first line. It accepts only `propext`, `Classical.choice`, and
`Quot.sound`. It explicitly rejects `sorryAx`, arbitrary axioms,
and Lean 4 native proof-computation axioms such as
`_native.bv_decide.ax_1_5`.

The necessity was demonstrated by
[proof attempt #38592278322](https://github.com/fraware/lean-project-evidence/actions/runs/38592278322),
which returned green even though `bv_decide` introduced a native
computation axiom printed on a later line. **That historical result is not
accepted as a kernel-only proof.** A replacement based exclusively on
`BitVec.ushiftRight_or_distrib` and `BitVec.or_eq_zero_iff` is tested
separately with an exact whitelist.

This script is for Lean's `#print axioms` report format and fails on
missing, duplicated, truncated, or malformed reports. The whitelist
expresses the project's standard for eligible theorems; it is not a
general statement that these are the only justified axioms in Lean.
