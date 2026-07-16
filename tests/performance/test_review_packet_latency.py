"""Review packet (compile + markdown) latency and render size/time (§17: < 30 s)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lpe.contract.loader import load_contract
from lpe.evidence.compiler import compile_evidence
from lpe.models import CandidateDescriptor
from lpe.reporting.markdown import render_packet
from tests.performance.budgets import assert_within_soft_budget
from tests.performance.metrics import record, timed


@pytest.mark.performance
def test_review_packet_compile_and_markdown(
    example_project: Path,
    example_candidate: CandidateDescriptor,
) -> None:
    contract = load_contract(example_project)

    with timed() as elapsed:
        packet = compile_evidence(
            example_project,
            example_candidate,
            skip_build=True,
            contract=contract,
        )
        markdown = render_packet(packet)
    total_s = elapsed[0]
    record(
        "review_packet_s",
        total_s,
        unit="s",
        notes="skip_build compile + render_packet",
    )
    assert_within_soft_budget("review_packet_s", total_s)

    with timed() as elapsed:
        again = render_packet(packet)
    render_s = elapsed[0]
    md_bytes = len(again.encode("utf-8"))
    record("markdown_render_s", render_s, unit="s", notes="render_packet alone")
    record("markdown_bytes", md_bytes, unit="bytes", notes="UTF-8 markdown size")
    assert_within_soft_budget("markdown_render_s", render_s)
    assert "Evidence packet" in markdown
    # Logs omitted from markdown; size should stay modest for skip_build packets.
    assert md_bytes < 500_000
