from __future__ import annotations

from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from common_lib.modules.data_storage.database.connection import get_session

# Import all governance models so they register in SQLModel.metadata
from common_lib.modules.governance.db_models import (  # noqa: F401
    GovernanceIdentity,
    GovernanceRole,
    GovernancePermission,
    GovernanceRoleAssignment,
    GovernanceDelegation,
    GovernanceAuditEvent,
    GovernanceTrustScore,
    GovernanceTrustEvent,
    GovernanceIncident,
    GovernanceTool,
    GovernanceComplianceReport,
    GovernanceWorkflowDefinition,
    GovernanceWorkflowLineage,
    GovernanceMemoryNamespace,
    GovernanceMemoryRecord,
    GovernanceApprovalPolicy,
    GovernanceTriggerDB,
    GovernanceHookDB,
    GovernanceInterceptorDB,
    GovernanceApprovalRequest,
    GovernanceEmergencyOverride,
    GovernanceGroup,
    GovernanceToken,
    GovernanceApiKey,
    GovernanceMtlsCredential,
    GovernancePolicyTriggerLink,
    GovernancePolicyHookLink,
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

# Deduplicate indexes by name to avoid duplicate creation errors on SQLite
# when multiple SQLModel classes map to the same table
seen_index_names: set[str] = set()
for table in SQLModel.metadata.tables.values():
    for ix in list(table.indexes):
        if ix.name and ix.name in seen_index_names:
            table.indexes.discard(ix)
        elif ix.name:
            seen_index_names.add(ix.name)

SQLModel.metadata.create_all(engine)


def get_test_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


@pytest.fixture(scope="session")
def app() -> FastAPI:
    from app.modules.governance.routes import router as governance_router

    app = FastAPI()
    app.include_router(governance_router, prefix="/api/v1/governance")
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
