from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SynthesisEvalCase:
    case_id: str
    baseline_tppr: float
    synthesis_tppr: float
    budget_tokens: int


@dataclass(frozen=True)
class SynthesisEvalResult:
    case_id: str
    beats_baseline: bool
    tppr_delta: float
    # Fixture-harness flag only — NOT ENGINEERING_SPEC §21 science-gate clearance
    # (AUDIT-031). Do not rename back to gate_passed.
    fixture_harness_ok: bool
    note: str


class SynthesisEvalHarness:
    """M7 scaffold: compare synthesis vs baseline on held-out fixture data.

    **Gate-blocked / no training (AUDIT-031):** this harness evaluates fixture
    numbers only. It does not train models and must not be read as §21 science
    gate clearance. Real training remains blocked until M6 utility outcomes and
    held-out gates pass.
    """

    HELD_OUT_GATE_MIN_DELTA = 0.0

    def evaluate(self, cases: list[SynthesisEvalCase]) -> list[SynthesisEvalResult]:
        results: list[SynthesisEvalResult] = []
        for case in cases:
            delta = case.synthesis_tppr - case.baseline_tppr
            beats = delta > self.HELD_OUT_GATE_MIN_DELTA
            results.append(
                SynthesisEvalResult(
                    case_id=case.case_id,
                    beats_baseline=beats,
                    tppr_delta=delta,
                    fixture_harness_ok=beats,
                    note=(
                        "Fixture-only evaluation; no model training performed; "
                        "fixture_harness_ok is not §21 science-gate clearance"
                        if beats
                        else "Synthesis did not beat baseline on held-out fixture"
                    ),
                )
            )
        return results

    @property
    def training_blocked_reason(self) -> str:
        return (
            "M7 synthesis training blocked until M6 learned routing demonstrates "
            "held-out TPPR improvement over deterministic baseline "
            "(ENGINEERING_SPEC §21). This scaffold performs no training."
        )
