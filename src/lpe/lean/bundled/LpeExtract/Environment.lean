/-
  Environment scanning for protocol v2 declaration / edge emission.
  Lean 4.14-compatible; keep surface area close to the fixture extractor.
-/
import Lean
import LpeExtract.Json
import LpeExtract.Modules
import LpeExtract.Protocol

open Lean
open LpeExtract

namespace LpeExtract.Environment

def kindOf : ConstantInfo → String
  | .axiomInfo _ => "axiom"
  | .defnInfo _ => "definition"
  | .thmInfo _ => "theorem"
  | .opaqueInfo _ => "opaque"
  | .quotInfo _ => "opaque"
  | .inductInfo _ => "inductive"
  | .ctorInfo _ => "constructor"
  | .recInfo _ => "recursor"

def sourcePathGuess (module : String) : String :=
  if module.isEmpty || module == "[anonymous]" then ""
  else (module.replace "." "/") ++ ".lean"

def axiomsOf (env : Lean.Environment) (n : Name) : Array Name :=
  (((CollectAxioms.collect n).run env).run {}).2.axioms

def collectDeclarations (env : Lean.Environment) (roots : Array Name) :
    List (Name × ConstantInfo) :=
  env.constants.fold (init := []) fun acc name info =>
    if name.isInternal || !Modules.isProjectName roots name then acc
    else (name, info) :: acc

def collectDeclEdges (decls : List (Name × ConstantInfo)) : List (String × String) :=
  Id.run do
    let names : NameSet := decls.foldl (init := {}) fun s (n, _) => s.insert n
    let mut edges : List (String × String) := []
    let mut seen : NameSet := {}
    for (depender, info) in decls do
      let used := info.getUsedConstantsAsSet
      for dependee in used do
        if dependee != depender && names.contains dependee then
          let key := Name.mkStr dependee depender.toString
          if !seen.contains key then
            seen := seen.insert key
            edges := (dependee.toString, depender.toString) :: edges
    return edges.reverse

def collectImportEdges (env : Lean.Environment) (roots : Array Name) :
    List (String × String) × List String :=
  Id.run do
    let mut edges : List (String × String) := []
    let mut imports : List String := []
    let mut seenImp : NameSet := {}
    let mut seenEdge : NameSet := {}
    let moduleNames := env.allImportedModuleNames
    for h : i in [0:moduleNames.size] do
      let importing := moduleNames[i]'h.upper
      if !Modules.isProjectModule roots importing then
        continue
      let some data := env.header.moduleData[i]? | continue
      for imp in data.imports do
        let imported := imp.module
        let key := Name.mkStr imported importing.toString
        if !seenEdge.contains key then
          seenEdge := seenEdge.insert key
          edges := (imported.toString, importing.toString) :: edges
        if Modules.isProjectModule roots imported && !seenImp.contains imported then
          seenImp := seenImp.insert imported
          imports := imported.toString :: imports
    return (edges.reverse, imports.reverse)

/-- Build one declaration JSON object (axioms supplied by caller). -/
def declJsonWithAxioms (name : Name) (info : ConstantInfo) (axioms : List String) : String :=
  let kind := kindOf info
  let module :=
    let p := name.getPrefix.toString
    if p == "[anonymous]" then name.toString else p
  let typePretty := toString info.type
  let typeHash := toString (hash typePretty)
  let path := sourcePathGuess module
  let pathField := if path.isEmpty then "null" else Json.str path
  Json.object [
    ("fqn", Json.str name.toString),
    ("kind", Json.str kind),
    ("module", Json.str module),
    ("source_path", pathField),
    ("source_start_line", "null"),
    ("source_start_column", "null"),
    ("public_visibility", Json.str "public"),
    ("type_pretty", Json.str typePretty),
    ("type_expr_hash", Json.str typeHash),
    ("value_expr_hash", "null"),
    ("universe_params", Json.strArray []),
    ("attributes", Json.strArray []),
    ("axioms_used", Json.strArray axioms)
  ]

def completenessJson (allImported : Bool) : String :=
  Json.object [
    ("environment_loaded", Json.bool true),
    ("all_project_modules_imported", Json.bool allImported),
    ("declaration_types_complete", Json.bool true),
    ("declaration_values_available_where_exposed", Json.bool true),
    ("axiom_collection_complete_for_loaded_environment", Json.bool true),
    ("source_positions_complete", Json.bool false),
    ("known_limitations", Json.strArray [
      "source positions not available from Environment constants",
      "attributes not collected in v0 generic extractor",
      "tactic-erased intermediate constants are invisible",
      "opaque/axiom bodies expose only stored Lean values"
    ])
  ]

def buildPayload
    (env : Lean.Environment)
    (roots : Array Name)
    (snapshotFingerprint : String)
    (leanVersion : String)
    (lakeVersion : String)
    (toolchainSpec : String)
    (allModulesImported : Bool) : String :=
  let decls := collectDeclarations env roots
  let declEdges := collectDeclEdges decls
  let (importEdges, projectImports) := collectImportEdges env roots
  let declJsons := decls.map fun (n, i) =>
    let axs := (axiomsOf env n).toList.map (·.toString)
    declJsonWithAxioms n i axs
  let declEdgeJsons := declEdges.map fun (a, b) => Json.edge a b
  let importEdgeJsons := importEdges.map fun (a, b) => Json.importEdge a b
  let moduleJsons :=
    projectImports.map fun m =>
      Json.object [
        ("name", Json.str m),
        ("source_path", Json.str (sourcePathGuess m)),
        ("imported", Json.bool true)
      ]
  let axiomsByDeclFields :=
    decls.map fun (n, _) =>
      let axs := (axiomsOf env n).toList.map (·.toString)
      (n.toString, Json.strArray axs)
  let axiomsObj :=
    "{" ++ ", ".intercalate (axiomsByDeclFields.map fun (k, v) => Json.str k ++ ": " ++ v) ++ "}"
  Json.object [
    ("schema_version", Json.str Protocol.schemaVersion),
    ("snapshot_fingerprint", Json.str snapshotFingerprint),
    ("lean_version", Json.str leanVersion),
    ("lake_version", Json.str lakeVersion),
    ("toolchain_spec", Json.str toolchainSpec),
    ("imported_modules", "[" ++ ", ".intercalate moduleJsons ++ "]"),
    ("declarations", "[" ++ ", ".intercalate declJsons ++ "]"),
    ("declaration_dependency_edges", "[" ++ ", ".intercalate declEdgeJsons ++ "]"),
    ("import_edges", "[" ++ ", ".intercalate importEdgeJsons ++ "]"),
    ("axioms_by_declaration", axiomsObj),
    ("placeholders", "[]"),
    ("errors", "[]"),
    ("completeness", completenessJson allModulesImported),
    ("extractor", Json.str Protocol.extractorId),
    ("extractor_version", Json.str Protocol.extractorVersion),
    ("notes", Json.strArray [
      "emitted by lean.generic-inject (Environment IR)",
      "declaration edges from ConstantInfo.getUsedConstantsAsSet",
      "import edges from Environment ModuleData"
    ])
  ]

end LpeExtract.Environment
