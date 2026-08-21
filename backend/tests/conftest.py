import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.app import app
from backend.audit import models as audit_models  # noqa: F401 - registers AuditLog on Base.metadata
from backend.comm import models as comm_models  # noqa: F401 - registers COMM models on Base.metadata
from backend.config import settings
from backend.db import Base, get_db
from backend.intelligence import models as intelligence_models  # noqa: F401 - registers INT models
from backend.intelligence.graph.schema import ensure_graph_ready
from backend.ops import models
from backend.ops.security import create_access_token, hash_password

TEST_DB_NAME = "healthresq_test"

_base_url = make_url(settings.database_url)
_test_url = _base_url.set(database=TEST_DB_NAME)
_admin_url = _base_url.set(database="postgres")


@pytest.fixture(scope="session")
def test_engine():
    admin_engine = create_engine(_admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DB_NAME}).first()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()

    engine = create_engine(_test_url)
    Base.metadata.create_all(engine)
    ensure_graph_ready(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(test_engine):
    """One connection + outer transaction per test; the app's own session.commit() calls create
    savepoints inside it (join_transaction_mode="create_savepoint"), so nothing a test does is
    ever visible outside it — no test depends on seed data or another test's state."""
    connection = test_engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    trans.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


# --- Domain fixtures --------------------------------------------------------------------------------


@pytest.fixture()
def role_operator(db):
    role = models.Role(name="FACILITY_OPERATOR")
    db.add(role)
    db.flush()
    return role


@pytest.fixture()
def role_authority(db):
    role = models.Role(name="AUTHORITY_USER")
    db.add(role)
    db.flush()
    return role


@pytest.fixture()
def geo(db):
    """One country -> one state -> two districts, so scope-isolation tests have a second
    district to prove access is denied into."""
    country = models.Country(name=f"Country-{uuid.uuid4().hex[:8]}")
    db.add(country)
    db.flush()
    state = models.State(name="State-A", country_id=country.id)
    db.add(state)
    db.flush()
    district_a = models.District(name="District-A", state_id=state.id)
    district_b = models.District(name="District-B", state_id=state.id)
    db.add_all([district_a, district_b])
    db.flush()
    return {"country": country, "state": state, "district_a": district_a, "district_b": district_b}


def make_facility(
    db, geo, *, name: str, ftype: models.FacilityType, district=None, latitude=None, longitude=None
) -> models.Facility:
    district = district or geo["district_a"]
    f = models.Facility(
        type=ftype,
        name=name,
        district_id=district.id,
        state_id=geo["state"].id,
        country_id=geo["country"].id,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(f)
    db.flush()
    return f


def make_user_token(db, role, level: models.ScopeLevel, scope_id) -> str:
    user = models.User(username=f"user-{uuid.uuid4().hex[:8]}", password_hash=hash_password("pw"), role_id=role.id)
    db.add(user)
    db.flush()
    db.add(models.UserScope(user_id=user.id, level=level, scope_id=scope_id))
    db.flush()
    return create_access_token(user_id=user.id, role=role.name, scope_level=level.value, scope_id=scope_id)


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
