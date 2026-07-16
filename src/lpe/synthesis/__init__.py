"""Project-targeted synthesis eval harness (M7 scaffold).

**EPIC-040 blocked until ENGINEERING_SPEC §21 (and M6).** No model training
entrypoint exists in this package. ``SynthesisEvalHarness`` compares fixture
numbers only (AUDIT-031). Calling ``train`` raises ``ResearchGateBlocked``.
"""

from lpe.synthesis.eval_harness import (
    SynthesisEvalCase,
    SynthesisEvalHarness,
    SynthesisEvalResult,
    TrainingBlockedError,
)

__all__ = [
    "SynthesisEvalCase",
    "SynthesisEvalHarness",
    "SynthesisEvalResult",
    "TrainingBlockedError",
]
