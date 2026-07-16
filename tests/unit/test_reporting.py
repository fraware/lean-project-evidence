from __future__ import annotations

from lpe.evidence.compiler import compile_evidence
from lpe.reporting.markdown import render_packet


def test_markdown_includes_provenance(example_project, example_candidate) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    md = render_packet(packet)
    assert "Input hash:" in md
    assert packet.packet_id in md
    assert "Recommendation reasons" in md
    for finding in packet.findings:
        assert finding.check_id in md


def test_markdown_omits_injected_build_logs(example_project, example_candidate) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    for finding in packet.findings:
        if finding.check_id == "lean.build":
            finding.details["stdout"] = "SECRET_BUILD_LOG_BODY" * 100
            finding.details["stderr"] = "SECRET_BUILD_ERR_BODY" * 100
            break
    md = render_packet(packet)
    assert "SECRET_BUILD_LOG_BODY" not in md
    assert "bytes omitted" in md
