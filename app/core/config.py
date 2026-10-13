"""Core configuration module powered by Pydantic Settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PGUSER: str = "postgres"
    PGPASSWORD: str = "postgres"
    DB_NAME: str = "caching_service"
    PGHOST: str = "localhost"
    PGPORT: int = 5432

    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    @property
    def database_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        return f"postgresql+asyncpg://{self.PGUSER}:{self.PGPASSWORD}@{self.PGHOST}:{self.PGPORT}/{self.DB_NAME}"


settings = Settings()
