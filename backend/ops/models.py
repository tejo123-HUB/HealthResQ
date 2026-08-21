import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Enums -------------------------------------------------------------------------------------


class FacilityType(str, enum.Enum):
    PHC = "PHC"
    SHC = "SHC"
    WAREHOUSE = "WAREHOUSE"
    REFERRAL_HOSPITAL = "REFERRAL_HOSPITAL"


class ScopeLevel(str, enum.Enum):
    FACILITY = "FACILITY"
    DISTRICT = "DISTRICT"
    STATE = "STATE"
    NATIONAL = "NATIONAL"


class TransactionType(str, enum.Enum):
    RECEIPT = "RECEIPT"
    ISSUE = "ISSUE"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"


class EquipmentType(str, enum.Enum):
    OXYGEN_CONCENTRATOR = "OXYGEN_CONCENTRATOR"
    AMBULANCE = "AMBULANCE"
    COLD_CHAIN = "COLD_CHAIN"
    DIAGNOSTIC = "DIAGNOSTIC"


class EquipmentStatusValue(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    IN_USE = "IN_USE"
    UNAVAILABLE = "UNAVAILABLE"
    MAINTENANCE = "MAINTENANCE"


class InstructionStatus(str, enum.Enum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    READY = "READY"
    DISPATCHED = "DISPATCHED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class OTSlotStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ReferralUrgency(str, enum.Enum):
    ROUTINE = "ROUTINE"
    URGENT = "URGENT"


class ReferralStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CLOSED = "CLOSED"


# --- Geography & Access (OPS-01, OPS-02) --------------------------------------------------------


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    states: Mapped[list["State"]] = relationship(back_populates="country")


class State(Base):
    __tablename__ = "states"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    country_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("countries.id"), nullable=False)

    country: Mapped["Country"] = relationship(back_populates="states")
    districts: Mapped[list["District"]] = relationship(back_populates="state")


class District(Base):
    __tablename__ = "districts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    state_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("states.id"), nullable=False)

    state: Mapped["State"] = relationship(back_populates="districts")
    facilities: Mapped[list["Facility"]] = relationship(back_populates="district")


class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[uuid.UUID] = _uuid_pk()
    type: Mapped[FacilityType] = mapped_column(Enum(FacilityType, name="facility_type"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("districts.id"), nullable=False, index=True)
    # Denormalized for cheap OPS-02 scope checks without joining up the hierarchy every request.
    state_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("states.id"), nullable=False, index=True)
    country_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("countries.id"), nullable=False, index=True)
    # Real-world coordinates (was a documented gap — INT-06/07 used a synthetic hash-based
    # distance, and INT-13's risk map had no location field, until these were added).
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    district: Mapped["District"] = relationship(back_populates="facilities")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)

    role: Mapped["Role"] = relationship()
    scopes: Mapped[list["UserScope"]] = relationship(back_populates="user")


class UserScope(Base):
    __tablename__ = "user_scopes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    level: Mapped[ScopeLevel] = mapped_column(Enum(ScopeLevel, name="scope_level"), nullable=False)
    # Heterogeneous target (facility/district/state/country id depending on level) — not a single FK.
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="scopes")


# --- Resource (OPS-04) --------------------------------------------------------------------------


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    unit: Mapped[str] = mapped_column(String, nullable=False, default="unit")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, name="transaction_type"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    batch: Mapped[str | None] = mapped_column(String, nullable=True)
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    source_facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)


class InventoryPosition(Base):
    """Derived-only running balance. Recomputed inside the same transaction as each inserted
    InventoryTransaction row (OPS-04) — there is no code path that writes this table directly."""

    __tablename__ = "inventory_positions"

    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), primary_key=True)
    current_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


# --- Capacity (OPS-03, OPS-05) -------------------------------------------------------------------


