/-!
Deterministic Lean sources paired with `.lpe/lean-extraction.json`.
Compiler treats the JSON artifact as lean.toolchain + complete when present.
This fixture does not require Lake/elan in CI.
-/

def comparisonFunctor : Nat := 1

def helper : Nat := comparisonFunctor
