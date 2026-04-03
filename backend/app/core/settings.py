from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IntentShelf API"
    app_env: str = "development"
    debug: bool = True
    api_port: int = Field(
        default=18001,
        validation_alias=AliasChoices("INTENTSHELF_API_PORT", "API_PORT", "BACKEND_PORT"),
    )
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/intentshelf",
        validation_alias=AliasChoices(
            "INTENTSHELF_DATABASE_URL",
            "DATABASE_URL",
            "POSTGRES_URL",
        ),
    )

    # TODO(phase-1): split settings by environment only when real services appear.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="INTENTSHELF_",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
