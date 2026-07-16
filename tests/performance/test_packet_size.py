"""Evidence compile --skip-build latency and packet JSON size (§17: < 1 MB excl. logs)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lpe.contract.loader import load_contract
from lpe.evidence.compiler import compile_evidence
from lpe.models import CandidateDescriptor
from tests.performance.budgets import assert_within_soft_budget
from tests.performance.metrics import (
    packet_json_bytes_excluding_logs,
    record,
    timed,
)


@pytest.mark.performance
def test_evidence_skip_build_latency_and_packet_size(
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
    compile_s = elapsed[0]
    record(
        "evidence_skip_build_s",
        compile_s,
        unit="s",
        notes="compile_evidence skip_build with preloaded contract",
    )
    assert_within_soft_budget("evidence_skip_build_s", compile_s)

    raw = packet.model_dump_json()
    raw_bytes = len(raw.encode("utf-8"))
    excl_logs = packet_json_bytes_excluding_logs(raw)
    record("packet_json_bytes", raw_bytes, unit="bytes", notes="full JSON")
    record(
        "packet_size_excl_logs_bytes",
        excl_logs,
        unit="bytes",
        notes="§17 packet size excluding stdout/stderr bodies",
    )
    assert_within_soft_budget("packet_size_excl_logs_bytes", float(excl_logs))
    assert packet.findings
