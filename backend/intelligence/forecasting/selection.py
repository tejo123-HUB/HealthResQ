"""INT-01: rolling-origin cross-validated auto-selection across the candidate models in
`forecasting.models`, by MASE. The MASE naive-scale denominator is pinned to seasonal-naive
(period=7), computed on the training fold only — not the full series — so it's reproducible and
never leaks test-fold information into the metric."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.intelligence.forecasting.models import (
    CANDIDATE_FNS,
    FLOOR_MIN_OBSERVATIONS,
    SEASONAL_PERIOD,
    STL_MIN_OBSERVATIONS,
    CandidateResult,
    recent_average_forecast,
)
from backend.intelligence.models import ForecastModel

CV_FOLDS = 3
CV_HORIZON = 7


@dataclass
class CandidateMetric:
    model: ForecastModel
    eligible: bool
    cv_mase: float | None
    selected: bool = False


@dataclass
class SelectionResult:
    chosen: CandidateResult
    metrics: list[CandidateMetric]


def _seasonal_naive_scale(train: np.ndarray, period: int = SEASONAL_PERIOD) -> float:
    if len(train) <= period:
        diffs = np.abs(np.diff(train))
    else:
        diffs = np.abs(train[period:] - train[:-period])
    scale = float(np.mean(diffs)) if len(diffs) else 0.0
    return scale if scale > 0 else 1.0


def _is_eligible(model: ForecastModel, n_obs: int) -> bool:
    if model == ForecastModel.DECOMPOSABLE:
        return n_obs >= STL_MIN_OBSERVATIONS
    return n_obs >= FLOOR_MIN_OBSERVATIONS


def _cv_mase(model: ForecastModel, series: pd.Series) -> float | None:
    fold_errors = []
    n = len(series)
    for fold in range(CV_FOLDS):
        cutoff = n - CV_HORIZON * (CV_FOLDS - fold)
        if cutoff < FLOOR_MIN_OBSERVATIONS:
            continue
        train = series.iloc[:cutoff]
        test = series.iloc[cutoff : cutoff + CV_HORIZON]
        if len(test) < CV_HORIZON or not _is_eligible(model, len(train)):
            continue
        try:
            result = CANDIDATE_FNS[model](train, CV_HORIZON)
        except Exception:
            continue
        mae = float(np.mean(np.abs(test.to_numpy() - result.point[: len(test)])))
        scale = _seasonal_naive_scale(train.to_numpy())
        fold_errors.append(mae / scale)
    return float(np.mean(fold_errors)) if fold_errors else None


def select_and_forecast(series: pd.Series, horizon_days: int) -> SelectionResult:
    """Full history's observation count decides the floor case; otherwise every eligible candidate
    is cross-validated and the lowest-MASE one is refit on the *entire* series for the real
    forecast returned to the caller."""
    n_obs = len(series)
    if n_obs < FLOOR_MIN_OBSERVATIONS:
        chosen = recent_average_forecast(series, horizon_days)
        return SelectionResult(
            chosen=chosen,
            metrics=[CandidateMetric(model=ForecastModel.RECENT_AVERAGE, eligible=True, cv_mase=None, selected=True)],
        )

    metrics: list[CandidateMetric] = []
    best_model: ForecastModel | None = None
    best_mase = np.inf
    for model in (ForecastModel.SARIMA, ForecastModel.STATE_SPACE, ForecastModel.DECOMPOSABLE):
        eligible = _is_eligible(model, n_obs)
        cv_mase = _cv_mase(model, series) if eligible else None
        metrics.append(CandidateMetric(model=model, eligible=eligible and cv_mase is not None, cv_mase=cv_mase))
        if cv_mase is not None and cv_mase < best_mase:
            best_mase, best_model = cv_mase, model

    if best_model is None:
        chosen = recent_average_forecast(series, horizon_days)
        metrics.append(CandidateMetric(model=ForecastModel.RECENT_AVERAGE, eligible=True, cv_mase=None, selected=True))
        return SelectionResult(chosen=chosen, metrics=metrics)

    for metric in metrics:
        metric.selected = metric.model == best_model
    chosen = CANDIDATE_FNS[best_model](series, horizon_days)
    return SelectionResult(chosen=chosen, metrics=metrics)
