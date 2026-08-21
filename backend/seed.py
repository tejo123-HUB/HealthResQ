"""Seed data for local/dev use: one country, a handful of states/districts, ~20 PHCs plus a few
SHCs and warehouses, a product catalog, demo users per role/scope, 30 days of operational history
for every facility (so Direction 2's forecasting has real history to run against), and a couple of
sample atomic_instructions rows so OPS-06/07's inbox endpoints are demonstrably non-empty.

Run with: python -m backend.seed
"""

import random
from datetime import date, datetime, timedelta, timezone

from backend.audit.service import log_event
from backend.comm import models as comm_models
from backend.db import Base, SessionLocal, engine
from backend.ops import models
from backend.ops.security import hash_password
from backend.config import settings

random.seed(42)

PRODUCTS = ["ORS", "Paracetamol", "IV Fluids", "Amoxicillin", "Oxygen Cylinders"]

STATES = {
    "Andhra Pradesh": ["Krishna", "Guntur"],
    "Maharashtra": ["Pune", "Nagpur"],
    "Karnataka": ["Bengaluru Urban", "Mysuru"],
}

PHC_COUNT = 20
SHC_COUNT = 4
WAREHOUSE_COUNT = 4
HISTORY_DAYS = 30


def slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("---", "-")


def run() -> None:
    Base.metadata.create_all(engine)  # no-op once alembic migrations have run; safe either way
    db = SessionLocal()

    try:
        if db.query(models.Country).count() > 0:
            print("Seed data already present, skipping.")
            return

        # --- Roles -----------------------------------------------------------------------------
        role_operator = models.Role(name="FACILITY_OPERATOR")
        role_authority = models.Role(name="AUTHORITY_USER")
        db.add_all([role_operator, role_authority])
        db.flush()

        # --- Geography ---------------------------------------------------------------------------
        country = models.Country(name="India")
        db.add(country)
        db.flush()

        districts_by_state: dict[str, list[models.District]] = {}
        states: list[models.State] = []
        for state_name, district_names in STATES.items():
            state = models.State(name=state_name, country_id=country.id)
            db.add(state)
            db.flush()
            states.append(state)
            districts = []
            for district_name in district_names:
                district = models.District(name=district_name, state_id=state.id)
                db.add(district)
                db.flush()
                districts.append(district)
            districts_by_state[state_name] = districts

        all_districts = [d for ds in districts_by_state.values() for d in ds]

        def district_state_country(district: models.District) -> tuple[models.State, models.Country]:
            state = next(s for s in states if s.id == district.state_id)
            return state, country

        # --- Facilities ----------------------------------------------------------------------------
        facilities: list[models.Facility] = []

        def make_facility(name: str, ftype: models.FacilityType, district: models.District) -> models.Facility:
            state, ctry = district_state_country(district)
            f = models.Facility(
                type=ftype, name=name, district_id=district.id, state_id=state.id, country_id=ctry.id
            )
            db.add(f)
            db.flush()
            facilities.append(f)
            return f

        for i in range(1, PHC_COUNT + 1):
            district = all_districts[i % len(all_districts)]
            make_facility(f"PHC-{i:03d}", models.FacilityType.PHC, district)

        shcs: list[models.Facility] = []
        for i in range(1, SHC_COUNT + 1):
            district = all_districts[i % len(all_districts)]
            shcs.append(make_facility(f"SHC-{i:03d}", models.FacilityType.SHC, district))

        warehouses: list[models.Facility] = []
        for i in range(1, WAREHOUSE_COUNT + 1):
            district = all_districts[i % len(all_districts)]
            warehouses.append(make_facility(f"WH-{i:03d}", models.FacilityType.WAREHOUSE, district))

        db.flush()

        # --- Products ------------------------------------------------------------------------------
        products = {}
        for name in PRODUCTS:
            p = models.Product(name=name, unit="unit")
            db.add(p)
            db.flush()
            products[name] = p

        # --- Users ---------------------------------------------------------------------------------
        default_password_hash = hash_password(settings.seed_default_password)

        def make_user(username: str, role: models.Role, level: models.ScopeLevel, scope_id) -> models.User:
            u = models.User(username=username, password_hash=default_password_hash, role_id=role.id)
            db.add(u)
            db.flush()
            db.add(models.UserScope(user_id=u.id, level=level, scope_id=scope_id))
            return u

        for f in facilities:
            make_user(f"operator.{slugify(f.name)}", role_operator, models.ScopeLevel.FACILITY, f.id)

        for district in all_districts:
            make_user(f"district.{slugify(district.name)}", role_authority, models.ScopeLevel.DISTRICT, district.id)

        for state in states:
            make_user(f"state.{slugify(state.name)}", role_authority, models.ScopeLevel.STATE, state.id)

        make_user("national.india", role_authority, models.ScopeLevel.NATIONAL, country.id)

        db.flush()

        # --- 30 days of operational history for every PHC/SHC ----------------------------------------
        now = datetime.now(timezone.utc)
        operational_facilities = [f for f in facilities if f.type in (models.FacilityType.PHC, models.FacilityType.SHC)]

        for f in operational_facilities:
            stock: dict[str, int] = {name: random.randint(400, 1200) for name in PRODUCTS}

            for day_offset in range(HISTORY_DAYS, 0, -1):
                day = date.today() - timedelta(days=day_offset)
                observed_at = now - timedelta(days=day_offset)

                opd = random.randint(60, 220)
                db.add(
                    models.PatientActivity(
                        facility_id=f.id,
                        date=day,
                        shift="DAY",
                        opd_visits=opd,
                        admissions=random.randint(0, 5),
                        discharges=random.randint(0, 5),
                        referrals=random.randint(0, 2),
                        observed_at=observed_at,
                    )
                )

                db.add(
                    models.BedStatus(
                        facility_id=f.id, total=20, occupied=random.randint(2, 18), observed_at=observed_at
                    )
                )
                for role_name, scheduled in (("DOCTOR", 4), ("NURSE", 9), ("PHARMACIST", 2), ("TECHNICIAN", 3)):
                    db.add(
                        models.StaffAttendance(
                            facility_id=f.id,
                            role=role_name,
                            scheduled=scheduled,
                            present=max(0, scheduled - random.randint(0, 2)),
                            observed_at=observed_at,
                        )
                    )
                for eq_type in models.EquipmentType:
                    db.add(
                        models.EquipmentStatus(
                            facility_id=f.id,
                            type=eq_type,
                            status=random.choice(list(models.EquipmentStatusValue)),
                            observed_at=observed_at,
                        )
                    )

                for name in PRODUCTS:
                    consumed = max(1, int(opd * random.uniform(0.5, 1.5) / 20))
                    stock[name] = max(0, stock[name] - consumed)
                    db.add(
                        models.InventoryTransaction(
                            facility_id=f.id,
                            product_id=products[name].id,
                            type=models.TransactionType.ISSUE,
                            quantity=consumed,
                            at=observed_at,
                            observed_at=observed_at,
                            source_facility_id=f.id,
                        )
                    )
                    if day_offset % 7 == 0:
                        received = random.randint(200, 500)
                        stock[name] += received
                        db.add(
                            models.InventoryTransaction(
                                facility_id=f.id,
                                product_id=products[name].id,
                                type=models.TransactionType.RECEIPT,
                                quantity=received,
                                at=observed_at,
                                observed_at=observed_at,
                                source_facility_id=f.id,
                            )
                        )

            for name in PRODUCTS:
                pos = models.InventoryPosition(facility_id=f.id, product_id=products[name].id, current_stock=stock[name])
                db.add(pos)

        # --- Warehouse stock -----------------------------------------------------------------------
        for wh in warehouses:
            for name in PRODUCTS:
                qty = random.randint(3000, 8000)
                db.add(
                    models.InventoryTransaction(
                        facility_id=wh.id,
                        product_id=products[name].id,
                        type=models.TransactionType.RECEIPT,
                        quantity=qty,
                        at=now - timedelta(days=HISTORY_DAYS),
                        observed_at=now - timedelta(days=HISTORY_DAYS),
                        source_facility_id=wh.id,
                    )
                )
                db.add(models.InventoryPosition(facility_id=wh.id, product_id=products[name].id, current_stock=qty))

        # --- Wards/beds for SHCs, one demo admission ------------------------------------------------
        for shc in shcs:
            ward = models.Ward(facility_id=shc.id, name="General Ward")
            db.add(ward)
            db.flush()
            for b in range(1, 11):
                db.add(models.Bed(facility_id=shc.id, ward_id=ward.id, code=f"BED-{b:02d}", occupied=False))
        db.flush()

        # --- Demo referral -----------------------------------------------------------------------
        if facilities and shcs:
            db.add(
                models.Referral(
                    source_facility_id=facilities[0].id,
                    dest_facility_id=shcs[0].id,
                    reason="Suspected fracture requiring imaging",
                    urgency=models.ReferralUrgency.URGENT,
                )
            )

        # --- Demo atomic_instructions (schema owned here; CMD-08 populates real ones later) -----------
        target_phc = facilities[0]
        target_wh = warehouses[0]
        db.add(
            models.AtomicInstruction(
                recipient_facility_id=target_phc.id,
                product_id=products["ORS"].id,
                action="Prepare 500 ORS packets",
                quantity=500,
                deadline=now + timedelta(hours=6),
                status=models.InstructionStatus.ACKNOWLEDGED,
            )
        )
        db.add(
            models.AtomicInstruction(
                recipient_facility_id=target_wh.id,
                product_id=products["ORS"].id,
                action="Dispatch 440 ORS to PHC-001",
                quantity=440,
                deadline=now + timedelta(hours=6),
                status=models.InstructionStatus.ACKNOWLEDGED,
            )
        )

        # --- COMM-03 stub graph edges (Direction 4; swapped for Apache AGE once INT-06 ships) -------
        # One ADMIN_PARENT edge per facility, from its own district — enough for
        # backend/comm/service.py::sync_unit_mailbox to seal each facility's demo instruction into
        # its mailbox the moment that facility's operator logs in and registers a key.
        for f in facilities:
            db.add(
                comm_models.CommCommandEdge(
                    from_level=comm_models.IssuerLevel.DISTRICT,
                    from_scope_id=f.district_id,
                    to_facility_id=f.id,
                    edge_type=comm_models.GraphEdgeType.ADMIN_PARENT,
                )
            )

        log_event(db, actor_user_id=None, action="SEED", entity_type="database", entity_id="seed", details={"facilities": len(facilities)})

        db.commit()
        print(f"Seeded {len(facilities)} facilities ({PHC_COUNT} PHC, {SHC_COUNT} SHC, {WAREHOUSE_COUNT} warehouse), "
              f"{len(PRODUCTS)} products, {HISTORY_DAYS} days of history.")
        print(f"Demo login password for every seeded user: {settings.seed_default_password}")
        print("Example usernames: operator.phc-001, district.krishna, state.andhra-pradesh, national.india")
    finally:
        db.close()


if __name__ == "__main__":
    run()
