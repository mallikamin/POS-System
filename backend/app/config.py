import sys

from pydantic_settings import BaseSettings

_INSECURE_DEFAULTS = {"CHANGE-ME-IN-PRODUCTION", "dev-secret-key-change-in-production"}


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://pos_user:pos_pass@localhost:5432/pos_db"

    # Redis
    REDIS_URL: str = "redis://:pos_redis_dev_secret@localhost:6379/0"

    # CORS — stored as comma-separated string, parsed via property
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://localhost:8090"
    )

    # JWT Token lifetimes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours for a POS shift
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # QuickBooks Integration
    QB_CLIENT_ID: str = ""
    QB_CLIENT_SECRET: str = ""
    QB_REDIRECT_URI: str = (
        "http://localhost:8090/api/v1/integrations/quickbooks/callback"
    )
    QB_ENVIRONMENT: str = "sandbox"  # sandbox | production

    @property
    def qb_base_url(self) -> str:
        if self.QB_ENVIRONMENT == "production":
            return "https://quickbooks.api.intuit.com"
        return "https://sandbox-quickbooks.api.intuit.com"

    @property
    def qb_auth_url(self) -> str:
        return "https://appcenter.intuit.com/connect/oauth2"

    @property
    def qb_token_url(self) -> str:
        return "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

    @property
    def qb_revoke_url(self) -> str:
        return "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"

    @property
    def qb_configured(self) -> bool:
        return bool(self.QB_CLIENT_ID and self.QB_CLIENT_SECRET)

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()

# Guard: refuse to start in production with insecure SECRET_KEY
if settings.is_production and settings.SECRET_KEY in _INSECURE_DEFAULTS:
    print(
        "FATAL: SECRET_KEY is set to an insecure default. "
        "Set a strong, unique SECRET_KEY environment variable for production.",
        file=sys.stderr,
    )
    sys.exit(1)
