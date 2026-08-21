import numpy as np
import pandas as pd
import pytest

from backend.intelligence.forecasting import models as fm
from backend.intelligence.forecasting.footfall_adjustment import MAX_RATIO, MIN_RATIO, footfall_adjustment_ratio
from backend.intelligence.forecasting.selection import select_and_forecast
from backend.intelligence.models import ForecastModel, RangeSource


def _synthetic_series(n: int = 60, *, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    days = np.arange(n)
    trend = 50 + 0.3 * days
    weekly = 10 * np.sin(2 * np.pi * days / 7)
    noise = rng.normal(0, 2, n)
    values = np.clip(trend + weekly + noise, 0, None)
    idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=n, freq="D")
    return pd.Series(values, index=idx)


def test_recent_average_floor_case_for_short_series():
    series = _synthetic_series(n=5)
    result = fm.recent_average_forecast(series, horizon_days=7)
    assert result.model == ForecastModel.RECENT_AVERAGE
    assert result.range_source == RangeSource.RESIDUAL
    assert len(result.point) == 7


def test_select_and_forecast_picks_non_recent_average_with_enough_history():
    """Guards against the fixture-depth failure mode: with 60 days of real weekly-seasonal
    history, at least one candidate other than the floor case must be selected."""
    series = _synthetic_series(n=60)
    selection = select_and_forecast(series, horizon_days=7)
    assert selection.chosen.model != ForecastModel.RECENT_AVERAGE
    assert sum(1 for m in selection.metrics if m.selected) == 1


def test_select_and_forecast_never_worse_than_other_eligible_candidates():
    series = _synthetic_series(n=60)
    selection = select_and_forecast(series, horizon_days=7)
    selected_mase = next(m.cv_mase for m in selection.metrics if m.selected)
    for metric in selection.metrics:
        if metric.eligible and metric.cv_mase is not None:
            assert selected_mase <= metric.cv_mase + 1e-9


def test_forecast_is_deterministic():
    series = _synthetic_series(n=60)
    first = select_and_forecast(series, horizon_days=7)
    second = select_and_forecast(series, horizon_days=7)
    assert first.chosen.model == second.chosen.model
    np.testing.assert_allclose(first.chosen.point, second.chosen.point)


def test_footfall_adjustment_ratio_clamped_on_surge():
    footfall = pd.Series([100.0] * 14)
    footfall.iloc[-3:] = 1000.0
    assert footfall_adjustment_ratio(footfall) == pytest.approx(MAX_RATIO)


def test_footfall_adjustment_ratio_clamped_on_drop():
    footfall = pd.Series([100.0] * 14)
    footfall.iloc[-3:] = 1.0
    assert footfall_adjustment_ratio(footfall) == pytest.approx(MIN_RATIO)


def test_footfall_adjustment_ratio_neutral_with_insufficient_history():
    footfall = pd.Series([100.0] * 5)
    assert footfall_adjustment_ratio(footfall) == 1.0
