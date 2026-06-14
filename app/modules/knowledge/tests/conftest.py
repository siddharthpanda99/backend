"""
Knowledge E2E test configuration.

Creates an in-memory SQLite database with seed conflict data and
provides client + db_session fixtures for conflict resolution tests.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.modules.knowledge.routes import router as knowledge_router
from common_lib.modules.knowledge_hub.models import ConflictRecord

# ── In-memory SQLite engine ────────────────────────────────────────

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SQLModel.metadata.create_all(engine)

# ── Seed data ──────────────────────────────────────────────────────

_NOW = datetime.now(timezone.utc).replace(tzinfo=None)

SEED_CONFLICTS = [
    {
        "id": "e2e-conf-open-001",
        "chunk_a_id": "chunk-a-001",
        "chunk_b_id": "chunk-b-001",
        "conflict_type": "direct_contradiction",
        "severity": "high",
        "domain": "financial",
        "status": "open",
        "chunk_a_content_preview": "Revenue grew 20% in Q1",
        "chunk_b_content_preview": "Revenue declined 5% in Q1",
        "chunk_a_source": "src-finance-001",
        "chunk_b_source": "src-finance-002",
        "chunk_a_confidence": 0.95,
        "chunk_b_confidence": 0.88,
        "similarity_score": 0.85,
        "detected_at": _NOW,
        "updated_at": _NOW,
    },
    {
        "id": "e2e-conf-resolved-002",
        "chunk_a_id": "chunk-a-002",
        "chunk_b_id": "chunk-b-002",
        "conflict_type": "temporal",
        "severity": "medium",
        "domain": "news",
        "status": "resolved",
        "chunk_a_content_preview": "Event occurred on Monday",
        "chunk_b_content_preview": "Event occurred on Tuesday",
        "chunk_a_source": "src-news-001",
        "chunk_b_source": "src-news-002",
        "chunk_a_confidence": 0.90,
        "chunk_b_confidence": 0.85,
        "similarity_score": 0.75,
        "winner_chunk_id": "chunk-a-002",
        "loser_chunk_id": "chunk-b-002",
        "rationale": "Monday is the correct date",
        "resolution_strategy": "human_arbitration",
        "resolved_by": "admin",
        "detected_at": _NOW,
        "updated_at": _NOW,
    },
    {
        "id": "e2e-conf-dismissed-003",
        "chunk_a_id": "chunk-a-003",
        "chunk_b_id": "chunk-b-003",
        "conflict_type": "cross_source",
        "severity": "low",
        "domain": "general",
        "status": "dismissed",
        "chunk_a_content_preview": "Some content A",
        "chunk_b_content_preview": "Different content B",
        "chunk_a_source": "src-gen-001",
        "chunk_b_source": "src-gen-002",
        "chunk_a_confidence": 0.70,
        "chunk_b_confidence": 0.65,
        "similarity_score": 0.45,
        "detected_at": _NOW,
        "updated_at": _NOW,
    },
]


def seed_test_data(session: Session) -> None:
    """Insert seed conflicts into the test database."""
    for data in SEED_CONFLICTS:
        session.add(ConflictRecord(**data))
    session.commit()


with Session(engine) as _session:
    existing = _session.exec(select(ConflictRecord).limit(1)).first()
    if not existing:
        seed_test_data(_session)


def get_test_session() -> Generator[Session, None, None]:
    """Yield a session connected to the in-memory test DB."""
    with Session(engine) as session:
        yield session


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Create the FastAPI app with the knowledge router."""
    _app = FastAPI()
    _app.include_router(knowledge_router, prefix="/api/v1")

    from common_lib.modules.data_storage.database.connection import get_session
    _app.dependency_overrides[get_session] = get_test_session

    return _app


@pytest.fixture(scope="session")
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Create a TestClient with the pre-seeded in-memory DB."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Provide a fresh DB session for tests that need direct DB access."""
    with Session(engine) as session:
        yield session
