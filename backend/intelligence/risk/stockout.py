"""INT-04: `projected_stock(t) = current_stock + expected_incoming(t) - forecast_consumption(t)`
per facility-resource pair, classified Normal / Watch (<=7d) / High (<=3d) / Critical (<=48h)
against fixed day thresholds. Pure function of its inputs — no randomness, no wall-clock read —
so the same forecast always yields the same severity (the INT-04 acceptance criterion)."""

import numpy as np

from backend.intelligence.models import Severity

CRITICAL_DAYS = 2  # 48 hours
HIGH_DAYS = 3
WATCH_DAYS = 7


def project_stock(current_stock: int, expected_incoming: np.ndarray, forecast_consumption: np.ndarray) -> np.ndarray:
    """Cumulative projected stock for every day in the horizon."""
    cumulative_incoming = np.cumsum(expected_incoming)
    cumulative_consumption = np.cumsum(forecast_consumption)
    return current_stock + cumulative_incoming - cumulative_consumption


def first_stockout_day(projected: np.ndarray) -> int | None:
    """1-indexed day the projection first reaches zero or below, or None if it never does within
    the horizon."""
    below_zero = np.where(projected <= 0)[0]
    return int(below_zero[0]) + 1 if len(below_zero) else None


def classify_severity(days_to_stockout: int | None) -> Severity:
    if days_to_stockout is None:
        return Severity.NORMAL
    if days_to_stockout <= CRITICAL_DAYS:
        return Severity.CRITICAL
    if days_to_stockout <= HIGH_DAYS:
        return Severity.HIGH
    if days_to_stockout <= WATCH_DAYS:
        return Severity.WATCH
    return Severity.NORMAL
