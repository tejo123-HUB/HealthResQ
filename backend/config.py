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


settings = Settings()
