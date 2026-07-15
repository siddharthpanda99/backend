"""MCP tools for Query History, Snippets & Templates (UDS Module 21)."""

from typing import Optional

from common_lib.modules.db_studio.knowledge_library import (
    KnowledgeLibraryService,
    HistoryRecordCreate, HistorySearchRequest,
    SavedQueryCreate, SavedQueryUpdate,
    SnippetCreate, SnippetUpdate,
    TemplateCreate, TemplateUpdate,
    CollectionCreate, CollectionUpdate, CollectionItemAdd,
    TagCreate,
    SearchRequest,
)

svc = KnowledgeLibraryService()


def mcp_history_record(query_text: str, database_type: str = None,
                        execution_time_ms: int = None, status: str = "success",
                        workspace_id: str = None) -> dict:
    """Record a query execution in history."""
    req = HistoryRecordCreate(
        query_text=query_text, database_type=database_type,
        execution_time_ms=execution_time_ms, status=status,
        workspace_id=workspace_id,
    )
    result = svc.record_execution(req)
    return result.model_dump()


def mcp_history_list(workspace_id: str = None, database_type: str = None,
                      limit: int = 50) -> list:
    """List query history with optional filters."""
    results = svc.list_history(workspace_id, database_type, limit=limit)
    return [r.model_dump() for r in results]


def mcp_history_search(query: str = "", database_type: str = None,
                        is_favorite: bool = None, limit: int = 50) -> list:
    """Search query history."""
    req = HistorySearchRequest(query=query, database_type=database_type,
                                is_favorite=is_favorite, limit=limit)
    results = svc.search_history(req)
    return [r.model_dump() for r in results]


def mcp_history_toggle_favorite(history_id: str) -> Optional[dict]:
    """Toggle favorite on a history record."""
    result = svc.toggle_favorite(history_id)
    return result.model_dump() if result else None


def mcp_saved_query_create(title: str, query_text: str, description: str = None,
                            language: str = "sql", category: str = None,
                            tags: list = None, workspace_id: str = None) -> dict:
    """Save a query."""
    req = SavedQueryCreate(
        title=title, query_text=query_text, description=description,
        language=language, category=category, tags=tags,
        workspace_id=workspace_id,
    )
    result = svc.create_saved_query(req)
    return result.model_dump()


def mcp_saved_query_list(category: str = None, language: str = None,
                          workspace_id: str = None, limit: int = 50) -> list:
    """List saved queries."""
    results = svc.list_saved_queries(category, language, workspace_id, limit=limit)
    return [r.model_dump() for r in results]


def mcp_saved_query_update(query_id: str, title: str = None,
                            description: str = None) -> Optional[dict]:
    """Update a saved query."""
    req = SavedQueryUpdate(title=title, description=description)
    result = svc.update_saved_query(query_id, req)
    return result.model_dump() if result else None


def mcp_snippet_create(title: str, code: str, description: str = None,
                        language: str = "sql", category: str = None,
                        tags: list = None, is_team_snippet: bool = False,
                        workspace_id: str = None) -> dict:
    """Create a code snippet."""
    req = SnippetCreate(
        title=title, code=code, description=description,
        language=language, category=category, tags=tags,
        is_team_snippet=is_team_snippet, workspace_id=workspace_id,
    )
    result = svc.create_snippet(req)
    return result.model_dump()


def mcp_snippet_list(language: str = None, category: str = None,
                      workspace_id: str = None, limit: int = 50) -> list:
    """List snippets."""
    results = svc.list_snippets(language, category, workspace_id, limit=limit)
    return [r.model_dump() for r in results]


def mcp_template_create(name: str, content: str, description: str = None,
                         template_type: str = "query", language: str = "sql",
                         category: str = None) -> dict:
    """Create a template."""
    req = TemplateCreate(
        name=name, content=content, description=description,
        template_type=template_type, language=language, category=category,
    )
    result = svc.create_template(req)
    return result.model_dump()


def mcp_template_list(template_type: str = None, language: str = None,
                       category: str = None, limit: int = 50) -> list:
    """List templates."""
    results = svc.list_templates(template_type, language, category, limit=limit)
    return [r.model_dump() for r in results]


def mcp_collection_create(name: str, description: str = None,
                           workspace_id: str = None) -> dict:
    """Create a collection."""
    req = CollectionCreate(name=name, description=description, workspace_id=workspace_id)
    result = svc.create_collection(req)
    return result.model_dump()


def mcp_collection_list(workspace_id: str = None, limit: int = 50) -> list:
    """List collections."""
    results = svc.list_collections(workspace_id, limit)
    return [r.model_dump() for r in results]


def mcp_collection_add_item(collection_id: str, item_type: str,
                             item_id: str) -> dict:
    """Add an item to a collection."""
    req = CollectionItemAdd(item_type=item_type, item_id=item_id)
    result = svc.add_collection_item(collection_id, req)
    return result.model_dump()


def mcp_tag_create(name: str, workspace_id: str = None) -> dict:
    """Create a tag."""
    req = TagCreate(name=name, workspace_id=workspace_id)
    result = svc.create_tag(req)
    return result.model_dump()


def mcp_search(query: str = "", resource_types: list = None,
                language: str = None, category: str = None,
                limit: int = 50) -> list:
    """Search across saved queries, snippets, and templates."""
    req = SearchRequest(query=query, resource_types=resource_types,
                         language=language, category=category, limit=limit)
    results = svc.search(req)
    return [r.model_dump() for r in results]


def mcp_knowledge_library_dashboard() -> dict:
    """Get knowledge library dashboard summary."""
    result = svc.get_dashboard()
    return result.model_dump()


def register_knowledge_library_tools(mcp_server):
    """Register all knowledge library tools with the MCP server."""
    for name, fn in TOOLS.items():
        mcp_server.tool(name=name)(fn)
    return mcp_server


TOOLS = {
    "history_record": mcp_history_record,
    "history_list": mcp_history_list,
    "history_search": mcp_history_search,
    "history_toggle_favorite": mcp_history_toggle_favorite,
    "saved_query_create": mcp_saved_query_create,
    "saved_query_list": mcp_saved_query_list,
    "saved_query_update": mcp_saved_query_update,
    "snippet_create": mcp_snippet_create,
    "snippet_list": mcp_snippet_list,
    "template_create": mcp_template_create,
    "template_list": mcp_template_list,
    "collection_create": mcp_collection_create,
    "collection_list": mcp_collection_list,
    "collection_add_item": mcp_collection_add_item,
    "tag_create": mcp_tag_create,
    "search": mcp_search,
    "knowledge_library_dashboard": mcp_knowledge_library_dashboard,
}
