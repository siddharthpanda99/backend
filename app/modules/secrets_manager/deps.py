"""Secrets Manager — FastAPI dependencies.

Provides shared dependencies for secrets_manager route handlers.
Uses generator-based pattern so FastAPI auto-closes sessions.
"""

from sqlmodel import Session
from typing import Generator


def get_sm_session() -> Generator[Session, None, None]:
    """Get a DB session for secrets_manager route handlers.

    Creates a fresh SQLModel Session from the shared engine.
    Generator-based dependency so FastAPI handles cleanup.
    """
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    with Session(engine) as session:
        yield session


__all__ = ["get_sm_session"]
