from __future__ import annotations

from lpe.routing.baseline import DeterministicRoutingBaseline
from lpe.synthesis.eval_harness import SynthesisEvalCase, SynthesisEvalHarness


def test_deterministic_routing_orders_semantic_first() -> None:
    baseline = DeterministicRoutingBaseline()
    decision = baseline.route(unresolved_dimensions=["kernel", "semantic", "downstream"])
    assert decision.question_priority[0] == "semantic"


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
