from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class AppConfig(BaseModel):
    """Application runtime configuration."""

    NAME: str
    ENV: str
    HOST: str
    PORT: int
    DEBUG: bool
    CORS_ORIGINS: list[str]


class DatabaseConfig(BaseModel):
    """Database configuration."""

    URL: str


class RedisConfig(BaseModel):
    """Redis configuration."""

    HOST: str
    PORT: int
    TTL: int


class JWTConfig(BaseModel):
    """JWT configuration."""

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int


class APIKeyConfig(BaseModel):
    """API key management configuration."""

    PREFIX_LENGTH: int
    TOKEN_BYTES: int
    CREATE_RATE_LIMIT: int
    CREATE_RATE_WINDOW_SECONDS: int
    ADMIN_ROLE_NAME: str


class Settings(BaseSettings):
    """Global settings loaded from environment variables."""

    APP_NAME: str = "fastapi-app"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_DEBUG: bool = True
    APP_CORS_ORIGINS: str = "*"

    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/aegis"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_TTL: int = 60

    JWT_SECRET_KEY: str = "your-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_CONFIG_ENCRYPTION_KEY: str = ""

    API_KEY_PREFIX_LENGTH: int = 8
    API_KEY_TOKEN_BYTES: int = 32
    API_KEY_CREATE_RATE_LIMIT: int = 5
    API_KEY_CREATE_RATE_WINDOW_SECONDS: int = 60
    API_KEY_ADMIN_ROLE_NAME: str = "admin"

    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @staticmethod
    def parse_cors_origins(value: str) -> list[str]:
        """Parse CORS origins from wildcard or comma-separated text."""
        if value.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @property
    def app(self) -> AppConfig:
        """Return application-specific config."""
        return AppConfig(
            NAME=self.APP_NAME,
            ENV=self.APP_ENV,
            HOST=self.APP_HOST,
            PORT=self.APP_PORT,
            DEBUG=self.APP_DEBUG,
            CORS_ORIGINS=self.parse_cors_origins(self.APP_CORS_ORIGINS),
        )

    @property
    def database(self) -> DatabaseConfig:
        """Return database-specific config."""
        return DatabaseConfig(URL=self.DATABASE_URL)

    @property
    def redis(self) -> RedisConfig:
        """Return Redis-specific config."""
        return RedisConfig(
            HOST=self.REDIS_HOST,
            PORT=self.REDIS_PORT,
            TTL=self.REDIS_TTL,
        )

    @property
    def jwt(self) -> JWTConfig:
        """Return JWT-specific config."""
        return JWTConfig(
            SECRET_KEY=self.JWT_SECRET_KEY,
            ALGORITHM=self.JWT_ALGORITHM,
            ACCESS_TOKEN_EXPIRE_MINUTES=self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
            REFRESH_TOKEN_EXPIRE_DAYS=self.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
        )

    @property
    def api_key(self) -> APIKeyConfig:
        """Return API key management config."""
        return APIKeyConfig(
            PREFIX_LENGTH=self.API_KEY_PREFIX_LENGTH,
            TOKEN_BYTES=self.API_KEY_TOKEN_BYTES,
            CREATE_RATE_LIMIT=self.API_KEY_CREATE_RATE_LIMIT,
            CREATE_RATE_WINDOW_SECONDS=self.API_KEY_CREATE_RATE_WINDOW_SECONDS,
            ADMIN_ROLE_NAME=self.API_KEY_ADMIN_ROLE_NAME,
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()


settings = get_settings()
