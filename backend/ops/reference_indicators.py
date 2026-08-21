from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, get_current_user
from backend.ops.schemas import ReferenceIndicator

router = APIRouter(tags=["reference-indicators"])

# OPS-14 default reference set: health-workforce-density indicators, since they scale sensibly
# to a facility's likely patient load. Matched against GHO's own IndicatorName dimension at
# lookup time rather than a hard-coded IndicatorCode, since GHO's codes can change.
DEFAULT_INDICATOR_NAME_PATTERNS: tuple[str, ...] = (
    "Medical doctors",
    "Nursing and midwifery personnel",
    "Skilled health professionals",
)

# Fixed sample values for offline/dev use. Same shape as the real adapter's output — swapping
# REFERENCE_INDICATOR_MODE is a config change, never a code change.
_MOCK_INDICATORS: list[ReferenceIndicator] = [
    ReferenceIndicator(indicator_code="MOCK_DOCTORS_PER_10K", country="IND", value=7.3, year=2023),
    ReferenceIndicator(indicator_code="MOCK_NURSING_PER_10K", country="IND", value=17.6, year=2023),
    ReferenceIndicator(indicator_code="MOCK_SKILLED_HEALTH_PER_10K", country="IND", value=25.8, year=2023),
]


class MockAdapter:
    def get_indicators(self, country: str) -> list[ReferenceIndicator]:
        return [i for i in _MOCK_INDICATORS if i.country == country] or [
            ReferenceIndicator(indicator_code=i.indicator_code, country=country, value=i.value, year=i.year)
            for i in _MOCK_INDICATORS
        ]


class GHOAdapter:
    """Calls the WHO Global Health Observatory OData API — genuinely public, no API key, no
    account (OPS-14). Falls back to MockAdapter only on a network error, never on an access
    barrier, since GHO has none."""

    def __init__(self) -> None:
        self._resolved_codes: list[str] | None = None

    def _resolve_indicator_codes(self, client: httpx.Client) -> list[str]:
        if self._resolved_codes is not None:
            return self._resolved_codes

        codes: list[str] = []
        resp = client.get(f"{settings.gho_base_url}/Indicator", timeout=10)
        resp.raise_for_status()
        rows = resp.json().get("value", [])
        for pattern in DEFAULT_INDICATOR_NAME_PATTERNS:
            match = next((r for r in rows if pattern.lower() in r.get("IndicatorName", "").lower()), None)
            if match:
                codes.append(match["IndicatorCode"])

        self._resolved_codes = codes
        return codes

    def get_indicators(self, country: str) -> list[ReferenceIndicator]:
        with httpx.Client() as client:
            codes = self._resolve_indicator_codes(client)
            results: list[ReferenceIndicator] = []
            for code in codes:
                resp = client.get(
                    f"{settings.gho_base_url}/{code}",
                    params={"$filter": f"SpatialDim eq '{country}'"},
                    timeout=10,
                )
                resp.raise_for_status()
                rows = resp.json().get("value", [])
                if not rows:
                    continue
                latest = max(rows, key=lambda r: r.get("TimeDim", 0))
                results.append(
                    ReferenceIndicator(
                        indicator_code=code, country=country, value=float(latest["NumericValue"]), year=int(latest["TimeDim"])
                    )
                )
            return results


def get_adapter() -> MockAdapter | GHOAdapter:
    if settings.reference_indicator_mode == "real":
        return GHOAdapter()
    return MockAdapter()


def get_indicators_cached(db: Session, country: str) -> list[ReferenceIndicator]:
    """Lazy weekly refresh (OPS-14): serves the cache unless it's older than the configured
    interval, avoiding the need for a separate scheduler process."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.reference_indicator_refresh_days)
    cached = (
        db.query(models.ReferenceIndicatorCache)
        .filter(models.ReferenceIndicatorCache.country == country, models.ReferenceIndicatorCache.fetched_at >= cutoff)
        .all()
    )
    if cached:
        return [
            ReferenceIndicator(indicator_code=c.indicator_code, country=c.country, value=float(c.value), year=c.year)
            for c in cached
        ]

    adapter = get_adapter()
    try:
        fresh = adapter.get_indicators(country)
    except httpx.HTTPError:
        fresh = MockAdapter().get_indicators(country)

    now = datetime.now(timezone.utc)
    for indicator in fresh:
        stmt = (
            pg_insert(models.ReferenceIndicatorCache)
            .values(
                indicator_code=indicator.indicator_code,
                country=indicator.country,
                value=indicator.value,
                year=indicator.year,
                fetched_at=now,
            )
            .on_conflict_do_update(
                index_elements=["indicator_code", "country"],
                set_={"value": indicator.value, "year": indicator.year, "fetched_at": now},
            )
        )
        db.execute(stmt)
    db.commit()

    return fresh


@router.get("/reference-indicators", response_model=list[ReferenceIndicator])
def list_reference_indicators(
    indicator: str | None = Query(default=None, description="Optional indicator code substring filter"),
    country: str = Query(default="IND", description="ISO3 country code"),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> list[ReferenceIndicator]:
    results = get_indicators_cached(db, country)
    if indicator:
        results = [r for r in results if indicator.lower() in r.indicator_code.lower()]
    return results
