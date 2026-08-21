"""INT-01's candidate forecasting models, statsmodels-only (no Prophet/pmdarima — both carry
fragile Windows install toolchains that a two-day build shouldn't risk). Every function returns a
`CandidateResult`: a point forecast for `horizon_days` plus a range and where that range came from
(model-native credible interval vs residual-based), so `forecasting.uncertainty` never has to guess.

Determinism (INT-04's "same input never yields two different severities" depends on it): no
function here introduces randomness — STL is deterministic LOESS, and SARIMAX/UnobservedComponents
use scipy's deterministic default optimizer, so refitting identical data twice reproduces identical
parameters."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.statespace.structural import UnobservedComponents

from backend.intelligence.models import ForecastModel, RangeSource

SEASONAL_PERIOD = 7
FLOOR_MIN_OBSERVATIONS = 7
STL_MIN_OBSERVATIONS = 2 * SEASONAL_PERIOD
SARIMA_SEASONAL_MIN_OBSERVATIONS = 3 * SEASONAL_PERIOD

_SARIMA_GRID = [
    ((1, 0, 0), (0, 0, 0, 0)),
    ((1, 1, 1), (0, 0, 0, 0)),
    ((1, 0, 0), (1, 0, 0, SEASONAL_PERIOD)),
    ((0, 1, 1), (0, 1, 1, SEASONAL_PERIOD)),
]


@dataclass
class CandidateResult:
    model: ForecastModel
    point: np.ndarray
    low: np.ndarray
    high: np.ndarray
    range_source: RangeSource


def recent_average_forecast(series: pd.Series, horizon_days: int) -> CandidateResult:
    """The <7-observation floor case: repeat the recent average, with a residual-based range from
    the same window's spread."""
    window = series.iloc[-min(len(series), FLOOR_MIN_OBSERVATIONS) :]
    avg = float(window.mean()) if len(window) else 0.0
    spread = float(window.std(ddof=0)) if len(window) > 1 else max(avg * 0.25, 1.0)
    point = np.full(horizon_days, avg)
    return CandidateResult(
        model=ForecastModel.RECENT_AVERAGE,
        point=point,
        low=np.clip(point - spread, 0, None),
        high=point + spread,
        range_source=RangeSource.RESIDUAL,
    )


def _best_sarima_order(train: pd.Series) -> tuple[tuple, tuple]:
    eligible_grid = _SARIMA_GRID if len(train) >= SARIMA_SEASONAL_MIN_OBSERVATIONS else _SARIMA_GRID[:2]
    best_order, best_aic = eligible_grid[0], np.inf
    for order, seasonal_order in eligible_grid:
        try:
            fitted = SARIMAX(
                train, order=order, seasonal_order=seasonal_order,
                enforce_stationarity=False, enforce_invertibility=False,
            ).fit(disp=False)
        except Exception:
            continue
        if fitted.aic < best_aic:
            best_aic, best_order = fitted.aic, (order, seasonal_order)
    return best_order


def sarima_forecast(train: pd.Series, horizon_days: int) -> CandidateResult:
    if len(train) < FLOOR_MIN_OBSERVATIONS:
        raise ValueError("insufficient history for SARIMA")
    order, seasonal_order = _best_sarima_order(train)
    fitted = SARIMAX(
        train, order=order, seasonal_order=seasonal_order,
        enforce_stationarity=False, enforce_invertibility=False,
    ).fit(disp=False)
    forecast = fitted.get_forecast(steps=horizon_days)
    frame = forecast.summary_frame(alpha=0.05)
    point = np.clip(frame["mean"].to_numpy(), 0, None)
    return CandidateResult(
        model=ForecastModel.SARIMA,
        point=point,
        low=np.clip(frame["mean_ci_lower"].to_numpy(), 0, None),
        high=np.clip(frame["mean_ci_upper"].to_numpy(), 0, None),
        range_source=RangeSource.MODEL_NATIVE,
    )


def state_space_forecast(train: pd.Series, horizon_days: int) -> CandidateResult:
    """Bayesian structural time-series / Kalman-filter local-level-trend-seasonal candidate
    (INT-01) — `UnobservedComponents`'s own forecast interval satisfies INT-03's model-native
    range requirement directly."""
    if len(train) < FLOOR_MIN_OBSERVATIONS:
        raise ValueError("insufficient history for state-space model")
    seasonal = SEASONAL_PERIOD if len(train) >= STL_MIN_OBSERVATIONS else None
    fitted = UnobservedComponents(train, level="local linear trend", seasonal=seasonal).fit(disp=False)
    forecast = fitted.get_forecast(steps=horizon_days)
    frame = forecast.summary_frame(alpha=0.05)
    point = np.clip(frame["mean"].to_numpy(), 0, None)
    return CandidateResult(
        model=ForecastModel.STATE_SPACE,
        point=point,
        low=np.clip(frame["mean_ci_lower"].to_numpy(), 0, None),
        high=np.clip(frame["mean_ci_upper"].to_numpy(), 0, None),
        range_source=RangeSource.MODEL_NATIVE,
    )


def decomposable_forecast(train: pd.Series, horizon_days: int) -> CandidateResult:
    """Decomposable additive (trend + seasonality + event-effect) candidate: STL decomposition,
    a linear-OLS trend extrapolation, and the last observed seasonal cycle tiled forward. No
    native interval, so the range comes from the decomposition residuals (INT-03's residual-based
    path)."""
    if len(train) < STL_MIN_OBSERVATIONS:
        raise ValueError("insufficient history for STL decomposition")
    stl = STL(train, period=SEASONAL_PERIOD, robust=True).fit()

    x = np.arange(len(train))
    slope, intercept = np.polyfit(x, stl.trend.to_numpy(), 1)
    future_x = np.arange(len(train), len(train) + horizon_days)
    trend_forecast = slope * future_x + intercept

    last_cycle = stl.seasonal.to_numpy()[-SEASONAL_PERIOD:]
    seasonal_forecast = np.tile(last_cycle, int(np.ceil(horizon_days / SEASONAL_PERIOD)))[:horizon_days]

    point = np.clip(trend_forecast + seasonal_forecast, 0, None)
    resid_std = float(stl.resid.std(ddof=0)) or max(float(train.mean()) * 0.1, 1.0)
    band = 1.28 * resid_std  # ~80% band from the residual distribution (INT-03 residual path)
    return CandidateResult(
        model=ForecastModel.DECOMPOSABLE,
        point=point,
        low=np.clip(point - band, 0, None),
        high=point + band,
        range_source=RangeSource.RESIDUAL,
    )


CANDIDATE_FNS = {
    ForecastModel.SARIMA: sarima_forecast,
    ForecastModel.STATE_SPACE: state_space_forecast,
    ForecastModel.DECOMPOSABLE: decomposable_forecast,
}
