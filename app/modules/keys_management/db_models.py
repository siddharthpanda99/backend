from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    BigInteger,
    Float,
    Text,
    JSON,
)
from common_lib.modules.data_storage.database.connection import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(64), nullable=False, index=True)
    label = Column(String(256), nullable=False, default="")
    encrypted_key = Column(Text, nullable=False)
    iv = Column(String(64), nullable=False)
    auth_tag = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="unknown", index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    usage_limits = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_checked_at = Column(DateTime, nullable=True)


class KeyUsageLog(Base):
    __tablename__ = "key_usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_id = Column(Integer, nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    model = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False)
    input_tokens = Column(Integer, nullable=True, default=0)
    output_tokens = Column(Integer, nullable=True, default=0)
    latency_ms = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    endpoint = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class RateLimitCooldown(Base):
    __tablename__ = "rate_limit_cooldowns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_id = Column(Integer, nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    cooldown_until = Column(DateTime, nullable=False)
    hit_count = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
