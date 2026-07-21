/-
  Minimal JSON string builders for protocol v2 emission.
-/
namespace LpeExtract.Json

def escape (s : String) : String :=
  (((s.replace "\\" "\\\\").replace "\"" "\\\"").replace "\n" "\\n").replace "\r" "\\r"
    |>.replace "\t" "\\t"

def str (s : String) : String :=
  "\"" ++ escape s ++ "\""

def strArray (xs : List String) : String :=
  "[" ++ ", ".intercalate (xs.map str) ++ "]"

def bool (b : Bool) : String :=
  if b then "true" else "false"

def nat (n : Nat) : String :=
  toString n

def optStr (s? : Option String) : String :=
  match s? with
  | some s => str s
  | none => "null"

def optNat (n? : Option Nat) : String :=
  match n? with
  | some n => nat n
  | none => "null"

def object (fields : List (String × String)) : String :=
  "{" ++ ", ".intercalate (fields.map fun (k, v) => str k ++ ": " ++ v) ++ "}"

def edge (a b : String) : String :=
  object [("dependee", str a), ("depender", str b)]

def importEdge (a b : String) : String :=
  object [("imported", str a), ("importing", str b)]

end LpeExtract.Json
