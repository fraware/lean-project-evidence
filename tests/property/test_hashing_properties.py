"""Property-style hashing invariants (seeded / combinatorial; no Hypothesis required)."""

from __future__ import annotations

import random
from typing import Any

import pytest

from lpe.hashing import canonical_json, sha256_text, sha256_value


def _random_jsonable(rng: random.Random, depth: int = 0) -> Any:
    if depth > 3:
        return rng.choice([None, True, False, rng.randint(0, 100), rng.random(), "x"])
    kind = rng.randint(0, 4)
    if kind == 0:
        return {f"k{i}": _random_jsonable(rng, depth + 1) for i in range(rng.randint(0, 4))}
    if kind == 1:
        return [_random_jsonable(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    if kind == 2:
        return rng.randint(-(10**6), 10**6)
    if kind == 3:
        return rng.random()
    return rng.choice(["a", "b", "twin", ""])


@pytest.mark.parametrize("seed", range(25))
def test_canonical_json_stable_under_key_shuffle(seed: int) -> None:
    rng = random.Random(seed)
    payload = {
        "z": rng.randint(0, 10),
        "a": {"y": 1, "x": _random_jsonable(rng)},
        "m": [_random_jsonable(rng) for _ in range(3)],
    }
    keys = list(payload.keys())
    rng.shuffle(keys)
    shuffled = {k: payload[k] for k in keys}
    assert canonical_json(payload) == canonical_json(shuffled)
    assert sha256_value(payload) == sha256_value(shuffled)


@pytest.mark.parametrize("seed", range(15))
def test_sha256_value_matches_canonical_text(seed: int) -> None:
    rng = random.Random(seed + 100)
    value = _random_jsonable(rng)
    assert sha256_value(value) == sha256_text(canonical_json(value))
