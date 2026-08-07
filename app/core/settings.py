from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, field_validator
from functools import lru_cache
from typing import Self
from common_lib.core.config import config

# Known weak / example secret — rejected in non-dev environments.
_KNOWN_WEAK_SECRETS: frozenset[str] = frozenset(
    [
        "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
        "secret",
        "changeme",
        "your-secret-key",
    ]
)


class Settings(BaseSettings):
    # enable_decoding=False stops pydantic-settings from json.loads()-ing complex
    # (list/dict) env values before validators run, so comma-separated env strings
    # like BACKEND_CORS_ORIGINS=a,b are handled by _split_csv_list instead of crashing.
    model_config = SettingsConfigDict(enable_decoding=False)

    PROJECT_NAME: str = config.get("Backend", "project_name", "Nexus AI Backend")
    VERSION: str = config.get("Backend", "version", "0.1.0")
    ENVIRONMENT: str = config.get("Backend", "environment", "prod")

    # P0-1 FIX: Default is now False. Set DEV_MODE=True explicitly in dev via config.ini or env.
    # DEV_MODE=True is rejected when ENVIRONMENT is "prod" or "staging" (see validator below).
    DEV_MODE: bool = config.get("Backend", "dev_mode", False)
    DISABLE_AUTH: bool = config.get("Backend", "disable_auth", False)

    # Goal Mode — flag-gated ferment-driven project execution. When enabled, the
    # ferment router exposes POST /ferment/goal and project status endpoints, and
    # the agent graph builder prefers the ferment role-driven loop.
    GOAL_MODE: bool = config.get("Backend", "goal_mode", False)

    # Goal-Mode v2 — auto conversation compactor trigger. When a goal project's
    # token usage crosses budget * COMPACT_TRIGGER_FRACTION, the ferment loop
    # auto-compacts the agent session context (best-effort). Only effective when
    # the token-budget guard is active (Goal Mode ON + a token_budget is set).
    COMPACT_TRIGGER_FRACTION: float = config.get(
        "Backend", "compact_trigger_fraction", 0.6
    )

    BACKEND_CORS_ORIGINS: list[str] = config.get_list(
        "Backend", "cors_origins", ["http://localhost:3000", "http://localhost:5173"]
    )
    API_V1_STR: str = config.get("Backend", "api_v1_str", "/api/v1")
    PRELOAD_LLM: bool = False
    SKIP_REGISTRY_SYNC: bool = config.get("Backend", "skip_registry_sync", True)
    EXCLUDE_TOOL_CATEGORIES: list[str] = config.get_list(
        "Backend", "exclude_tool_categories", ["internal", "deprecated", "test"]
    )

    # Image Generation Performance & Optimization
    OPTIMIZE_USE_XFORMERS: bool = config.get("Backend", "optimize_use_xformers", True)
    OPTIMIZE_USE_TORCH_COMPILE: bool = False
    OPTIMIZE_USE_STABLE_FAST: bool = False
    OPTIMIZE_USE_FREEU: bool = True
    OPTIMIZE_LOW_VRAM: bool = config.get("Backend", "optimize_low_vram", False)

    # OpenAPI Customization — hide docs in production
    OPENAPI_URL: str = "/openapi.json"
    DOCS_URL: str = "/docs"
    REDOC_URL: str = "/redoc"

    # Security
    # P0-1 FIX: No hard-coded fallback. If SECRET_KEY is absent or is a known weak value
    # in a non-dev environment, startup fails with a descriptive error.
    SECRET_KEY: str = config.get("Keys", "secret_key", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database Settings
    # P0-1 FIX: No hard-coded password fallback. Absent password in non-dev → startup fails.
    POSTGRES_SERVER: str = config.get("Database", "postgres_server", "localhost")
    POSTGRES_USER: str = config.get("Database", "postgres_user", "nexus")
    POSTGRES_PASSWORD: str = config.get("Database", "postgres_password", "")
    POSTGRES_DB: str = config.get("Database", "postgres_db", "nexus_db")
    POSTGRES_PORT: int = config.get("Database", "postgres_port", 5432)

    # Proxy trust — only accept identity headers from a proxy that presents this secret.
    # Leave blank to disable proxy-header identity (safe default).
    TRUSTED_PROXY_SECRET: str = config.get("Backend", "trusted_proxy_secret", "")

    @field_validator("BACKEND_CORS_ORIGINS", "EXCLUDE_TOOL_CATEGORIES", mode="before")
    @classmethod
    def _split_csv_list(cls, v):
        """Accept list-typed settings from env as JSON *or* comma-separated strings.

        We set ``enable_decoding=False`` so pydantic-settings does not try to
        ``json.loads()`` the raw env value (a plain value like
        ``http://localhost:3000,http://localhost:5173`` is not valid JSON and would
        crash startup). We normalise strings here instead.
        """
        if v is None:
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s[0] in "[{":
                import json as _json

                try:
                    return _json.loads(s)
                except ValueError:
                    return [item.strip() for item in s.split(",") if item.strip()]
            return [item.strip() for item in s.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def _validate_security(self) -> Self:
        """Fail fast when security invariants are violated.

        Rules:
        - DEV_MODE=True is forbidden in prod/staging environments.
        - A missing or known-weak SECRET_KEY is forbidden in non-dev environments.
        - An empty POSTGRES_PASSWORD is forbidden in non-dev environments.
        """
        is_prod_like = self.ENVIRONMENT in ("prod", "staging")
        is_dev = self.DEV_MODE

        if is_prod_like and is_dev:
            raise ValueError(
                f"DEV_MODE=True is not allowed in ENVIRONMENT={self.ENVIRONMENT!r}. "
                "Set DEV_MODE=False or change ENVIRONMENT to 'development'."
            )

        if is_prod_like and self.DISABLE_AUTH:
            raise ValueError(
                f"DISABLE_AUTH=True is not allowed in ENVIRONMENT={self.ENVIRONMENT!r}. "
                "Authentication must be enabled in production."
            )

        if not is_dev:
            if not self.SECRET_KEY:
                raise ValueError(
                    "SECRET_KEY must be set via config or environment variable. "
                    "It cannot be empty in non-dev environments."
                )
            if self.SECRET_KEY in _KNOWN_WEAK_SECRETS:
                raise ValueError(
                    "SECRET_KEY is set to a known weak/example value. "
                    "Generate a strong secret and set it via config or SECRET_KEY env var."
                )
            if not self.POSTGRES_PASSWORD:
                raise ValueError(
                    "POSTGRES_PASSWORD must be set via config or environment variable. "
                    "It cannot be empty in non-dev environments."
                )

        return self

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache()
def get_settings():
    return Settings()
