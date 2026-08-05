"""
Secrets Manager — Shared Test Fixtures.

Provides an in-memory SQLite database with ONLY secrets_manager tables
registered (to avoid conflicts with PostgreSQL-only schemas in other modules).
"""
from __future__ import annotations

import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import event as sa_event
from typing import Any

# Import models to ensure they register with SQLModel.metadata
from common_lib.modules.secrets_manager.vault.models import Secret, SecretVersion, SecretMetadata  # noqa: F401
from common_lib.modules.secrets_manager.policy.models import Policy, PolicyBinding  # noqa: F401
from common_lib.modules.secrets_manager.core.models import EncryptionKey  # noqa: F401
from common_lib.modules.secrets_manager.audit.models import AuditEntry  # noqa: F401
from common_lib.modules.secrets_manager.seal.models import SealState, SealConfig, UnsealShare, RecoveryKey  # noqa: F401
from common_lib.modules.secrets_manager.engines.models import SecretEngine, EngineConfig, EngineHealth  # noqa: F401
from common_lib.modules.secrets_manager.events.models import SecretEvent, AlertRule, EventSubscription  # noqa: F401
from common_lib.modules.secrets_manager.scanning.models import ScanTarget, ScanFinding, RemediationAction  # noqa: F401
from common_lib.modules.secrets_manager.replication.models import ReplicationConfig, ReplicationLag  # noqa: F401
from common_lib.modules.secrets_manager.plugins.models import PluginManifest, PluginExecution  # noqa: F401
from common_lib.modules.secrets_manager.import_export.service import ImportExportService  # noqa: F401

# Filter to only secrets_manager tables (sm_* prefix) to avoid PostgreSQL-only schemas from other modules
SM_TABLES = [
    t for t in SQLModel.metadata.tables.values()
    if t.name.startswith("sm_")
]


class SQLModelSession:
    """Wraps a raw SQLAlchemy Session to add SQLModel's .exec() method."""

    def __init__(self, session: Session):
        self._session = session

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)

    def exec(self, statement, params=None, execution_options=None):
        """SQLModel-compatible exec() that delegates to session.exec().

        Using exec() (not execute()) so that .first() and .all() return
        model instances directly instead of Row tuples.
        """
        return self._session.exec(
            statement,
            params=params,
            execution_options=execution_options or {},
        )


@pytest.fixture
def db():
    """Create an in-memory SQLite database with only secrets_manager tables."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})

    # Enable WAL mode and foreign keys
    @sa_event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Only create secrets_manager tables (sm_* prefix)
    SQLModel.metadata.create_all(engine, tables=SM_TABLES)
    session = Session(engine)
    try:
        yield SQLModelSession(session)
        session.commit()
    finally:
        session.close()
