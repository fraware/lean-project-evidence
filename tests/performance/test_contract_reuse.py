"""Assert optional contract= reuse skips a second filesystem load."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from lpe.contract.loader import load_contract
from lpe.evidence.compiler import compile_evidence
from lpe.models import CandidateDescriptor


@pytest.mark.performance
def test_compile_reuses_preloaded_contract(
    example_project: Path,
    example_candidate: CandidateDescriptor,
) -> None:
    contract = load_contract(example_project)
    with patch("lpe.evidence.compiler.load_contract") as mocked:
        packet = compile_evidence(
            example_project,
            example_candidate,
            skip_build=True,
            contract=contract,
        )
        mocked.assert_not_called()
    assert packet.contract_hash == contract.contract_hash
