"""Shared timing / sizing helpers and optional metrics artifact writer."""

from __future__ import annotations

import json
import os
import statistics
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tests.performance.budgets import budget_snapshot

# Session accumulator; written when LPE_RECORD_BENCHMARKS=1.
_RECORDED: dict[str, Any] = {}


def record(name: str, value: float | int, *, unit: str, notes: str = "") -> None:
    _RECORDED[name] = {
        "value": value,
        "unit": unit,
        "notes": notes,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def recorded_metrics() -> dict[str, Any]:
    return dict(_RECORDED)


@contextmanager
def timed() -> Iterator[list[float]]:
    """Yield a one-element list that receives elapsed seconds on exit."""
    slot: list[float] = []
    started = time.perf_counter()
    try:
        yield slot
    finally:
        slot.append(time.perf_counter() - started)


def percentile(sorted_or_raw: list[float], p: float) -> float:
    if not sorted_or_raw:
        raise ValueError("empty sample")
    data = sorted(sorted_or_raw)
    if len(data) == 1:
        return data[0]
    # Nearest-rank style for small n (CI-friendly).
    k = max(0, min(len(data) - 1, round((p / 100.0) * (len(data) - 1))))
    return data[k]


def summarize_latencies(samples: list[float]) -> dict[str, float]:
    return {
        "n": float(len(samples)),
        "mean_s": statistics.fmean(samples),
        "p50_s": percentile(samples, 50),
        "p95_s": percentile(samples, 95),
        "max_s": max(samples),
    }


_LOG_KEYS = frozenset({"stdout", "stderr"})


def packet_json_bytes_excluding_logs(packet_json: str) -> int:
    """Count packet JSON size with build log bodies removed (§17 excl. logs)."""
    payload = json.loads(packet_json)
    for finding in payload.get("findings", []):
        details = finding.get("details")
        if not isinstance(details, dict):
            continue
        for key in _LOG_KEYS:
            if key in details and isinstance(details[key], str):
                details[key] = ""
    return len(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def maybe_write_benchmark_artifact(repository_root: Path) -> Path | None:
    """Write ``benchmarks/latest.json`` when ``LPE_RECORD_BENCHMARKS=1``."""
    if os.environ.get("LPE_RECORD_BENCHMARKS", "").lower() not in {"1", "true", "yes"}:
        return None
    if not _RECORDED:
        return None
    out_dir = repository_root / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "latest.json"
    document = {
        "schema_version": "0.1.0",
        "suite": "week3-performance",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology": (
            "Wall times via time.perf_counter; soft CI ceiling is 2x ENGINEERING_SPEC "
            "§17 hard targets. Ledger N=100/1000 only (100k is Week 4). Docker cold-start "
            "optional via @pytest.mark.docker."
        ),
        "budgets": budget_snapshot(),
        "metrics": _RECORDED,
    }
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path
