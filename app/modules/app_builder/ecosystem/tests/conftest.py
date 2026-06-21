"""pytest conftest — Ecosystem API test fixtures.

Uses in-memory SQLite with SQLModel to test all CRUD endpoints
via FastAPI TestClient. Follows the governance module test pattern.
"""

from __future__ import annotations

from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from common_lib.modules.data_storage.database.connection import get_session

# Import all ecosystem models so they register in SQLModel.metadata
from common_lib.modules.app_builder.ecosystem import (  # noqa: F401
    AppRecord,
    SocialPostRecord,
    BlogArticleRecord,
    ReviewRecord,
    WalkthroughRecord,
    WalkthroughStepRecord,
    DataSourceRecord,
    AppSettingsRecord,
)

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Strip schemas from all ORM model tables for SQLite compatibility
for table in SQLModel.metadata.tables.values():
    table.schema = None

# Drop explicit indexes on columns with unique=True to avoid
# duplicate index creation errors on SQLite
for table in SQLModel.metadata.tables.values():
    unique_col_names = {c.name for c in table.columns if c.unique}
    for ix in list(table.indexes):
        col_names = [c.name for c in ix.columns]
        if len(col_names) == 1 and col_names[0] in unique_col_names:
            table.indexes.discard(ix)

SQLModel.metadata.create_all(engine)


def get_test_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


@pytest.fixture(scope="session")
def app() -> FastAPI:
    from app.modules.app_builder.ecosystem.routes import router as ecosystem_router

    app = FastAPI()
    app.include_router(ecosystem_router, prefix="/api/v1/ecosystem")
    app.dependency_overrides[get_session] = get_test_session
    return app


@pytest.fixture(scope="session")
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c



