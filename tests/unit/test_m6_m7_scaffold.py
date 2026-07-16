from __future__ import annotations

from lpe.routing.baseline import DeterministicRoutingBaseline
from lpe.synthesis.eval_harness import SynthesisEvalCase, SynthesisEvalHarness
import pytest

from lpe.honesty.research_gates import ResearchGateBlocked


def test_deterministic_routing_orders_semantic_first() -> None:
    baseline = DeterministicRoutingBaseline()
    decision = baseline.route(unresolved_dimensions=["kernel", "semantic", "downstream"])
    assert decision.question_priority[0] == "semantic"
    assert decision.baseline_id == DeterministicRoutingBaseline.BASELINE_ID
    assert "not a learned policy" in decision.rationale.lower() or "§21" in decision.rationale


def test_synthesis_harness_fixture_eval() -> None:
    harness = SynthesisEvalHarness()
    results = harness.evaluate(
        [
            SynthesisEvalCase(
                case_id="held-out-1",
                baseline_tppr=0.5,
                synthesis_tppr=0.6,
                budget_tokens=1000,
            )
        ]
    )
    assert results[0].beats_baseline is True
    assert results[0].fixture_harness_ok is True
    assert "no model training" in results[0].note.lower()
    assert "gate_passed" not in results[0].__dataclass_fields__
    assert harness.training_blocked_reason
    assert "training entrypoint" in harness.training_blocked_reason.lower() or "§21" in (
        harness.training_blocked_reason
    )


def test_m6_m7_training_entrypoints_do_not_exist() -> None:
    """Engineering enforcement: train() must not succeed before §21."""
    with pytest.raises(ResearchGateBlocked):
        DeterministicRoutingBaseline().train()
    with pytest.raises(ResearchGateBlocked):
        SynthesisEvalHarness().train()
