"""Anti-oversell honesty surfaces (NON_CLAIMS, research gates, Lean status).

Engineering enforcement for claims that must not be made until ENGINEERING_SPEC
§21 clears: causal TPPR from dry-runs, Mathlib-scale elaborator truth, R3/R4
production ACCEPT, and M6/M7 training (EPIC-039/040).
"""

from lpe.honesty.adr import adr_0003_status
from lpe.honesty.lean_status import lean_extractor_status
from lpe.honesty.non_claims import (
    NON_CLAIMS_ITEMS,
    NON_CLAIMS_MARKDOWN,
    OversellClaimError,
    format_non_claims_block,
    refuse_oversell_flags,
)
from lpe.honesty.research_gates import (
    RESEARCH_GATE_MATRIX,
    ResearchGateBlocked,
    format_research_status,
    refuse_research_entrypoint,
)

__all__ = [
    "NON_CLAIMS_ITEMS",
    "NON_CLAIMS_MARKDOWN",
    "OversellClaimError",
    "RESEARCH_GATE_MATRIX",
    "ResearchGateBlocked",
    "adr_0003_status",
    "format_non_claims_block",
    "format_research_status",
    "lean_extractor_status",
    "refuse_oversell_flags",
    "refuse_research_entrypoint",
]
