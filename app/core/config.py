from pydantic_settings import BaseSettings, SettingsConfigDict
from arq.connections import RedisSettings


class Settings(BaseSettings):
    # DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/yt"
    DATABASE_URL: str
    # REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_URL: str
    # API_ORIGIN: str = "http://localhost:5173"
    API_ORIGIN: str
    YOUTUBE_API_KEY: str
    SHORTS_MAX_SECONDS: int = 60
    echo_sql: bool = False
    debug_logs: bool = True
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def get_redis_settings(self) -> RedisSettings:
        return RedisSettings.from_dsn(self.REDIS_URL)


settings = Settings()
