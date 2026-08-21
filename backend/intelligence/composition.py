"""Shared composition helper: builds and persists one `Forecast` (+ its `ForecastMetric`/
`ForecastPoint`/`Alert` rows) for a facility-product pair. Both `backend.intelligence.tools`
(the frozen tool functions) and `backend.intelligence.visualization` (the resource explorer's
on-demand drill-down) call this — kept in one place instead of two, so INT-01's cross-validation,
INT-02's footfall adjustment, INT-03's range-source tagging, and INT-12's cold-start fallback are
never implemented twice."""

import uuid

import numpy as np

from backend.intelligence import ports
from backend.intelligence.federation.cold_start import fallback_daily_rate, needs_fallback
from backend.intelligence.forecasting.footfall_adjustment import apply_footfall_adjustment, footfall_adjustment_ratio
from backend.intelligence.forecasting.selection import select_and_forecast
from backend.intelligence.models import Alert, FallbackLevel, Forecast, ForecastMetric, ForecastModel, ForecastPoint, RangeSource
from backend.intelligence.risk.stockout import classify_severity, first_stockout_day, project_stock


def build_forecast(db, facility_id: uuid.UUID, product_id: uuid.UUID, *, horizon_days: int = 14) -> Forecast:
    consumption = ports.get_consumption_series(db, facility_id, product_id)
    footfall = ports.get_footfall_series(db, facility_id)
    current_stock = ports.get_current_stock(db, facility_id, product_id)
    expected_incoming = np.zeros(horizon_days)  # ports.get_expected_incoming: no source table yet

    fallback_level = FallbackLevel.LOCAL
    if needs_fallback(consumption):
        rate, fallback_level = fallback_daily_rate(db, facility_id, product_id)
        point = np.full(horizon_days, rate)
        low, high = point * 0.75, point * 1.25  # residual-based band unavailable with no local fit
        chosen_model, range_source = ForecastModel.RECENT_AVERAGE, RangeSource.RESIDUAL
        metrics_records = []
    else:
        selection = select_and_forecast(consumption, horizon_days)
        ratio = footfall_adjustment_ratio(footfall)
        point = apply_footfall_adjustment(selection.chosen.point, ratio)
        low = apply_footfall_adjustment(selection.chosen.low, ratio)
        high = apply_footfall_adjustment(selection.chosen.high, ratio)
        chosen_model, range_source = selection.chosen.model, selection.chosen.range_source
        metrics_records = selection.metrics

    projected = project_stock(current_stock, expected_incoming, point)
    stockout_day = first_stockout_day(projected)

    forecast = Forecast(
        facility_id=facility_id,
        product_id=product_id,
        horizon_days=horizon_days,
        current_stock=current_stock,
        forecast_demand=float(point.sum()),
        projected_stock=float(projected[-1]) if len(projected) else float(current_stock),
        stockout_day=stockout_day,
        model_used=chosen_model,
        range_low=float(low.sum()),
        range_high=float(high.sum()),
        range_source=range_source,
        fallback_level=fallback_level,
        footfall_adjustment_ratio=footfall_adjustment_ratio(footfall) if fallback_level == FallbackLevel.LOCAL else None,
    )
    db.add(forecast)
    db.flush()

    for metric in metrics_records:
        db.add(
            ForecastMetric(
                forecast_id=forecast.id,
                candidate_model=metric.model,
                eligible=metric.eligible,
                selected=metric.selected,
                cv_mase=metric.cv_mase,
            )
        )
    for day_offset, (p, lo, hi) in enumerate(zip(point, low, high), start=1):
        db.add(ForecastPoint(forecast_id=forecast.id, day_offset=day_offset, point=float(p), low=float(lo), high=float(hi)))

    severity = classify_severity(stockout_day)
    db.add(
        Alert(
            facility_id=facility_id,
            product_id=product_id,
            severity=severity,
            days_to_stockout=stockout_day,
            forecast_id=forecast.id,
        )
    )
    db.flush()
    return forecast
