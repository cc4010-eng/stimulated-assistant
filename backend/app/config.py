from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/stimulated"
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"

    storage_dir: str = "./storage"
    max_upload_mb: int = 500
    # "stub" returns a fixed transcript so the pipeline runs without an API key.
    transcriber: str = "stub"
    # "pause" is a rule-based baseline that needs no model.
    suggester: str = "pause"
    followup_policy: str = "keyword"
    coder: str = "keyword"
    # AI codings at or above this confidence are accepted without review.
    coding_auto_accept: float = 0.6


settings = Settings()
