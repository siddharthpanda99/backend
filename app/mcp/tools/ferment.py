"""MCP tools for Ferment — multi-agent lifecycle, project phases, grading.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.ferment.service.ProjectEngine.
"""

import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.ferment")


def register_ferment_tools(mcp: FastMCP):
    """Register tools for multi-agent lifecycle management."""

    @mcp.tool()
    async def ferment_list_projects() -> List[Dict[str, Any]]:
        """List all ferment projects as lightweight summaries (id, name, goal, status, progress)."""
        try:
            from common_lib.modules.ferment.service import ProjectEngine

            svc = ProjectEngine()
            result = svc.list_projects()
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"ferment_list_projects error: {e}")
            return []

    @mcp.tool()
    async def ferment_create_project_from_goal(
        goal: str,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new ferment project from a natural-language goal.

        Runs the ScopingLoop (orient → plan → approve, headless auto-approve by
        default) and persists the phased step plan to .ferment/<name>.ferment.json.
        """
        try:
            from common_lib.modules.ferment.service import ProjectEngine

            svc = ProjectEngine()
            return svc.create_project_from_goal(goal=goal, name=name, config=config)
        except Exception as e:
            logger.error(f"ferment_create_project_from_goal error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def ferment_get_project(project_id: str) -> Dict[str, Any]:
        """Get a ferment project by ID or name (full serialized project)."""
        try:
            from common_lib.modules.ferment.service import ProjectEngine

            svc = ProjectEngine()
            result = svc.get_project(project_id)
            if result is None:
                return {"error": f"Project '{project_id}' not found"}
            return result
        except Exception as e:
            logger.error(f"ferment_get_project error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def ferment_execute_project(
        project_id: str,
        phase: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a ferment project.

        Primary driver is the role-driven ferment LangGraph; falls back to the
        deterministic FermentExecutor when the graph suspends/fails.
        """
        try:
            from common_lib.modules.ferment.service import ProjectEngine

            svc = ProjectEngine()
            return svc.execute_project(project_id, phase=phase, inputs=inputs)
        except Exception as e:
            logger.error(f"ferment_execute_project error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def ferment_grade_project(
        project_id: str, strictness: float = 0.5
    ) -> Dict[str, Any]:
        """Grade a project's completed steps and phases (A–F with rubric scores)."""
        try:
            from common_lib.modules.ferment.service import ProjectEngine

            svc = ProjectEngine()
            result = svc.grade_project(project_id, strictness=strictness)
            if result is None:
                return {"error": f"Project '{project_id}' not found"}
            return result
        except Exception as e:
            logger.error(f"ferment_grade_project error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def ferment_goal_status(project_id: str) -> Dict[str, Any]:
        """Return the goal-status progress payload for a ferment project.

        Includes overall status, completion boolean, progress string, step counts,
        and per-phase/per-step progress with grades.
        """
        try:
            from common_lib.modules.ferment.service import ProjectEngine

            svc = ProjectEngine()
            result = svc.goal_status(project_id)
            if result is None:
                return {"error": f"Project '{project_id}' not found"}
            return result
        except Exception as e:
            logger.error(f"ferment_goal_status error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def ferment_delete_project(project_id: str) -> str:
        """Delete a ferment project."""
        try:
            from common_lib.modules.ferment.service import ProjectEngine

            svc = ProjectEngine()
            deleted = svc.delete_project(project_id)
            return (
                f"Project {project_id} deleted"
                if deleted
                else f"Project {project_id} not found"
            )
        except Exception as e:
            logger.error(f"ferment_delete_project error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def ferment_check_token_budget(project_id: str) -> Dict[str, Any]:
        """Check the token-budget ledger for a goal-mode project.

        Returns active/status (inactive, ok, extension_pending, exceeded),
        consumed, budget, and remaining. Use to see whether the per-goal token
        limit has been hit before starting heavy execution.
        """
        try:
            from common_lib.modules.ferment.service import ProjectEngine

            svc = ProjectEngine()
            result = svc.check_token_budget(project_id)
            if result is None:
                return {"error": f"Project '{project_id}' not found"}
            return result
        except Exception as e:
            logger.error(f"ferment_check_token_budget error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def ferment_request_token_extension(
        project_id: str,
        reason: str = "",
        tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Request a human-approved token-budget extension for a goal-mode project.

        Sets extension_requested and appends a pending entry; execution stays
        suspended until a human approves (extend_token_budget) or rejects.
        """
        try:
            from common_lib.modules.ferment.service import ProjectEngine

            svc = ProjectEngine()
            result = svc.request_token_extension(
                project_id, reason=reason, tokens=tokens
            )
            if result is None:
                return {"error": f"Project '{project_id}' not found"}
            return result
        except Exception as e:
            logger.error(f"ferment_request_token_extension error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def ferment_extend_token_budget(
        project_id: str,
        extra_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Approve a pending token-budget extension.

        Raises the project budget by the requested (or explicit extra) tokens
        and clears the human hold so execution can resume.
        """
        try:
            from common_lib.modules.ferment.service import ProjectEngine

            svc = ProjectEngine()
            result = svc.approve_token_extension(
                project_id, approved_by="mcp", extra_tokens=extra_tokens
            )
            if result is None:
                return {"error": f"Project '{project_id}' not found"}
            return result
        except Exception as e:
            logger.error(f"ferment_extend_token_budget error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def ferment_compact_session(
        project_id: str, session_id: str
    ) -> Dict[str, Any]:
        """Auto-compact the agent session context for a goal-mode project.

        Reuses session_service.compact_session (evicts large tool outputs /
        intermediate turns; never touches the current pending subtask).
        """
        try:
            from common_lib.modules.ferment.service import ProjectEngine

            svc = ProjectEngine()
            result = svc.compact_project_session(project_id, session_id)
            if result is None:
                return {"error": f"Project '{project_id}' not found"}
            return result
        except Exception as e:
            logger.error(f"ferment_compact_session error: {e}")
            return {"error": str(e)}

    logger.info("Ferment: 11 MCP tools registered")
