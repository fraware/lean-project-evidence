from __future__ import annotations

import pytest

from lpe.models import Obligation, ObligationsFile


def _obligation(obligation_id: str, downstream: list[str]) -> Obligation:
    return Obligation(
        obligation_id=obligation_id,
        description="fixture obligation",
        artifact_type="definition",
        weight=1,
        milestone="m0",
        owner="tester",
        downstream=downstream,
    )


def test_obligations_reject_self_reference() -> None:
    with pytest.raises(ValueError, match="cannot depend downstream on itself"):
        ObligationsFile.model_validate(
            {
                "schema_version": "0.1.0",
                "obligations": [
                    _obligation("O-01", ["O-01"]).model_dump(mode="json"),
                ],
            }
        )


def test_obligations_reject_indirect_cycle() -> None:
    with pytest.raises(ValueError, match="cycle"):
        ObligationsFile.model_validate(
            {
                "schema_version": "0.1.0",
                "obligations": [
                    _obligation("O-01", ["O-02"]).model_dump(mode="json"),
                    _obligation("O-02", ["O-03"]).model_dump(mode="json"),
                    _obligation("O-03", ["O-01"]).model_dump(mode="json"),
                ],
            }
        )
