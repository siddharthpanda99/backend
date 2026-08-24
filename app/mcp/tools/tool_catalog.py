"""MCP Tools — Tool Catalog & Execution.

Provides 47 pre-registered platform tools to external agents
via the MCP server: catalog browsing, execution, chaining, and versioning.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def register_tool_catalog_tools(mcp):
    """Register Tool Catalog MCP tools."""

    @mcp.tool()
    def list_tools(
        category: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List all 47+ pre-registered platform tools organized by category.

        Categories: database, data, web, ai, file, communication, system, security, media, knowledge.
        Returns tool definitions with input/output schemas.

        Args:
            category: Filter by category (e.g. 'ai', 'web', 'database')
            search: Search by name, description, or tags

        Returns:
            Dict with 'tools' list, 'total' count, and 'categories' breakdown
        """
        from common_lib.modules.tools.catalog import (
            get_catalog,
            get_tools_by_category,
            search_tools,
            get_categories,
        )
        if search:
            tools = search_tools(search)
        elif category:
            tools = get_tools_by_category(category)
        else:
            tools = get_catalog()
        return {"tools": tools, "total": len(tools), "categories": get_categories()}

    @mcp.tool()
    def get_tool(tool_id: str) -> Dict[str, Any]:
        """Get a specific tool definition from the catalog by ID.

        Args:
            tool_id: Tool ID (e.g. 'tool_llm_complete', 'tool_web_scraper')

        Returns:
            Full tool definition with parameters, type, and tags
        """
        from common_lib.modules.tools.catalog import get_tool_by_id
        tool = get_tool_by_id(tool_id)
        if not tool:
            return {"error": f"Tool not found: {tool_id}"}
        return {"tool": tool}

    @mcp.tool()
    def execute_tool(
        tool_id: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Execute a registered platform tool with given arguments.

        Supports function tools, API tools, and data transformers.
        Returns execution result with status, output, and timing.

        Args:
            tool_id: Tool ID to execute
            arguments: Tool input arguments matching the tool's parameter schema
            timeout: Execution timeout in seconds (default: 30)

        Returns:
            Dict with 'status' (success/error), 'output', 'error', 'duration_ms'
        """
        from common_lib.modules.tools.executor import get_tool_executor
        executor = get_tool_executor()
        return executor.execute(tool_id, arguments or {}, timeout=timeout)

    @mcp.tool()
    def execute_tool_chain(
        steps: List[Dict[str, Any]],
        initial_input: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a chain of tools where each tool's output feeds the next.

        Useful for multi-step workflows: scrape → parse → classify → store.

        Args:
            steps: List of {tool_id, arguments} dicts
            initial_input: Optional initial input for the first step

        Returns:
            Dict with 'status', 'output' (final), 'steps_completed', 'results'
        """
        from common_lib.modules.tools.executor import get_tool_executor
        executor = get_tool_executor()
        return executor.execute_chain(steps, initial_input)

    @mcp.tool()
    def register_tool_version(
        tool_id: str,
        definition: Dict[str, Any],
        version: str = "1.0.0",
        changelog: str = "",
    ) -> Dict[str, Any]:
        """Register a new tool version with semver tracking.

        Args:
            tool_id: Tool ID
            definition: Tool definition dict
            version: Semver version (default: 1.0.0)
            changelog: Version changelog

        Returns:
            Dict with 'version' and 'created_at'
        """
        from common_lib.modules.tools.versioning import get_version_manager
        vm = get_version_manager()
        return vm.register(tool_id, definition, version=version, changelog=changelog)

    @mcp.tool()
    def update_tool_version(
        tool_id: str,
        definition: Dict[str, Any],
        bump: str = "patch",
        changelog: str = "",
    ) -> Dict[str, Any]:
        """Bump a tool to a new version (major/minor/patch).

        Args:
            tool_id: Tool ID
            definition: Updated tool definition
            bump: Version bump type — major (breaking), minor (features), patch (fixes)
            changelog: What changed

        Returns:
            Dict with new 'version' and 'created_at'
        """
        from common_lib.modules.tools.versioning import get_version_manager
        vm = get_version_manager()
        return vm.update(tool_id, definition, bump=bump, changelog=changelog)

    @mcp.tool()
    def rollback_tool(tool_id: str, target_version: str) -> Dict[str, Any]:
        """Rollback a tool to a previous version.

        Args:
            tool_id: Tool ID
            target_version: Version to rollback to

        Returns:
            Dict with 'version' and 'definition' at that version
        """
        from common_lib.modules.tools.versioning import get_version_manager
        vm = get_version_manager()
        result = vm.rollback(tool_id, target_version)
        if not result:
            return {"error": f"Version {target_version} not found for {tool_id}"}
        return result

    @mcp.tool()
    def tool_execution_stats() -> Dict[str, Any]:
        """Get tool execution statistics.

        Returns:
            Dict with total_executions, success_rate, avg_duration_ms, registered_handlers
        """
        from common_lib.modules.tools.executor import get_tool_executor
        executor = get_tool_executor()
        return executor.get_stats()

    logger.info("Tool Catalog MCP tools registered (8 tools)")
