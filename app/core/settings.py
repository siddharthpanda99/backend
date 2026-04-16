from pydantic_settings import BaseSettings
from functools import lru_cache
from common_lib.core.config import config


class Settings(BaseSettings):
    PROJECT_NAME: str = config.get("Backend", "project_name", "Nexus AI Backend")
    VERSION: str = config.get("Backend", "version", "0.1.0")
    ENVIRONMENT: str = config.get("Backend", "environment", "prod")
    DEV_MODE: bool = config.get("Backend", "dev_mode", True)
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

    # OpenAPI Customization
    OPENAPI_URL: str = "/openapi.json"
    DOCS_URL: str = "/docs"
    REDOC_URL: str = "/redoc"

    # Security
    SECRET_KEY: str = config.get(
        "Keys",
        "secret_key",
        "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database Settings
    POSTGRES_SERVER: str = config.get("Database", "postgres_server", "localhost")
    POSTGRES_USER: str = config.get("Database", "postgres_user", "nexus")
    POSTGRES_PASSWORD: str = config.get(
        "Database", "postgres_password", "nexus_password"
    )
    POSTGRES_DB: str = config.get("Database", "postgres_db", "nexus_db")
    POSTGRES_PORT: int = config.get("Database", "postgres_port", 5432)

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


@lru_cache()
def get_settings():
    return Settings()
