from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base for every response/request shape that must match healthresq-interface-shapes.md's
    camelCase TypeScript field names exactly, while staying snake_case/Pythonic internally."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


# --- Auth & scope (OPS-02) -----------------------------------------------------------------------

ScopeLevelLiteral = Literal["FACILITY", "DISTRICT", "STATE", "NATIONAL"]


class Scope(CamelModel):
    level: ScopeLevelLiteral
    id: str


class LoginRequest(CamelModel):
    username: str
    password: str


class LoginResponse(CamelModel):
    token: str
    scope: Scope


# --- Geography (OPS-01) ---------------------------------------------------------------------------

FacilityTypeLiteral = Literal["PHC", "SHC", "WAREHOUSE", "REFERRAL_HOSPITAL"]


class Location(CamelModel):
    lat: float
    lng: float


class Facility(CamelModel):
    id: str
    type: FacilityTypeLiteral
    name: str
    district_id: str
    state_id: str
    country_id: str
    location: Location | None = None


class District(CamelModel):
    id: str
    name: str
    facility_ids: list[str]


class State(CamelModel):
    id: str
    name: str
    districts: list[District]


class Country(CamelModel):
    id: str
    name: str
    states: list[State]


# --- Footfall (OPS-03) -----------------------------------------------------------------------------


class FootfallEntryIn(CamelModel):
    date: date
    shift: str
    opd_visits: int
    admissions: int
    discharges: int
    referrals: int


class FootfallEntry(CamelModel):
    facility_id: str
    date: date
    shift: str
    opd_visits: int
    admissions: int
    discharges: int
    referrals: int


# --- Inventory (OPS-04) -----------------------------------------------------------------------------

TransactionTypeLiteral = Literal["RECEIPT", "ISSUE", "TRANSFER_OUT", "TRANSFER_IN"]


class InventoryTransactionIn(CamelModel):
    product_id: str
    type: TransactionTypeLiteral
    quantity: int
    batch: str | None = None
    expiry: date | None = None
    at: datetime | None = None


class InventoryTransaction(CamelModel):
    facility_id: str
    product_id: str
    type: TransactionTypeLiteral
    quantity: int
    batch: str | None
    expiry: date | None
    at: datetime
    current_stock: int
    freshness: str


# --- Capacity (OPS-05) -----------------------------------------------------------------------------

EquipmentStatusLiteral = Literal["AVAILABLE", "IN_USE", "UNAVAILABLE", "MAINTENANCE"]


class BedsIn(CamelModel):
    total: int
    occupied: int


class StaffIn(CamelModel):
    role: str
    scheduled: int
    present: int


class EquipmentIn(CamelModel):
    type: str
    status: EquipmentStatusLiteral


class CapacityStatusIn(CamelModel):
    beds: BedsIn
    staff: list[StaffIn]
    equipment: list[EquipmentIn]


class CapacityStatus(CamelModel):
    facility_id: str
    at: datetime
    beds: BedsIn
    staff: list[StaffIn]
    equipment: list[EquipmentIn]


# --- Instructions (OPS-06/07) -----------------------------------------------------------------------

InstructionStatusLiteral = Literal["ACKNOWLEDGED", "READY", "DISPATCHED", "IN_PROGRESS", "COMPLETED", "BLOCKED"]


class Instruction(CamelModel):
    id: str
    recommendation_id: str | None
    recipient_facility_id: str
    product_id: str | None
    action: str
    quantity: int
    deadline: datetime | None
    status: InstructionStatusLiteral


class InstructionStatusUpdate(CamelModel):
    status: InstructionStatusLiteral


# --- Warehouses (OPS-07) --------------------------------------------------------------------------


class WarehouseInventoryLine(CamelModel):
    product_id: str
    current_stock: int


class Warehouse(CamelModel):
    id: str
    name: str
    district_id: str
    state_id: str
    country_id: str
    inventory: list[WarehouseInventoryLine]
    orders: list[Instruction]


# --- Hospital management (OPS-11/12/13) -------------------------------------------------------------


class Ward(CamelModel):
    id: str
    facility_id: str
    name: str


class Bed(CamelModel):
    id: str
    facility_id: str
    ward_id: str
    code: str
    occupied: bool


class AdmissionIn(CamelModel):
    ward_id: str
    bed_id: str


class Admission(CamelModel):
    id: str
    facility_id: str
    ward_id: str
    bed_id: str
    admitted_at: datetime
    discharged_at: datetime | None


OTSlotStatusLiteral = Literal["SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]


class OTSlotIn(CamelModel):
    ward_id: str
    start: datetime
    end: datetime


class OTSlot(CamelModel):
    id: str
    facility_id: str
    ward_id: str
    start: datetime
    end: datetime
    status: OTSlotStatusLiteral


ReferralUrgencyLiteral = Literal["ROUTINE", "URGENT"]
ReferralStatusLiteral = Literal["OPEN", "ACKNOWLEDGED", "CLOSED"]


class ReferralIn(CamelModel):
    source_facility_id: str
    dest_facility_id: str
    reason: str
    urgency: ReferralUrgencyLiteral


class Referral(CamelModel):
    id: str
    source_facility_id: str
    dest_facility_id: str
    reason: str
    urgency: ReferralUrgencyLiteral
    status: ReferralStatusLiteral


class ReferralStatusUpdate(CamelModel):
    status: ReferralStatusLiteral


# --- Reference indicators (OPS-14) --------------------------------------------------------------------


class ReferenceIndicator(CamelModel):
    indicator_code: str
    country: str
    value: float
    year: int
