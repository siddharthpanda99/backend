"""MCP tools for CLI error investigation."""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.cli_investigation")


def register_cli_investigation_tools(mcp: FastMCP):
    """Register tools for CLI error investigation."""

    @mcp.tool()
    async def cli_capture_error(
        module: str,
        action: str,
        command: str,
        exit_code: int,
        error_type: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Capture a CLI error for later investigation."""
        from common_lib.modules.cli.service.error_investigation import (
            get_error_investigation_service,
        )

        service = get_error_investigation_service()
        record = service.capture_error(
            module=module,
            action=action,
            command=command,
            exit_code=exit_code,
            error_type=error_type,
            error_message=error_message,
            error_details=error_details,
            stack_trace=stack_trace,
            args=args,
            session_id=session_id,
        )
        return record.model_dump()

    @mcp.tool()
    async def cli_investigate_error(
        error_id: str,
        mode: str = "auto",
        include_codebase: bool = True,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Investigate a captured CLI error using LLM analysis (direct or agentic mode)."""
        from common_lib.modules.cli.service.error_investigation import (
            get_error_investigation_service,
        )
        from common_lib.modules.cli.schemas.error_investigation import (
            InvestigateRequest,
        )

        service = get_error_investigation_service()
        request = InvestigateRequest(
            error_id=UUID(error_id),
            mode=mode,  # type: ignore
            include_codebase=include_codebase,
            model=model,
        )
        result = service.investigate(request)
        return result.model_dump()

    @mcp.tool()
    async def cli_list_errors(
        limit: int = 50,
        offset: int = 0,
        module: Optional[str] = None,
        investigated_only: bool = False,
        uninvestigated_only: bool = False,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List captured CLI errors with filtering and pagination."""
        from common_lib.modules.cli.service.error_investigation import (
            get_error_investigation_service,
        )
        from common_lib.modules.cli.schemas.error_investigation import ErrorListRequest
        from datetime import datetime

        service = get_error_investigation_service()
        request = ErrorListRequest(
            limit=limit,
            offset=offset,
            module=module,
            investigated_only=investigated_only,
            uninvestigated_only=uninvestigated_only,
            since=datetime.fromisoformat(since) if since else None,
        )
        result = service.list_errors(request)
        return result.model_dump()

    @mcp.tool()
    async def cli_get_error(error_id: str) -> Dict[str, Any]:
        """Get a specific captured error by ID."""
        from common_lib.modules.cli.service.error_investigation import (
            get_error_investigation_service,
        )

        service = get_error_investigation_service()
        error = service.get_error(UUID(error_id))
        if not error:
            return {"status": "error", "message": f"Error not found: {error_id}"}
        return error.model_dump()
