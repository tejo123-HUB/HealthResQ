"""Direction 2's read access to Direction 1's real operational data.

No fixture/stub layer here: `backend.ops` already exists as real SQLAlchemy models in the same
primary database, so INT queries them directly, in-process — per AGENTS.md's "no internal HTTP
between backend modules" rule and architecture Section 12. This module is the one place INT reads
OPS tables from; every other INT module goes through these functions rather than importing
`backend.ops.models` directly, so a future change to how OPS stores something touches one file.
"""

import uuid
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.ops import models

OPERATIONAL_TYPES = (models.FacilityType.PHC, models.FacilityType.SHC)
DONOR_TYPES = (models.FacilityType.PHC, models.FacilityType.SHC, models.FacilityType.WAREHOUSE)
_CONSUMING = (models.TransactionType.ISSUE, models.TransactionType.TRANSFER_OUT)


def list_operational_facilities(db: Session) -> list[models.Facility]:
    """PHC/SHC facilities — the ones INT forecasts consumption and stock-out risk for."""
    return (
        db.query(models.Facility)
        .filter(models.Facility.type.in_(OPERATIONAL_TYPES))
        .order_by(models.Facility.name)
        .all()
    )


def list_donor_capable_facilities(db: Session) -> list[models.Facility]:
    """PHC/SHC/warehouse — everything INT-08 may consider as a redistribution source."""
    return (
        db.query(models.Facility)
        .filter(models.Facility.type.in_(DONOR_TYPES))
        .order_by(models.Facility.name)
        .all()
    )


def get_facility(db: Session, facility_id: uuid.UUID) -> models.Facility | None:
    return db.query(models.Facility).filter(models.Facility.id == facility_id).one_or_none()


def list_products(db: Session) -> list[models.Product]:
    return db.query(models.Product).order_by(models.Product.name).all()


def get_product(db: Session, product_id: uuid.UUID) -> models.Product | None:
    return db.query(models.Product).filter(models.Product.id == product_id).one_or_none()


def _to_daily_series(rows: list[tuple[date, float]], since: date, until: date) -> pd.Series:
    """Zero-fills gaps *within* [since, until] only — callers are responsible for clamping
    `since` to when the underlying record actually starts, so a facility with less history than
    the requested window doesn't get a run of fabricated leading zeros that would corrupt model
    fitting and mask INT-01/INT-12's insufficient-history detection."""
    if since > until:
        return pd.Series(dtype=float)
    idx = pd.date_range(start=since, end=until, freq="D")
    series = pd.Series(0.0, index=idx)
    for day, value in rows:
        ts = pd.Timestamp(day)
        if ts in series.index:
            series.loc[ts] = float(value or 0)
    return series


def get_footfall_series(db: Session, facility_id: uuid.UUID, *, days: int = 120) -> pd.Series:
    """Daily total OPD visits for a facility, ascending by date, zero-filled for days with no
    submitted entry since the facility's *first* recorded entry — the series INT-02's footfall
    adjustment reads. Returns an empty series if the facility has no footfall history at all."""
    today = date.today()
    requested_since = today - timedelta(days=days)
    first_entry = (
        db.query(func.min(models.PatientActivity.date))
        .filter(models.PatientActivity.facility_id == facility_id)
        .scalar()
    )
    if first_entry is None:
        return pd.Series(dtype=float)
    since = max(requested_since, first_entry)
    rows = (
        db.query(models.PatientActivity.date, func.sum(models.PatientActivity.opd_visits))
        .filter(models.PatientActivity.facility_id == facility_id, models.PatientActivity.date >= since)
        .group_by(models.PatientActivity.date)
        .order_by(models.PatientActivity.date)
        .all()
    )
    return _to_daily_series(rows, since, today)


_INCREASING = (models.TransactionType.RECEIPT, models.TransactionType.TRANSFER_IN)


def _transaction_series(
    db: Session, facility_id: uuid.UUID, product_id: uuid.UUID, types: tuple, *, days: int
) -> pd.Series:
    """Zero-fills only from this facility-product's first transaction *of any type* (not just the
    given `types`) — a product that's only ever been received, never issued, still has a real
    "since" date; without this, `get_consumption_series` on a never-issued product would fall back
    to the full zero-filled window and look identical to "no history" rather than "zero demand"."""
    today = date.today()
    requested_since = today - timedelta(days=days)
    first_txn = (
        db.query(func.min(models.InventoryTransaction.at))
        .filter(
            models.InventoryTransaction.facility_id == facility_id,
            models.InventoryTransaction.product_id == product_id,
        )
        .scalar()
    )
    if first_txn is None:
        return pd.Series(dtype=float)
    since = max(requested_since, first_txn.date())
    day_col = func.date(models.InventoryTransaction.at)
    rows = (
        db.query(day_col, func.sum(models.InventoryTransaction.quantity))
        .filter(
            models.InventoryTransaction.facility_id == facility_id,
            models.InventoryTransaction.product_id == product_id,
            models.InventoryTransaction.type.in_(types),
            models.InventoryTransaction.at >= since,
        )
        .group_by(day_col)
        .order_by(day_col)
        .all()
    )
    return _to_daily_series(rows, since, today)


def get_consumption_series(
    db: Session, facility_id: uuid.UUID, product_id: uuid.UUID, *, days: int = 120
) -> pd.Series:
    """Daily consumption (ISSUE + TRANSFER_OUT quantity) for a facility-product pair, ascending by
    date, zero-filled for days with no transaction — the series INT-01 fits candidate models to."""
    return _transaction_series(db, facility_id, product_id, _CONSUMING, days=days)


def get_receipt_series(
    db: Session, facility_id: uuid.UUID, product_id: uuid.UUID, *, days: int = 120
) -> pd.Series:
    """Daily incoming quantity (RECEIPT + TRANSFER_IN) for a facility-product pair — the other
    half of the daily net change a backward stock reconstruction (INT-10's stock-out frequency)
    needs alongside `get_consumption_series`."""
    return _transaction_series(db, facility_id, product_id, _INCREASING, days=days)


def get_current_stock(db: Session, facility_id: uuid.UUID, product_id: uuid.UUID) -> int:
    position = (
        db.query(models.InventoryPosition)
        .filter(
            models.InventoryPosition.facility_id == facility_id,
            models.InventoryPosition.product_id == product_id,
        )
        .one_or_none()
    )
    return position.current_stock if position else 0


def get_expected_incoming(
    db: Session, facility_id: uuid.UUID, product_id: uuid.UUID, *, horizon_days: int
) -> int:
    """OPS tracks only recorded transactions, not scheduled future receipts — there is no table to
    read a real number from yet. Returns 0 rather than fabricating one, per AGT-05/INT-04's rule
    against inventing a figure with no backing record; this is the seam a future OPS "planned
    delivery" feature would plug into without changing this function's signature."""
    return 0


def get_bed_status(db: Session, facility_id: uuid.UUID) -> dict:
    """Latest bed snapshot for a facility — used by INT-10's local capacity-flavored parameters."""
    bed = (
        db.query(models.BedStatus)
        .filter(models.BedStatus.facility_id == facility_id)
        .order_by(models.BedStatus.observed_at.desc())
        .first()
    )
    return {"total": bed.total if bed else 0, "occupied": bed.occupied if bed else 0}


def list_districts(db: Session) -> list[models.District]:
    return db.query(models.District).order_by(models.District.name).all()


def list_states(db: Session) -> list[models.State]:
    return db.query(models.State).order_by(models.State.name).all()


def list_countries(db: Session) -> list[models.Country]:
    return db.query(models.Country).order_by(models.Country.name).all()
