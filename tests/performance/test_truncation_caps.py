"""Truncation caps hold under large build output (cost-reduction assert)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lpe.evidence.compiler import compile_evidence
from lpe.execution.runner import SubprocessLeanExecutor, _truncate
from lpe.models import CandidateDescriptor
from lpe.reporting.markdown import _details_for_markdown, render_packet
from tests.performance.metrics import record


@pytest.mark.performance
def test_truncate_respects_max_output_bytes() -> None:
    max_bytes = 8_192
    huge = "x" * (max_bytes * 10)
    out = _truncate(huge, max_bytes=max_bytes)
    encoded = out.encode("utf-8")
    assert len(encoded) <= max_bytes
    assert "truncated by lpe" in out
    record(
        "truncation_cap_bytes",
        max_bytes,
        unit="bytes",
        notes="asserted _truncate ceiling",
    )


@pytest.mark.performance
def test_subprocess_executor_truncates_stdout(tmp_path: Path) -> None:
    """Host executor applies max_output_bytes after redaction."""
    script = tmp_path / "spew.py"
    # Print ~200 KiB; cap at 4 KiB.
    script.write_text(
        "print('A' * 200_000)\n",
        encoding="utf-8",
    )
    executor = SubprocessLeanExecutor()
    # Use python as command — not allowlisted for Lean builds, but executor itself
    # does not enforce allowlist (compiler does). Direct unit call is fine.
    result = executor.verify_build(
        repository=tmp_path,
        command=["python", str(script.name)],
        timeout_seconds=30,
        max_output_bytes=4_096,
        environment_allowlist=["PATH", "HOME", "USER", "TMPDIR", "SYSTEMROOT"],
    )
    assert len(result.stdout.encode("utf-8")) <= 4_096
    assert "truncated by lpe" in result.stdout


@pytest.mark.performance
def test_markdown_omits_raw_build_logs(
    example_project: Path,
    example_candidate: CandidateDescriptor,
) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    # Inject synthetic logs as if a build ran (mutate details dict in place).
    injected = False
    for finding in packet.findings:
        if finding.check_id == "lean.build":
            finding.details["stdout"] = "LOG" * 50_000
            finding.details["stderr"] = "ERR" * 50_000
            finding.details["stdout_hash"] = "abc"
            finding.details["stderr_hash"] = "def"
            injected = True
            break
    assert injected

    md = render_packet(packet)
    assert "LOGLOG" not in md
    assert "bytes omitted" in md
    sanitized = _details_for_markdown(
        {"stdout": "x" * 10_000, "stderr": "y" * 10_000, "exit_code": 1}
    )
    assert "bytes omitted" in str(sanitized["stdout"])
    assert sanitized["exit_code"] == 1
    assert len(md.encode("utf-8")) < 200_000
