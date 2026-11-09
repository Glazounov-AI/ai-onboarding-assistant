from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"

    bot_token: SecretStr | None = None

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    postgres_db: str = "onboarding"
    postgres_user: str = "onboarding_app"
    postgres_password: SecretStr | None = None
    postgres_host: str = "db"
    postgres_port: int = Field(default=5432, ge=1, le=65535)

    training_profile: str = "config/training.example.yaml"

    def validate_runtime(self) -> None:
        if not self.bot_token or not self.bot_token.get_secret_value():
            raise ValueError("BOT_TOKEN is required")

        if not self.postgres_password or not self.postgres_password.get_secret_value():
            raise ValueError("POSTGRES_PASSWORD is required")


@lru_cache
def get_settings() -> Settings:
    return Settings()