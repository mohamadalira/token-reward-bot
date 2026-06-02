from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    bot_token: str = Field(alias="BOT_TOKEN")
    admin_ids: str = Field(default="", alias="ADMIN_IDS")
    webapp_url: str = Field(default="http://localhost:3000", alias="WEBAPP_URL")

    # Database
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="tokenbot", alias="POSTGRES_DB")
    postgres_user: str = Field(default="tokenbot", alias="POSTGRES_USER")
    postgres_password: str = Field(alias="POSTGRES_PASSWORD")

    # Redis
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_secret_key: str = Field(alias="API_SECRET_KEY")
    webhook_path: str = Field(default="/webhook/plisio", alias="WEBHOOK_PATH")
    webhook_url: str = Field(default="", alias="WEBHOOK_URL")

    # Plisio (فقط API Token لازمه — Secret اختیاریه)
    plisio_api_key: str = Field(default="", alias="PLISIO_API_KEY")
    plisio_secret_key: str = Field(default="", alias="PLISIO_SECRET_KEY")
    plisio_enabled: bool = Field(default=True, alias="PLISIO_ENABLED")

    # App
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    default_locale: str = Field(default="fa", alias="DEFAULT_LOCALE")
    use_persian_numbers: bool = Field(default=True, alias="USE_PERSIAN_NUMBERS")
    use_jalali_dates: bool = Field(default=True, alias="USE_JALALI_DATES")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def admin_id_list(self) -> List[int]:
        if not self.admin_ids.strip():
            return []
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        if not v or v == "your_bot_token_here":
            raise ValueError("BOT_TOKEN must be set")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
