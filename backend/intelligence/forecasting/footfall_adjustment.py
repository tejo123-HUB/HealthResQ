"""INT-02: scale a base consumption forecast by a clamped ratio of recent footfall to baseline
footfall — a facility with a footfall surge/drop gets a proportionally adjusted forecast, bounded
so a single noisy day can't blow the forecast up or down unrealistically."""

import numpy as np
import pandas as pd

RECENT_WINDOW_DAYS = 3
BASELINE_WINDOW_DAYS = 14
MIN_RATIO = 0.5
MAX_RATIO = 2.5


def footfall_adjustment_ratio(footfall_series: pd.Series) -> float:
    """1.0 (no adjustment) when there isn't enough footfall history for a meaningful baseline."""
    if len(footfall_series) < BASELINE_WINDOW_DAYS:
        return 1.0
    baseline = float(footfall_series.iloc[-BASELINE_WINDOW_DAYS:].mean())
    if baseline <= 0:
        return 1.0
    recent = float(footfall_series.iloc[-RECENT_WINDOW_DAYS:].mean())
    return float(np.clip(recent / baseline, MIN_RATIO, MAX_RATIO))


def apply_footfall_adjustment(point: np.ndarray, ratio: float) -> np.ndarray:
    return point * ratio
