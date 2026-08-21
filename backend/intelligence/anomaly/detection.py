"""INT-05: statistical anomaly detection — no ML model. Three signals against a 14-day baseline
(rolling z-score, rolling deviation, percentage change), each computed against an STL-deseasonalized
series where enough history exists, so a routine weekly dip/peak doesn't get flagged as an anomaly.
An anomaly is raised if any signal crosses its threshold; the returned record's `baseline`/`recent`/
`percentChange` match `get_anomalies`'s frozen shape exactly."""

import pandas as pd
from statsmodels.tsa.seasonal import STL

from backend.intelligence.forecasting.models import SEASONAL_PERIOD, STL_MIN_OBSERVATIONS

BASELINE_WINDOW_DAYS = 14
RECENT_WINDOW_DAYS = 3
PERCENT_CHANGE_THRESHOLD = 40.0
ZSCORE_THRESHOLD = 2.5
CUSUM_SLACK_STDS = 0.5  # per-day deviation smaller than this (in baseline stds) is treated as noise, not drift
CUSUM_THRESHOLD_STDS = 5.0  # cumulative deviation must clear this many baseline stds before drift is confirmed, so it only fires on a sustained trend, not a one-off swing already caught by detect_anomaly


def _deseasonalized(series: pd.Series) -> pd.Series:
    if len(series) < STL_MIN_OBSERVATIONS:
        return series
    stl = STL(series, period=SEASONAL_PERIOD, robust=True).fit()
    return series - stl.seasonal


def detect_anomaly(series: pd.Series) -> dict | None:
    if len(series) < RECENT_WINDOW_DAYS:
        return None

    deseasonalized = _deseasonalized(series)
    baseline_window = deseasonalized.iloc[-BASELINE_WINDOW_DAYS:] if len(deseasonalized) >= BASELINE_WINDOW_DAYS else deseasonalized
    baseline = float(baseline_window.mean())
    recent = float(deseasonalized.iloc[-RECENT_WINDOW_DAYS:].mean())

    std = float(baseline_window.std(ddof=0))
    zscore = (recent - baseline) / std if std > 0 else 0.0
    rolling_deviation = abs(recent - baseline)
    percent_change = (recent - baseline) / abs(baseline) * 100 if baseline != 0 else 0.0

    triggered = (
        abs(percent_change) >= PERCENT_CHANGE_THRESHOLD
        or abs(zscore) >= ZSCORE_THRESHOLD
        or (baseline > 0 and rolling_deviation >= baseline)
    )
    if not triggered:
        return None

    return {"baseline": round(baseline, 2), "recent": round(recent, 2), "percentChange": round(percent_change, 1)}


def detect_drift(series: pd.Series) -> dict | None:
    """CUSUM control chart: catches a slow, sustained drift (e.g. ~2-3%/day consumption creep)
    that never trips detect_anomaly's single-day thresholds. Uses the earliest BASELINE_WINDOW_DAYS
    of the (STL-deseasonalized) series as the stable reference, then walks the remaining days
    accumulating deviation from that reference; a run of small daily deviations in the same
    direction eventually crosses CUSUM_THRESHOLD_STDS even though no single day does."""
    if len(series) < BASELINE_WINDOW_DAYS + 2:
        return None

    deseasonalized = _deseasonalized(series)
    baseline_window = deseasonalized.iloc[:BASELINE_WINDOW_DAYS]
    baseline_mean = float(baseline_window.mean())
    std = float(baseline_window.std(ddof=0))
    if std == 0:
        return None

    slack = CUSUM_SLACK_STDS * std
    threshold = CUSUM_THRESHOLD_STDS * std

    cumulative_up = 0.0
    cumulative_down = 0.0
    for offset, value in enumerate(deseasonalized.iloc[BASELINE_WINDOW_DAYS:], start=1):
        cumulative_up = max(0.0, cumulative_up + (value - baseline_mean - slack))
        cumulative_down = max(0.0, cumulative_down + (baseline_mean - value - slack))

        if cumulative_up >= threshold:
            return {"type": "DRIFT", "direction": "UP", "detectedAtDayOffset": offset, "cumulativeDeviation": round(cumulative_up, 2)}
        if cumulative_down >= threshold:
            return {"type": "DRIFT", "direction": "DOWN", "detectedAtDayOffset": offset, "cumulativeDeviation": round(cumulative_down, 2)}

    return None