class PatientActivity(Base):
    __tablename__ = "patient_activity"
    __table_args__ = (UniqueConstraint("facility_id", "date", "shift", name="uq_patient_activity_slot"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    shift: Mapped[str] = mapped_column(String, nullable=False)
    opd_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    admissions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discharges: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    referrals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class BedStatus(Base):
    """Aggregate self-reported bed snapshot (OPS-05) — the plain total/occupied count every
    facility type reports periodically. Distinct from `beds`, which tracks individually
    addressable bed slots for facilities running admission workflows (OPS-11)."""

    __tablename__ = "bed_status"

    id: Mapped[uuid.UUID] = _uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False, index=True)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    occupied: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class StaffAttendance(Base):
    __tablename__ = "staff_attendance"

    id: Mapped[uuid.UUID] = _uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    scheduled: Mapped[int] = mapped_column(Integer, nullable=False)
    present: Mapped[int] = mapped_column(Integer, nullable=False)
    shift: Mapped[str] = mapped_column(String, nullable=False, default="DAY")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class EquipmentStatus(Base):
    __tablename__ = "equipment_status"

    id: Mapped[uuid.UUID] = _uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False, index=True)
    type: Mapped[EquipmentType] = mapped_column(Enum(EquipmentType, name="equipment_type"), nullable=False)
    status: Mapped[EquipmentStatusValue] = mapped_column(
        Enum(EquipmentStatusValue, name="equipment_status_value"), nullable=False
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


# --- Hospital management (OPS-10-13) --------------------------------------------------------------


class Ward(Base):
    __tablename__ = "wards"

    id: Mapped[uuid.UUID] = _uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Bed(Base):
    """Individually addressable bed slot, used only by facilities running OPS-11 admission
    tracking (typically SHCs). Separate from the aggregate `bed_status` snapshot (OPS-05)."""

    __tablename__ = "beds"

    id: Mapped[uuid.UUID] = _uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False, index=True)
    ward_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("wards.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String, nullable=False)
    occupied: Mapped[bool] = mapped_column(nullable=False, default=False)


class Admission(Base):
    __tablename__ = "admissions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False, index=True)
    ward_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("wards.id"), nullable=False)
    bed_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("beds.id"), nullable=False)
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OTSchedule(Base):
    __tablename__ = "ot_schedules"

    id: Mapped[uuid.UUID] = _uuid_pk()
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False, index=True)
    ward_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("wards.id"), nullable=False, index=True)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[OTSlotStatus] = mapped_column(
        Enum(OTSlotStatus, name="ot_slot_status"), nullable=False, default=OTSlotStatus.SCHEDULED
    )


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[uuid.UUID] = _uuid_pk()
    source_facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    dest_facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    urgency: Mapped[ReferralUrgency] = mapped_column(Enum(ReferralUrgency, name="referral_urgency"), nullable=False)
    status: Mapped[ReferralStatus] = mapped_column(
        Enum(ReferralStatus, name="referral_status"), nullable=False, default=ReferralStatus.OPEN
    )


# --- Instructions (schema owned here; CMD-08 / Direction 3 populates real rows later) -------------


class AtomicInstruction(Base):
    __tablename__ = "atomic_instructions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # No ForeignKey("recommendations.id") here: backend/ops must not import backend/command (the
    # dependency runs the other way — CMD-08 populates this column, see backend/command/service.py
    # ::decompose_and_dispatch). The FK constraint itself is still added, by column name, in the
    # Alembic migration that creates the recommendations table.
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    recipient_facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False, index=True)
    # See healthresq-interface-shapes.md's Instruction type note: added by Direction 1 so OPS-07's
    # "stock decrements on DISPATCH" acceptance criterion has a product to act on.
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[InstructionStatus] = mapped_column(
        Enum(InstructionStatus, name="instruction_status"), nullable=False, default=InstructionStatus.ACKNOWLEDGED
    )


# --- Reference indicators (OPS-14) -----------------------------------------------------------------


class ReferenceIndicatorCache(Base):
    __tablename__ = "reference_indicator_cache"

    indicator_code: Mapped[str] = mapped_column(String, primary_key=True)
    country: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[float] = mapped_column(Numeric, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
