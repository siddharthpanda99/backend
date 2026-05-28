import enum
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class KeyProvider(str, enum.Enum):
    OPENROUTER = "openrouter"
    GEMINI = "gemini"
    GROQ = "groq"
    TAVILY = "tavily"
    ATLASSIAN = "atlassian"
    CIVITAI = "civitai"
    NVIDIA = "nvidia"
    MISTRAL = "mistral"
    CEREBRAS = "cerebras"
    OPENCODE = "opencode"
    HUGGINGFACE = "huggingface"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"
    CUSTOM = "custom"


class KeyStatus(str, enum.Enum):
    HEALTHY = "healthy"
    INVALID = "invalid"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    UNKNOWN = "unknown"
    DISABLED = "disabled"


class KeyUsageLimit(BaseModel):
    rpm: int = Field(default=60, description="Requests per minute limit")
    rpd: int = Field(default=10000, description="Requests per day limit")
    tpm: int = Field(default=100000, description="Tokens per minute limit")
    tpd: int = Field(default=10000000, description="Tokens per day limit")


class ApiKeyCreate(BaseModel):
    provider: KeyProvider
    label: str
    key_value: str
    usage_limits: Optional[KeyUsageLimit] = None
    enabled: bool = True


class ApiKeyUpdate(BaseModel):
    label: Optional[str] = None
    key_value: Optional[str] = None
    usage_limits: Optional[KeyUsageLimit] = None
    enabled: Optional[bool] = None


class ApiKeyResponse(BaseModel):
    id: int
    provider: str
    label: str
    masked_key: str
    status: str
    enabled: bool
    created_at: str
    last_checked_at: Optional[str] = None
    usage_limits: KeyUsageLimit
    monthly_usage: Optional[int] = None


class ApiKeyListResponse(BaseModel):
    status: str = "success"
    message: Optional[str] = None
    data: List[ApiKeyResponse]
    total: int


class KeyCheckResult(BaseModel):
    id: int
    provider: str
    label: str
    status: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class UsageStats(BaseModel):
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    period_hours: int = 24


class ProviderUsageSummary(BaseModel):
    provider: str
    total_requests: int
    success_count: int
    error_count: int
    total_tokens: int


class UsageTimelinePoint(BaseModel):
    timestamp: str
    requests: int
    tokens: int
    errors: int
