"""
Knowledge Hub test configuration.

Creates an in-memory SQLite database with seed data for all knowledge hub tests.
"""
from __future__ import annotations

from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from common_lib.modules.knowledge_engine.models.db_records import KnowledgeChunkRecord

from common_lib.modules.knowledge_hub.models import (
    IngestionPipelineRecord,
    KnowledgeProjectRecord,
    PacketRecord,
    SourceConfigRecord,
    SourceTypeRecord,
)
from common_lib.modules.knowledge_hub.seed_data import (
    get_seed_pipelines,
    get_seed_projects,
    get_seed_source_configs,
    get_seed_source_types,
    get_seed_packets,
)

# ── In-memory SQLite engine ────────────────────────────────────────

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Create tables and seed data at import time
SQLModel.metadata.create_all(engine)


def seed_test_data(session: Session) -> None:
    """Insert all seed data into the test database."""
    for data in get_seed_source_types():
        session.add(SourceTypeRecord(**data))
    for data in get_seed_source_configs():
        session.add(SourceConfigRecord(**data))
    for data in get_seed_pipelines():
        session.add(IngestionPipelineRecord(**data))
    for data in get_seed_packets():
        session.add(PacketRecord(**data))
    for data in get_seed_projects():
        session.add(KnowledgeProjectRecord(**data))
    session.commit()


with Session(engine) as _session:
    existing = _session.exec(select(SourceTypeRecord).limit(1)).first()
    if not existing:
        seed_test_data(_session)


def get_test_session() -> Generator[Session, None, None]:
    """Yield a test session with the in-memory DB."""
    with Session(engine) as session:
        yield session


# ── Session-scoped fixtures ────────────────────────────────────────


@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Create the FastAPI app with all knowledge hub routers."""
    from app.modules.knowledge_hub.routes.sources import router as sources_router
    from app.modules.knowledge_hub.routes.pipelines import router as pipelines_router
    from app.modules.knowledge_hub.routes.packets import router as packets_router
    from app.modules.knowledge_hub.routes.projects import router as projects_router

    app = FastAPI()
    app.include_router(sources_router, prefix="/api/v1")
    app.include_router(pipelines_router, prefix="/api/v1")
    app.include_router(packets_router, prefix="/api/v1")
    app.include_router(projects_router, prefix="/api/v1")

    # Override the get_session dependency to use test DB
    from common_lib.modules.data_storage.database.connection import get_session
    app.dependency_overrides[get_session] = get_test_session

    return app


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
