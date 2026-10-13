#!/usr/bin/env python3
"""Bounded spot checks of the *exact arithmetic equations* of PR #533.

This is deliberately NOT a formal proof or cryptographic test. The authoritative
source is leanEthereum/leanVM@4a5a6cf0, file
verification/leanxmss/LeanxmssProofs/Encoding.lean, lemmas fold6 and fold12.

Run: python3 execution/probes/leanvm_pr533_encoding_arithmetic_probe.py
"""

from __future__ import annotations

import random

SEED = 20261013
ROUNDS = 200_000
LOW6 = 17311559823019733055


def val(base: int, digits: list[int]) -> int:
    return sum(digit * (base**index) for index, digit in enumerate(digits))


def fold6_sides(c: list[int]) -> tuple[int, int]:
    """Exactly the proof target; 0 <= c[0:10] < 64, 0 <= c[10] < 16."""
    assert len(c) == 11 and all(0 <= digit < 64 for digit in c[:10])
    assert 0 <= c[10] < 16
    x = val(64, c)
    lhs = (x & LOW6) + ((x >> 6) & LOW6)
    rhs = val(4096, [c[2 * i] + c[2 * i + 1] for i in range(5)] + [c[10]])
    return lhs, rhs


def fold12_sides(e: list[int]) -> tuple[int, int]:
    """Exactly the proof target; each 0 <= e_i <= 56."""
    assert len(e) == 6 and all(0 <= digit <= 56 for digit in e)
    s1 = val(4096, e)
    s2 = s1 + (s1 >> 12)
    s3 = s2 + (s2 >> 24)
    return (s3 + (s3 >> 48)) & 4095, sum(e)


def main() -> None:
    rng = random.Random(SEED)
    six_boundaries = [
        [0] * 11,
        [63] * 10 + [15],
        [0] * 10 + [15],
        [63 if i % 2 else 0 for i in range(10)] + [15],
    ]
    twelve_boundaries = [
        [0] * 6,
        [56] * 6,
        [56, 0, 56, 0, 56, 0],
        [0, 56, 0, 56, 0, 56],
    ]
    for c in six_boundaries:
        assert fold6_sides(c)[0] == fold6_sides(c)[1]
    for e in twelve_boundaries:
        assert fold12_sides(e)[0] == fold12_sides(e)[1]
    for _ in range(ROUNDS):
        c = [rng.randrange(64) for _ in range(10)] + [rng.randrange(16)]
        e = [rng.randrange(57) for _ in range(6)]
        assert fold6_sides(c)[0] == fold6_sides(c)[1]
        assert fold12_sides(e)[0] == fold12_sides(e)[1]
    print(
        f"OK: fold6 and fold12 each matched {ROUNDS + 4:,} "
        "seeded/boundary input assignments."
    )
    print("NOT A PROOF: finite samples do not establish the Lean statements universally.")


if __name__ == "__main__":
    main()
