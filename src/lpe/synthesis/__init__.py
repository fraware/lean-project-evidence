"""Project-targeted synthesis eval harness (M7 scaffold).

Gate-blocked: no model training. Fixture comparison only until
ENGINEERING_SPEC §21 science gates pass (AUDIT-031).
"""

from lpe.synthesis.eval_harness import SynthesisEvalCase, SynthesisEvalHarness, SynthesisEvalResult

__all__ = ["SynthesisEvalCase", "SynthesisEvalHarness", "SynthesisEvalResult"]
