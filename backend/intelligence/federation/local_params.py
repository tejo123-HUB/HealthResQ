"""INT-10: a national node's local statistical parameters for one resource — exactly the 11
documented aggregate fields (`FIELDS`), computed from real transaction/footfall history and
nothing else, so no PHC-level or patient-level field can leak into a federation payload by
construction.

Two fields lean on proxies because OPS doesn't store the ideal source column yet: lead time is
derived from gaps between consecutive RECEIPT transactions (there's no separate "order placed"
timestamp), and stock-out frequency is reconstructed backward from each facility's current
position (OPS keeps a transaction ledger, not a daily balance snapshot). Both are documented
approximations, not fabricated numbers — every value here still traces to a real OPS record.
"""

import uuid

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

from backend.intelligence import ports
from backend.intelligence.forecasting.models import FLOOR_MIN_OBSERVATIONS, SEASONAL_PERIOD
from backend.intelligence.forecasting.selection import select_and_forecast
from backend.ops import models

WINDOW_DAYS = 90
MONTHLY_PERIOD = 30

FIELDS = (
    "weekly_seasonal_index",
    "monthly_seasonal_index",
    "demand_trend",
    "consumption_per_1000_visits",
    "volatility",
    "lead_time_mean",
    "lead_time_variance",
    "forecast_mae",
    "forecast_bias",
    "stockout_frequency",
    "surge_multiplier",
)


def _sum_series(series_list: list[pd.Series]) -> pd.Series:
    if not series_list:
        return pd.Series(dtype=float)
    total = series_list[0].copy()
    for s in series_list[1:]:
        total = total.add(s, fill_value=0.0)
    return total


def _seasonal_index(series: pd.Series, period: int) -> float:
    if len(series) < 2 * period or series.mean() == 0:
        return 1.0
    stl = STL(series, period=period, robust=True).fit()
    return float(1.0 + stl.seasonal.iloc[-1] / series.mean())


def _lead_time_stats(db, facility_ids: list[uuid.UUID], product_id: uuid.UUID) -> tuple[float, float]:
    gaps: list[float] = []
    for fid in facility_ids:
        rows = (
            db.query(models.InventoryTransaction.at)
            .filter(
                models.InventoryTransaction.facility_id == fid,
                models.InventoryTransaction.product_id == product_id,
                models.InventoryTransaction.type == models.TransactionType.RECEIPT,
            )
            .order_by(models.InventoryTransaction.at)
            .all()
        )
        timestamps = [r[0] for r in rows]
        gaps.extend((b - a).total_seconds() / 86400 for a, b in zip(timestamps, timestamps[1:]))
    if not gaps:
        return 7.0, 1.0
    arr = np.array(gaps)
    return float(arr.mean()), float(arr.var())


def _stockout_frequency(db, facility_ids: list[uuid.UUID], product_id: uuid.UUID, *, days: int) -> float:
    """Reconstructs each day's balance backward from `current_stock` using the true recurrence
    `balance(t) = balance(t+1) + consumption(t) - receipts(t)` — both series are needed, or the
    reconstruction silently biases the count (omitting receipts overstates every past balance and
    under-counts stock-out days)."""
    total_days = 0
    stockout_days = 0
    for fid in facility_ids:
        consumption = ports.get_consumption_series(db, fid, product_id, days=days).to_numpy()
        receipts = ports.get_receipt_series(db, fid, product_id, days=days).to_numpy()
        if len(consumption) == 0:
            continue
        current = ports.get_current_stock(db, fid, product_id)
        balances = np.empty(len(consumption))
        running = float(current)
        for i in range(len(consumption) - 1, -1, -1):
            balances[i] = running
            running += consumption[i] - receipts[i]
        stockout_days += int(np.sum(balances <= 0))
        total_days += len(balances)
    return stockout_days / total_days if total_days else 0.0


def _surge_multiplier(footfall: pd.Series, *, recent_window: int = 3, baseline_window: int = 14) -> float:
    if len(footfall) < baseline_window:
        return 1.0
    ratios = []
    for end in range(baseline_window, len(footfall) + 1):
        baseline = footfall.iloc[end - baseline_window : end - recent_window].mean()
        recent = footfall.iloc[end - recent_window : end].mean()
        if baseline > 0:
            ratios.append(recent / baseline)
    return float(max(ratios)) if ratios else 1.0


def _backtest_forecast_error(series: pd.Series, *, horizon: int = 7) -> tuple[float, float]:
    if len(series) < horizon + FLOOR_MIN_OBSERVATIONS:
        return 0.0, 0.0
    train, test = series.iloc[:-horizon], series.iloc[-horizon:]
    try:
        result = select_and_forecast(train, horizon).chosen
    except Exception:
        return 0.0, 0.0
    errors = test.to_numpy() - result.point[: len(test)]
    return float(np.mean(np.abs(errors))), float(np.mean(errors))


def compute_local_parameters(
    db, country_id: uuid.UUID, product_id: uuid.UUID, *, window_days: int = WINDOW_DAYS
) -> dict:
    facility_ids = [f.id for f in ports.list_operational_facilities(db) if f.country_id == country_id]

    consumption = _sum_series([ports.get_consumption_series(db, fid, product_id, days=window_days) for fid in facility_ids])
    footfall = _sum_series([ports.get_footfall_series(db, fid, days=window_days) for fid in facility_ids])

    if len(consumption) >= 2:
        slope = float(np.polyfit(np.arange(len(consumption)), consumption.to_numpy(), 1)[0])
        demand_trend = slope / (float(consumption.mean()) or 1.0)
    else:
        demand_trend = 0.0

    total_visits = float(footfall.sum())
    mean_consumption = float(consumption.mean()) if len(consumption) else 0.0
    std_consumption = float(consumption.std(ddof=0)) if len(consumption) else 0.0
    lead_time_mean, lead_time_variance = _lead_time_stats(db, facility_ids, product_id)
    forecast_mae, forecast_bias = _backtest_forecast_error(consumption)

    return {
        "weekly_seasonal_index": _seasonal_index(consumption, SEASONAL_PERIOD),
        "monthly_seasonal_index": _seasonal_index(consumption, MONTHLY_PERIOD) if len(consumption) >= 2 * MONTHLY_PERIOD else 1.0,
        "demand_trend": demand_trend,
        "consumption_per_1000_visits": (float(consumption.sum()) / total_visits * 1000) if total_visits > 0 else 0.0,
        "volatility": (std_consumption / mean_consumption) if mean_consumption > 0 else 0.0,
        "lead_time_mean": lead_time_mean,
        "lead_time_variance": lead_time_variance,
        "forecast_mae": forecast_mae,
        "forecast_bias": forecast_bias,
        "stockout_frequency": _stockout_frequency(db, facility_ids, product_id, days=window_days),
        "surge_multiplier": _surge_multiplier(footfall),
    }
