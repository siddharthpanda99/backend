"""
Backend implementations of the common_lib provider protocols.

These classes provide concrete implementations for the ConfigProvider
and StorageProvider protocols defined in common_lib. They are wired
into the provider system via set_config_provider() and
set_storage_provider() calls in common_lib_integration.py.

Each method in these classes should delegate to the real Backend
implementation (app.utils.*, app.storage.*, etc.). Currently the
Backend implementations are being migrated, so some methods raise
NotImplementedError until the real modules are available.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from common_lib.modules.orchestration.infrastructure.providers import (
    set_config_provider,
    set_storage_provider,
)

logger = logging.getLogger(__name__)


# ── Config Provider ────────────────────────────────────────────────


class BackendConfigProvider:
    """Concrete ConfigProvider implementation for the Backend app.

    Each method delegates to the corresponding real implementation in
    the Backend application layer (app.utils.*, app.core.*, etc.).

    TODO: Fill in the real implementations once the corresponding
    app.utils.* modules are in place.
    """

    def get_llm(self, user: Any) -> Any:
        """Return an LLM instance for the given user.

        FIXME: Wire to the real LLM factory (e.g. app.core.llm.get_default_llm).
        """
        from app.core.llm import get_default_llm

        return get_default_llm(user)

    def get_vanna_instance(self) -> Any:
        """Return a Vanna NL2SQL instance.

        FIXME: Wire to the real Vanna factory.
        """
        raise NotImplementedError(
            "BackendConfigProvider.get_vanna_instance: not wired yet. "
            "Implement in app.core.providers when Vanna integration is ready."
        )

    def get_embeddings_model(self) -> Any:
        """Return an embedding model instance.

        FIXME: Wire to the real embedding model factory.
        """
        raise NotImplementedError(
            "BackendConfigProvider.get_embeddings_model: not wired yet. "
            "Implement when embedding model service is available."
        )

    def get_config(self) -> Dict[str, Any]:
        """Return the application config dict.

        FIXME: Wire to the real config source (e.g. config.ini loader).
        """
        raise NotImplementedError(
            "BackendConfigProvider.get_config: not wired yet. "
            "Implement when catalogue config service is available."
        )

    def get_chart_json(
        self,
        df: Any,
        user: Any,
        no_of_goals: int = 1,
        question: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Generate chart visualization specs.

        FIXME: Wire to the real LIDA integration (app.utils.lida_utils).
        """
        raise NotImplementedError(
            "BackendConfigProvider.get_chart_json: not wired yet. "
            "Implement when LIDA chart generation is available."
        )

    def get_profiler_response(
        self,
        question: str,
        df: Any,
        user: Any,
    ) -> Dict[str, Any]:
        """Profile/filter/aggregate a DataFrame.

        FIXME: Wire to the real profiler (app.utils.profiler).
        """
        raise NotImplementedError(
            "BackendConfigProvider.get_profiler_response: not wired yet. "
            "Implement when in-memory profiler is available."
        )

    def modify_sql_query_with_max_rows(
        self,
        user: Any,
        sql: str,
        max_rows: int,
    ) -> str:
        """Apply a row-limit to a SQL query.

        FIXME: Wire to the real query explanation module (app.utils.query_explanation).
        """
        raise NotImplementedError(
            "BackendConfigProvider.modify_sql_query_with_max_rows: not wired yet. "
            "Implement when query explanation module is available."
        )

    def generate_sql_follow_up_questions(
        self,
        catalogue_name: str,
        question: str,
        dataset: str,
        sql: str,
        user_email_id: str,
    ) -> List[str]:
        """Generate SQL-related follow-up questions.

        FIXME: Wire to the real question suggestions utils.
        """
        raise NotImplementedError(
            "BackendConfigProvider.generate_sql_follow_up_questions: not wired yet. "
            "Implement when question suggestions service is available."
        )

    def generate_chart_follow_up_questions(
        self,
        dataset: str,
        user_email_id: str,
    ) -> List[str]:
        """Generate chart-related follow-up questions.

        FIXME: Wire to the real question suggestions utils.
        """
        raise NotImplementedError(
            "BackendConfigProvider.generate_chart_follow_up_questions: not wired yet. "
            "Implement when question suggestions service is available."
        )


# ── Storage Provider ───────────────────────────────────────────────


