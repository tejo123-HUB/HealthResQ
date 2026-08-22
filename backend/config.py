from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://healthresq:healthresq@localhost:5432/healthresq"

    jwt_secret: str = "dev-only-secret-change-me"
    jwt_expiry_minutes: int = 480

    reference_indicator_mode: str = "mock"  # "real" | "mock"
    reference_indicator_refresh_days: int = 7
    gho_base_url: str = "https://ghoapi.azureedge.net/api"

    seed_default_password: str = "demo-pass-123"

    # OPS-12: "slot granularity is a configuration value defaulting to 30 minutes" — every OT
    # slot's duration must be a positive multiple of this.
    ot_slot_granularity_minutes: int = 30

    # INT-09: "greedy" (default, INT-08) or "min_cost_flow" for generate_redistribution_options.
    # Provably equivalent for the single-destination case (see redistribution/ORTOOLS_UPGRADE.md);
    # this flag exists to satisfy the architecture's "swappable allocator" acceptance criterion,
    # not because the default output changes.
    redistribution_allocator: str = "greedy"

    # INT-14: "age" (default, Apache AGE inside the primary Postgres) or "memgraph" (self-hosted,
    # profile-gated docker-compose service — never started by default, per the "no new deployable
    # process by default" rule). See graph/INT14_UPGRADE_NOTE.md.
    graph_backend: str = "age"
    memgraph_uri: str = "bolt://localhost:7687"
    memgraph_user: str = ""
    memgraph_password: str = ""

    # AGT-01: "real" (calls Google Gemini's function-calling API) or "mock" (deterministic,
    # tool-grounded template synthesis, no network call) — same real/mock adapter pattern as
    # OPS-14's reference-indicator adapter. Defaults to "mock" since a working GEMINI_API_KEY and
    # network egress aren't guaranteed in every environment this runs in; "real" is a config
    # change, not a code change, once both are available.
    agent_llm_mode: str = "mock"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    # AGT-03: bounded investigation loop's max tool calls per interaction, configurable per the
    # acceptance criterion ("the cap is a configuration value, not a hard-coded constant").
    agent_tool_call_cap: int = 8


settings = Settings()
