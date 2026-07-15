"""MCP tools for AI Database Copilot (UDS Module 06).

Exposes AI chat, query generation, schema explanation,
query optimization, documentation, and feedback to agents.
"""

import logging

logger = logging.getLogger(__name__)


def register_ai_copilot_tools(mcp_server):
    """Register all AI Database Copilot MCP tools."""

    from common_lib.modules.db_studio.ai_copilot import (
        AICopilotService,
        ChatRequest,
        GenerateQueryRequest,
        ExplainQueryRequest,
        ExplainSchemaRequest,
        OptimizeQueryRequest,
        DocumentSchemaRequest,
        FeedbackCreate,
        ConversationCreate,
        PromptCreate,
    )

    svc = AICopilotService()

    @mcp_server.tool()
    async def ai_chat(message: str, connection_id: str = None,
                       model: str = "gpt-4", conversation_id: str = None):
        """Chat with the AI database copilot."""
        req = ChatRequest(
            message=message,
            connection_id=connection_id,
            model=model,
            conversation_id=conversation_id,
        )
        result = svc.chat(req)
        return result.model_dump()

    @mcp_server.tool()
    async def ai_generate_query(natural_language: str, connection_id: str,
                                 database_type: str = "postgresql",
                                 query_type: str = "select"):
        """Generate a SQL query from natural language description."""
        req = GenerateQueryRequest(
            natural_language=natural_language,
            connection_id=connection_id,
            database_type=database_type,
            query_type=query_type,
        )
        result = svc.generate_query(req)
        return result.model_dump()

    @mcp_server.tool()
    async def ai_explain_query(query: str, database_type: str = "postgresql"):
        """Explain what a SQL query does step by step."""
        req = ExplainQueryRequest(query=query, database_type=database_type)
        result = svc.explain_query(req)
        return result.model_dump()

    @mcp_server.tool()
    async def ai_explain_schema(connection_id: str, schema_name: str = "public"):
        """Explain a database schema in plain language."""
        req = ExplainSchemaRequest(connection_id=connection_id, schema_name=schema_name)
        result = svc.explain_schema(req)
        return result.model_dump()

    @mcp_server.tool()
    async def ai_optimize_query(query: str, database_type: str = "postgresql"):
        """Suggest optimizations for a SQL query."""
        req = OptimizeQueryRequest(query=query, database_type=database_type)
        result = svc.optimize_query(req)
        return result.model_dump()

    @mcp_server.tool()
    async def ai_document_schema(connection_id: str, schema_name: str = "public"):
        """Generate documentation for a database schema."""
        req = DocumentSchemaRequest(connection_id=connection_id, schema_name=schema_name)
        result = svc.document_schema(req)
        return result.model_dump()

    @mcp_server.tool()
    async def ai_list_conversations(search: str = None, limit: int = 20):
        """List AI conversation history."""
        result = svc.list_conversations(search=search, limit=limit)
        return result.model_dump()

    @mcp_server.tool()
    async def ai_get_conversation(conversation_id: str):
        """Get a conversation with all messages."""
        result = svc.get_conversation(conversation_id)
        return result.model_dump() if result else {"error": "Not found"}

    @mcp_server.tool()
    async def ai_submit_feedback(conversation_id: str, message_id: str,
                                  score: int, comment: str = None):
        """Submit feedback on an AI response."""
        req = FeedbackCreate(
            conversation_id=conversation_id,
            message_id=message_id,
            score=score,
            comment=comment,
        )
        result = svc.submit_feedback(req)
        return result.model_dump()

    @mcp_server.tool()
    async def ai_list_prompts(category: str = None):
        """List available AI prompt templates."""
        results = svc.list_prompts(category=category)
        return [r.model_dump() for r in results]

    @mcp_server.tool()
    async def ai_list_model_usage(model: str = None, limit: int = 20):
        """List model usage statistics."""
        results = svc.list_model_usage(model=model, limit=limit)
        return [r.model_dump() for r in results]
