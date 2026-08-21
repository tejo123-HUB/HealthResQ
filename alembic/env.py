from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.audit import models as audit_models  # noqa: F401 - registers AuditLog on Base.metadata
from backend.comm import models as comm_models  # noqa: F401 - registers COMM models on Base.metadata
from backend.config import settings
from backend.db import Base
from backend.ops import models as ops_models  # noqa: F401 - registers OPS models on Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# The dev DB image (postgis/postgis) ships PostGIS/tiger-geocoder extension tables that aren't
# part of our schema. Autogenerate must never propose dropping them.
_EXTENSION_OWNED_TABLES = {
    "spatial_ref_sys",
    "geocode_settings",
    "geocode_settings_default",
    "direction_lookup",
    "secondary_unit_lookup",
    "state_lookup",
    "street_type_lookup",
    "place_lookup",
    "county_lookup",
    "countysub_lookup",
    "zip_lookup_all",
    "zip_lookup_base",
    "zip_lookup",
    "county",
    "state",
    "place",
    "zip_state",
    "zip_state_loc",
    "cousub",
    "edges",
    "addrfeat",
    "addr",
    "featnames",
    "faces",
    "loader_platform",
    "loader_variables",
    "loader_lookuptables",
    "tabblock20",
    "tabblock",
    "tract",
    "bg",
    "pagc_gaz",
    "pagc_lex",
    "pagc_rules",
    "layer",
    "topology",
    "zcta5",
}


def include_object(object_, name, type_, reflected, compare_to):
    if type_ == "table" and reflected and name in _EXTENSION_OWNED_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
