"""
Secrets Manager — Shared Test Fixtures.

Provides an in-memory SQLite database with ONLY secrets_manager tables
registered (to avoid conflicts with PostgreSQL-only schemas in other modules).
"""

# ruff: noqa: F401 — imports below exist purely to register SQLModel tables
# (side-effect registration); each symbol line must stay importable.
from __future__ import annotations

import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import event as sa_event
from typing import Any

# Import models to ensure they register with SQLModel.metadata
from common_lib.modules.secrets_manager.vault.models import (
    Secret,
    SecretVersion,
    SecretMetadata,
)
from common_lib.modules.secrets_manager.policy.models import (
    Policy,
    PolicyBinding,
)
from common_lib.modules.secrets_manager.core.models import EncryptionKey
from common_lib.modules.secrets_manager.audit.models import AuditEntry
from common_lib.modules.secrets_manager.seal.models import (
    SealState,
    SealConfig,
    UnsealShare,
    RecoveryKey,
)
from common_lib.modules.secrets_manager.engines.models import (
    SecretEngine,
    EngineConfig,
    EngineHealth,
)
from common_lib.modules.secrets_manager.events.models import (
    SecretEvent,
    AlertRule,
    EventSubscription,
)
from common_lib.modules.secrets_manager.scanning.models import (
    ScanTarget,
    ScanFinding,
    RemediationAction,
)
from common_lib.modules.secrets_manager.replication.models import (
    ReplicationConfig,
    ReplicationLag,
)
from common_lib.modules.secrets_manager.plugins.models import (
    PluginManifest,
    PluginExecution,
)
from common_lib.modules.secrets_manager.dynamic.models import (
    DynamicSecret,
    Lease,
)
from common_lib.modules.secrets_manager.cloud.models import (
    CloudProvider,
    CloudReplication,
    ExternalVault,
)
from common_lib.modules.secrets_manager.kubernetes.models import (
    K8sAuthConfig,
    CsiDriverConfig,
    ExternalSecretConfig,
    K8sOperatorConfig,
)
from common_lib.modules.secrets_manager.pki.models import (
    CertificateAuthority,
    Certificate,
    CertificateRequest,
)
from common_lib.modules.secrets_manager.proxy.models import (
    ApiKey,
    AgentConfig,
    ClientConfig,
    ProxyRoute,
)
from common_lib.modules.secrets_manager.rotation.models import (
    RotationPolicy,
    RotationRecord,
)
from common_lib.modules.secrets_manager.ssh.models import (
    SshKeyPair,
    SshTarget,
    SshCertificate,
    SshOtp,
)

# Filter to only secrets_manager tables (sm_* prefix) to avoid PostgreSQL-only schemas from other modules
SM_TABLES = [t for t in SQLModel.metadata.tables.values() if t.name.startswith("sm_")]


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


# All 19 secrets_manager subpackages whose nodes.py define @node wrappers.
SM_SUBPACKAGES = [
    "vault",
    "core",
    "policy",
    "audit",
    "seal",
    "engines",
    "events",
    "scanning",
    "replication",
    "plugins",
    "import_export",
    "dynamic",
    "cloud",
    "kubernetes",
    "monitoring",
    "pki",
    "proxy",
    "rotation",
    "ssh",
]


@pytest.fixture
def sm_nodes_session(monkeypatch, db):
    """Patch every secrets_manager ``nodes._get_session`` to return a fresh
    SQLModel Session bound to the in-memory test DB engine.

    Wrapper functions close their session in a ``finally`` block, so each
    call must get its own Session object. Data committed by service methods
    persists across these sessions because they share the same engine.
    """
    from sqlmodel import Session as SQLSession

    engine = db._session.get_bind()

    def _factory():
        return SQLSession(engine)

    for sub in SM_SUBPACKAGES:
        mod_path = f"common_lib.modules.secrets_manager.{sub}.nodes"
        monkeypatch.setattr(f"{mod_path}._get_session", _factory)
    return _factory
