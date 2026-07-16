"""Diff classification wall time (§17: < 5 s for a normal PR)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lpe.contract.loader import load_contract
from lpe.git.candidate import build_candidate_from_commits
from tests.performance.budgets import assert_within_soft_budget
from tests.performance.metrics import record, timed


@pytest.mark.performance
def test_diff_classification_within_budget(
    lean_diff_repo: tuple[Path, str, str],
) -> None:
    repo, base, head = lean_diff_repo
    contract = load_contract(repo)

    with timed() as elapsed:
        candidate = build_candidate_from_commits(
            repo,
            contract,
            candidate_id="cand-perf-diff",
            project_id=contract.project.project_id,
            obligation_ids=["O-01"],
            base_commit=base,
            head_commit=head,
            claimed_intent="perf diff classification",
            generator={"generator_type": "test", "name": "perf", "version": "0"},
        )
    classify_s = elapsed[0]
    record(
        "diff_classify_s",
        classify_s,
        unit="s",
        notes="build_candidate_from_commits on 1-file Lean PR",
    )
    assert_within_soft_budget("diff_classify_s", classify_s)
    assert any(p.endswith("Comparison.lean") for p in candidate.changed_paths)
