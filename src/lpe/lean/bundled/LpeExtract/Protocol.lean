/-
  LPE generic extraction protocol constants (protocol v2).
-/
namespace LpeExtract.Protocol

/-- Extraction JSON schema / protocol version. -/
def schemaVersion : String := "2.0"

/-- Extractor identity claimed in emitted JSON. -/
def extractorId : String := "lean.generic-inject"

/-- Extractor package version. -/
def extractorVersion : String := "0.1.0"

/-- Error code when the target toolchain is outside the supported matrix. -/
def unsupportedToolchainCode : String := "UNSUPPORTED_TOOLCHAIN"

/-- Error code when module discovery is ambiguous. -/
def moduleDiscoveryAmbiguousCode : String := "MODULE_DISCOVERY_AMBIGUOUS"

end LpeExtract.Protocol
