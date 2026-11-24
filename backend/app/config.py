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


settings = Settings()
