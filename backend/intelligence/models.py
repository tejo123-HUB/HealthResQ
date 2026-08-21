import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Enums ---------------------------------------------------------------------------------------
# String values match healthresq-interface-shapes.md §2 exactly — these are the frozen contract.


class ForecastModel(str, enum.Enum):
    RECENT_AVERAGE = "RECENT_AVERAGE"
    SARIMA = "SARIMA"
    STATE_SPACE = "STATE_SPACE"
    DECOMPOSABLE = "DECOMPOSABLE"


class RangeSource(str, enum.Enum):
    MODEL_NATIVE = "MODEL_NATIVE"
    RESIDUAL = "RESIDUAL"


class FallbackLevel(str, enum.Enum):
    LOCAL = "LOCAL"
    DISTRICT = "DISTRICT"
    STATE = "STATE"
    NATIONAL = "NATIONAL"
    BRICS = "BRICS"


class Severity(str, enum.Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# --- Forecasting (INT-01, INT-02, INT-03) --------------------------------------------------------


class Forecast(Base):
    """One row per `forecast_resource` call. Only the 6 fields in
    healthresq-interface-shapes.md §2's `forecast_resource` return type are part of the frozen
    tool contract (current_stock/forecast_demand/projected_stock/stockout_day/model_used/range) —
    everything else here is provenance for INT-01's cross-validation acceptance criterion and
    INT-03's range-source/INT-12's fallback-level requirements, deliberately kept off that return
    shape so Direction 3/4 callers never see a field they didn't agree to."""

    __tablename__ = "forecasts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)

    current_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    forecast_demand: Mapped[float] = mapped_column(Float, nullable=False)
    projected_stock: Mapped[float] = mapped_column(Float, nullable=False)
    stockout_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[ForecastModel] = mapped_column(Enum(ForecastModel, name="forecast_model"), nullable=False)
    range_low: Mapped[float] = mapped_column(Float, nullable=False)
    range_high: Mapped[float] = mapped_column(Float, nullable=False)

    # Provenance — not part of the frozen `forecast_resource` return shape.
    range_source: Mapped[RangeSource] = mapped_column(Enum(RangeSource, name="range_source"), nullable=False)
    fallback_level: Mapped[FallbackLevel] = mapped_column(
        Enum(FallbackLevel, name="fallback_level"),
        nullable=False,
        default=FallbackLevel.LOCAL,
    )
    footfall_adjustment_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    metrics: Mapped[list["ForecastMetric"]] = relationship(back_populates="forecast")
    points: Mapped[list["ForecastPoint"]] = relationship(back_populates="forecast")


class ForecastMetric(Base):
    """INT-01's cross-validation provenance: one row per candidate model evaluated for a forecast,
    so "never worse than any other eligible candidate" is checkable after the fact, not just
    trusted at selection time."""

    __tablename__ = "forecast_metrics"

    id: Mapped[uuid.UUID] = _uuid_pk()
    forecast_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("forecasts.id"), nullable=False)
    candidate_model: Mapped[ForecastModel] = mapped_column(
        Enum(ForecastModel, name="candidate_model"), nullable=False
    )
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cv_mase: Mapped[float | None] = mapped_column(Float, nullable=True)

    forecast: Mapped["Forecast"] = relationship(back_populates="metrics")


class ForecastPoint(Base):
    """Per-day point in the forecast horizon — the path INT-13's resource explorer charts."""

    __tablename__ = "forecast_points"

    id: Mapped[uuid.UUID] = _uuid_pk()
    forecast_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("forecasts.id"), nullable=False)
    day_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    point: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)

    forecast: Mapped["Forecast"] = relationship(back_populates="points")


# --- Risk & anomalies (INT-04, INT-05) ------------------------------------------------------------


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity, name="alert_severity"), nullable=False)
    days_to_stockout: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forecast_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("forecasts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = _uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    baseline: Mapped[float] = mapped_column(Float, nullable=False)
    recent: Mapped[float] = mapped_column(Float, nullable=False)
    percent_change: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


# --- Federation (INT-10, INT-11, INT-12) ----------------------------------------------------------


class FederationRound(Base):
    __tablename__ = "federation_rounds"

    id: Mapped[uuid.UUID] = _uuid_pk()
    round_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class FederationMetric(Base):
    """A national node's INT-10 submission for one round/resource: exactly the 11 documented
    aggregate fields plus a sample-size weight — never a PHC-level or patient-level field."""

    __tablename__ = "federation_metrics"

    id: Mapped[uuid.UUID] = _uuid_pk()
    round_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("federation_rounds.id"), nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    resource: Mapped[str] = mapped_column(String, nullable=False)
    samples: Mapped[int] = mapped_column(Integer, nullable=False)

    weekly_seasonal_index: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_seasonal_index: Mapped[float] = mapped_column(Float, nullable=False)
    demand_trend: Mapped[float] = mapped_column(Float, nullable=False)
    consumption_per_1000_visits: Mapped[float] = mapped_column(Float, nullable=False)
    volatility: Mapped[float] = mapped_column(Float, nullable=False)
    lead_time_mean: Mapped[float] = mapped_column(Float, nullable=False)
    lead_time_variance: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_mae: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_bias: Mapped[float] = mapped_column(Float, nullable=False)
    stockout_frequency: Mapped[float] = mapped_column(Float, nullable=False)
    surge_multiplier: Mapped[float] = mapped_column(Float, nullable=False)


class FederationProfile(Base):
    """The published, sample-weighted-aggregated BRICS reference profile for one round/resource
    (INT-11) — the same 11 fields as `FederationMetric`, aggregated across every country's
    submission for that resource, plus the always-0 raw-records-shared figure."""

    __tablename__ = "federation_profiles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    round_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("federation_rounds.id"), nullable=False)
    resource: Mapped[str] = mapped_column(String, nullable=False)
    participant_count: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_records_shared: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    weekly_seasonal_index: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_seasonal_index: Mapped[float] = mapped_column(Float, nullable=False)
    demand_trend: Mapped[float] = mapped_column(Float, nullable=False)
    consumption_per_1000_visits: Mapped[float] = mapped_column(Float, nullable=False)
    volatility: Mapped[float] = mapped_column(Float, nullable=False)
    lead_time_mean: Mapped[float] = mapped_column(Float, nullable=False)
    lead_time_variance: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_mae: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_bias: Mapped[float] = mapped_column(Float, nullable=False)
    stockout_frequency: Mapped[float] = mapped_column(Float, nullable=False)
    surge_multiplier: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
