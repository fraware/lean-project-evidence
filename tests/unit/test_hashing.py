from __future__ import annotations

import random
from typing import Any

import pytest

from lpe.hashing import canonical_json, sha256_file, sha256_text, sha256_value


@pytest.mark.parametrize("seed", range(5))
def test_sha256_value_is_invariant_under_key_reordering(seed: int) -> None:
    rng = random.Random(seed)
    keys = [f"key_{index}" for index in range(8)]
    rng.shuffle(keys)
    forward = {key: rng.randint(0, 100) for key in keys}
    reverse = dict(reversed(list(forward.items())))
    assert sha256_value(forward) == sha256_value(reverse)


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"a": 1, "b": [3, 2, 1]},
        {"nested": {"z": 1, "a": {"y": 2, "x": 3}}},
        ["list", {"b": 2, "a": 1}],
    ],
)
def test_canonical_json_is_stable_for_nested_structures(value: Any) -> None:
    first = canonical_json(value)
    second = canonical_json(value)
    assert first == second
    assert sha256_value(value) == sha256_text(first)


def test_sha256_text_is_deterministic() -> None:
    payload = "deterministic hashing fixture"
    assert sha256_text(payload) == sha256_text(payload)
    assert len(sha256_text(payload)) == 64


def test_sha256_file_matches_direct_hash(tmp_path) -> None:
    path = tmp_path / "payload.txt"
    path.write_text("ledger fixture", encoding="utf-8")
    assert sha256_file(path) == sha256_text("ledger fixture")
