from __future__ import annotations

import re

import pytest

from lpe.ids import new_id, stable_id, validate_id_format

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*_[0-9a-f]{32}$")


@pytest.mark.parametrize("prefix", ["run", "finding", "question", "event"])
def test_new_id_format_is_stable(prefix: str) -> None:
    identifier = new_id(prefix)
    assert ID_PATTERN.match(identifier)
    assert validate_id_format(identifier, prefix)


def test_new_id_values_differ_across_calls() -> None:
    first = new_id("run")
    second = new_id("run")
    assert first != second


def test_stable_id_is_deterministic_across_runs() -> None:
    material = "candidate:project:O-01:abc123"
    assert stable_id("artifact", material) == stable_id("artifact", material)


@pytest.mark.parametrize("prefix", ["artifact", "obligation", "packet"])
def test_stable_id_prefix_is_preserved(prefix: str) -> None:
    identifier = stable_id(prefix, "same-material")
    assert identifier.startswith(f"{prefix}_")
    assert validate_id_format(identifier, prefix)


def test_new_id_rejects_invalid_prefix() -> None:
    with pytest.raises(ValueError, match="prefix"):
        new_id("")