class BackendStorageProvider:
    """Concrete StorageProvider implementation for the Backend app.

    Each method delegates to the corresponding real implementation in
    the Backend application layer (app.storage.*).

    TODO: Fill in the real implementations once the corresponding
    app.storage modules are in place.
    """

    async def get_db_session(self) -> AsyncIterator[Any]:
        """Yield database session objects (async generator).

        Delegates to app.storage.db_operations.get_db_session.
        """
        from app.storage.db_operations import get_db_session as _real_get_db_session

        async for session in _real_get_db_session():
            yield session

    async def get_catalogue_details_by_id(
        self,
        catalogue_id: int,
        db_session: Any = None,
    ) -> Any:
        """Fetch catalogue metadata by ID.

        FIXME: Wire to the real catalogue storage.
        """
        raise NotImplementedError(
            "BackendStorageProvider.get_catalogue_details_by_id: not wired yet. "
            "Implement when catalogue storage is available."
        )

    async def get_session(self, session_id: str) -> Any:
        """Fetch a session by ID.

        FIXME: Wire to the real session storage.
        """
        raise NotImplementedError(
            "BackendStorageProvider.get_session: not wired yet. "
            "Implement when session storage is available."
        )

    async def get_user_by_id(
        self,
        user_id: int,
        db_session: Any = None,
    ) -> Any:
        """Fetch user by ID.

        FIXME: Wire to the real user storage.
        """
        raise NotImplementedError(
            "BackendStorageProvider.get_user_by_id: not wired yet. "
            "Implement when user storage is available."
        )

    async def add_tool_to_agent_state(
        self,
        message_id: int,
        tool_name: str,
        db_session: Any = None,
    ) -> None:
        """Record tool invocation.

        FIXME: Wire to the real session message storage.
        """
        raise NotImplementedError(
            "BackendStorageProvider.add_tool_to_agent_state: not wired yet. "
            "Implement when session message storage is available."
        )

    async def get_message(self, message_id: int) -> Any:
        """Fetch a message by ID.

        FIXME: Wire to the real session message storage.
        """
        raise NotImplementedError(
            "BackendStorageProvider.get_message: not wired yet. "
            "Implement when session message storage is available."
        )

    async def get_messages_in_session(self, session_id: str) -> List[Any]:
        """Fetch all messages in a session.

        FIXME: Wire to the real session message storage.
        """
        raise NotImplementedError(
            "BackendStorageProvider.get_messages_in_session: not wired yet. "
            "Implement when session message storage is available."
        )

    async def get_last_data_gen_message_in_session(
        self, session_id: str
    ) -> Any:
        """Fetch the last data-generating message.

        FIXME: Wire to the real session message storage.
        """
        raise NotImplementedError(
            "BackendStorageProvider.get_last_data_gen_message_in_session: "
            "not wired yet. Implement when session message storage is available."
        )

    async def update_message_result(
        self,
        session_message_id: int,
        result_type: str,
        result_content: Any,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
        processing_status: str = "completed",
        status_details: Optional[str] = None,
        db_session: Any = None,
    ) -> Any:
        """Create/update a message result.

        FIXME: Wire to the real message result storage.
        """
        raise NotImplementedError(
            "BackendStorageProvider.update_message_result: not wired yet. "
            "Implement when message result storage is available."
        )

    async def get_tables_by_catalogue_id(
        self, catalogue_id: int
    ) -> List[Any]:
        """Fetch tables by catalogue ID.

        FIXME: Wire to the real table metadata storage.
        """
        raise NotImplementedError(
            "BackendStorageProvider.get_tables_by_catalogue_id: not wired yet. "
            "Implement when table metadata storage is available."
        )

    async def get_columns_by_table_id(self, table_id: int) -> List[Any]:
        """Fetch columns by table ID.

        FIXME: Wire to the real column metadata storage.
        """
        raise NotImplementedError(
            "BackendStorageProvider.get_columns_by_table_id: not wired yet. "
            "Implement when column metadata storage is available."
        )

    def create_source_db_connector(
        self, catalogue_name: str, cfg: Dict[str, Any]
    ) -> Any:
        """Create a source DB connector.

        FIXME: Wire to the real source DB connector factory.
        """
        raise NotImplementedError(
            "BackendStorageProvider.create_source_db_connector: not wired yet. "
            "Implement when source DB connector is available."
        )


# ── Wiring Function ────────────────────────────────────────────────


def wire_providers() -> None:
    """Register the Backend provider implementations with common_lib.

    Call this once during app startup (from common_lib_integration.py
    or main.py lifespan).
    """
    config_provider = BackendConfigProvider()
    storage_provider = BackendStorageProvider()

    set_config_provider(config_provider)
    set_storage_provider(storage_provider)

    logger.info(
        "Backend providers wired: ConfigProvider=%s, StorageProvider=%s",
        type(config_provider).__name__,
        type(storage_provider).__name__,
    )
