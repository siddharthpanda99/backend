"""
Auto-Ontology — MCP Tool Registration.

Registers Auto-Ontology capabilities as MCP tools for agent consumption.
Provides term search, QA, ingestion, and semantic layer tools that agents
can call via MCP protocol.

Usage:
    # In app/mcp/server.py:
    from app.mcp.tools.auto_ontology import register_auto_ontology_tools
    register_auto_ontology_tools(mcp_server)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.mcp.fastmcp_compat import FastMCP
from ..mcp_dependencies import resolve_auto_ontology_service

logger = logging.getLogger("mcp.tools.auto_ontology")


def register_auto_ontology_tools(mcp: Any) -> None:
    """Register all Auto-Ontology tools with the MCP server.

    Registers 8 tools covering term search, retrieval, QA, ingestion,
    and semantic layer compilation.

    Args:
        mcp: FastMCP server instance.
    """

    # ── Term Search & Retrieval ──────────────────────────────────────

    @mcp.tool()
    async def search_terms(
        query: str,
        top_k: int = 10,
        connection_id: str | None = None,
    ) -> dict[str, Any]:
        """Search for ontology terms by keyword.

        Uses keyword-based search with scoring over term names, synonyms,
        descriptions, and mapped columns. Returns ranked terms with metadata.

        Args:
            query: The search query text.
            top_k: Maximum number of results to return (1-100).
            connection_id: Optional connection ID to filter by.

        Returns:
            Dict with 'terms' (list of term objects), 'total' (count), and 'query'.
        """
        from common_lib.modules.auto_ontology.service import AutoOntologyService
        from common_lib.modules.auto_ontology.config import get_settings

        settings = get_settings()
        service = AutoOntologyService(db_url=settings.db_url, settings=settings)
        return service.search_terms(
            query=query, top_k=top_k, connection_id=connection_id
        )

    @mcp.tool()
    async def get_term(term_id: str) -> dict[str, Any]:
        """Retrieve a term by ID with its columns, SQL attributes, and related terms.

        Args:
            term_id: The ID of the term to retrieve.

        Returns:
            Dict with 'term', 'sql_attributes', and 'related_terms'.
        """
        from common_lib.modules.auto_ontology.service import AutoOntologyService
        from common_lib.modules.auto_ontology.config import get_settings

        settings = get_settings()
        service = AutoOntologyService(db_url=settings.db_url, settings=settings)
        return service.get_term(term_id=term_id)

    @mcp.tool()
    async def get_term_columns(term_id: str) -> dict[str, Any]:
        """List the fully-qualified column names (schema.table.column) mapped to a term.

        Args:
            term_id: The ID of the term.

        Returns:
            Dict with 'term_id', 'term_name', and 'columns' (list of column refs).
        """
        from common_lib.modules.auto_ontology.service import AutoOntologyService
        from common_lib.modules.auto_ontology.config import get_settings

        settings = get_settings()
        service = AutoOntologyService(db_url=settings.db_url, settings=settings)
        return service.get_term_columns(term_id=term_id)

    @mcp.tool()
    async def get_term_sql_attributes(term_id: str) -> dict[str, Any]:
        """List the SQLAttribute objects owned by a term.

        Args:
            term_id: The ID of the term.

        Returns:
            Dict with 'term_id', 'term_name', and 'sql_attributes' (list of attribute objects).
        """
        from common_lib.modules.auto_ontology.service import AutoOntologyService
        from common_lib.modules.auto_ontology.config import get_settings

        settings = get_settings()
        service = AutoOntologyService(db_url=settings.db_url, settings=settings)
        return service.get_term_sql_attributes(term_id=term_id)

    @mcp.tool()
    async def get_sql_attribute(attr_id: str) -> dict[str, Any]:
        """Retrieve a single SQLAttribute by its ID.

        Args:
            attr_id: The ID of the SQL attribute.

        Returns:
            SQLAttribute object with id, term_id, name, expression, purpose, etc.
        """
        from common_lib.modules.auto_ontology.service import AutoOntologyService
        from common_lib.modules.auto_ontology.config import get_settings

        settings = get_settings()
        service = AutoOntologyService(db_url=settings.db_url, settings=settings)
        return service.get_sql_attribute(attr_id=attr_id)

    @mcp.tool()
    async def describe_table(
        connection_id: str,
        schema: str,
        table: str,
    ) -> dict[str, Any]:
        """Describe a table: its columns, which terms map to it, and its SQL attributes.

        Args:
            connection_id: The connection ID.
            schema: The schema name (e.g., 'main', 'public').
            table: The table name.

        Returns:
            Dict with 'connection_id', 'schema', 'table', 'columns', 'terms', 'sql_attributes'.
        """
        from common_lib.modules.auto_ontology.service import AutoOntologyService
        from common_lib.modules.auto_ontology.config import get_settings

        settings = get_settings()
        service = AutoOntologyService(db_url=settings.db_url, settings=settings)
        return service.describe_table(
            connection_id=connection_id, schema=schema, table=table
        )

    # ── QA / Check Answerable ───────────────────────────────────────

    @mcp.tool()
    async def check_answerable(
        question: str,
        connection_id: str | None = None,
    ) -> dict[str, Any]:
        """Grade ontology coverage for a natural-language question.

        Returns a coverage score (0-1), list of supported terms, and missing terms.
        Use as a pre-flight check before ask_question.

        Args:
            question: The natural-language question to check.
            connection_id: Optional connection ID to filter by.

        Returns:
            Dict with 'answerable' (bool), 'coverage' (0-1), 'supported_terms',
            'missing_terms', and optional 'suggested_refinement'.
        """
        from common_lib.modules.auto_ontology.service import AutoOntologyService
        from common_lib.modules.auto_ontology.config import get_settings

        settings = get_settings()
        service = AutoOntologyService(db_url=settings.db_url, settings=settings)
        return service.check_answerable(question=question, connection_id=connection_id)

    @mcp.tool()
    async def ask_question(
        question: str,
        connection_id: str | None = None,
        max_rows: int = 100,
    ) -> dict[str, Any]:
        """Full natural-language QA over the ontology.

        Runs coverage check, retrieves relevant terms and SQL attributes,
        generates SQL, executes against the source database, and returns
        the answer with SQL, steps, rows, coverage, and trace ID.

        Args:
            question: The natural-language question to answer.
            connection_id: Optional connection ID to filter by.
            max_rows: Maximum rows to return (1-10000).

        Returns:
            Dict with 'answer', 'sql', 'steps', 'rows', 'coverage', 'trace_id'.
        """
        from common_lib.modules.auto_ontology.service import AutoOntologyService
        from common_lib.modules.auto_ontology.config import get_settings

        settings = get_settings()
        service = AutoOntologyService(db_url=settings.db_url, settings=settings)
        return service.ask_question(
            question=question, connection_id=connection_id, max_rows=max_rows
        )
