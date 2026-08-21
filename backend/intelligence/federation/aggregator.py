"""INT-11: combine every participating national node's INT-10 submission into one shared BRICS
reference profile via sample-weighted averaging (`sum(metric * samples) / sum(samples)`), with a
robust trimmed mean for metrics that swing more between nodes."""

import numpy as np

from backend.intelligence.federation.local_params import FIELDS

UNSTABLE_FIELDS = {"demand_trend", "forecast_bias", "surge_multiplier"}
TRIM_FRACTION = 0.2


def _weighted_average(values: list[float], weights: list[int]) -> float:
    total_weight = sum(weights)
    return float(sum(v * w for v, w in zip(values, weights)) / total_weight) if total_weight else 0.0


def _trimmed_mean(values: list[float], *, fraction: float = TRIM_FRACTION) -> float:
    if not values:
        return 0.0
    arr = np.sort(np.array(values, dtype=float))
    cut = int(len(arr) * fraction)
    trimmed = arr[cut : len(arr) - cut] if len(arr) - 2 * cut > 0 else arr
    return float(np.mean(trimmed))


def aggregate_reference_profile(submissions: list[dict]) -> dict:
    """`submissions`: one dict per participating country, each holding exactly the 11 `FIELDS`
    plus a `samples` weight (INT-10's output). Returns the same 11 fields aggregated across every
    submission — this function never sees, and could not leak, a raw PHC-level record."""
    weights = [s["samples"] for s in submissions]
    return {
        field: (
            _trimmed_mean([s[field] for s in submissions])
            if field in UNSTABLE_FIELDS
            else _weighted_average([s[field] for s in submissions], weights)
        )
        for field in FIELDS
    }
