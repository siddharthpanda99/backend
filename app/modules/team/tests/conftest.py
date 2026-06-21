from __future__ import annotations

from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.team.models import Team, WorkspaceSetting

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SQLModel.metadata.create_all(engine)


def seed_test_data(session: Session) -> None:
    team = Team(
        id=1,
        name="Test Team",
        slug="test-team",
        owner_id=1,
    )
    session.add(team)
    session.commit()


with Session(engine) as _session:
    existing = _session.exec(select(Team).limit(1)).first()
    if not existing:
        seed_test_data(_session)


def get_test_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


@pytest.fixture(scope="session")
def app() -> FastAPI:
    from app.modules.team.routes import router as team_router

    app = FastAPI()
    app.include_router(team_router, prefix="/api/v1")
    app.dependency_overrides[get_session] = get_test_session
    return app


@pytest.fixture(scope="session")
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
