"""INT-03: package the point/range distinction `forecast_resource`'s frozen return shape needs,
plus the `range_source` provenance (model-native vs residual-based) that isn't part of that
frozen shape but must be recorded per-forecast."""

from dataclasses import dataclass

from backend.intelligence.forecasting.models import CandidateResult
from backend.intelligence.models import RangeSource


@dataclass
class ForecastRange:
    low: float
    high: float
    source: RangeSource


def total_range(result: CandidateResult) -> ForecastRange:
    """Sum of the per-day low/high across the whole horizon — what `forecast_resource`'s single
    `range` field reports for the horizon's total `forecastDemand`."""
    return ForecastRange(low=float(result.low.sum()), high=float(result.high.sum()), source=result.range_source)
