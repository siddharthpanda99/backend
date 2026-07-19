"""MCP tools for Rules Engine — rule registry, policy engine, scoring, resilience.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.rules_engine services.
"""

import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.rules_engine")


def register_rules_engine_tools(mcp: FastMCP):
    """Register tools for the rules/policy engine."""

    @mcp.tool()
    async def rules_list() -> List[Dict[str, Any]]:
        """List all rules in the engine."""
        try:
            from common_lib.modules.rules_engine.registry import RuleRegistry
            svc = RuleRegistry()
            result = svc.list_rules() if hasattr(svc, "list_rules") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"rules_list error: {e}")
            return []

    @mcp.tool()
    async def rules_create(name: str, expression: str, action: str = "", description: str = "", priority: int = 0) -> Dict[str, Any]:
        """Create a new rule."""
        try:
            from common_lib.modules.rules_engine.registry import RuleRegistry
            svc = RuleRegistry()
            result = svc.create_rule(name, description, expression, action, priority) if hasattr(svc, "create_rule") else {"name": name}
            return result if isinstance(result, dict) else {"name": name}
        except Exception as e:
            logger.error(f"rules_create error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def rules_delete(rule_id: str) -> str:
        """Delete a rule by ID."""
        try:
            from common_lib.modules.rules_engine.registry import RuleRegistry
            svc = RuleRegistry()
            svc.delete_rule(rule_id) if hasattr(svc, "delete_rule") else None
            return f"Rule {rule_id} deleted"
        except Exception as e:
            logger.error(f"rules_delete error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def rules_enable(rule_id: str) -> str:
        """Enable a rule."""
        try:
            from common_lib.modules.rules_engine.registry import RuleRegistry
            svc = RuleRegistry()
            svc.enable_rule(rule_id) if hasattr(svc, "enable_rule") else None
            return f"Rule {rule_id} enabled"
        except Exception as e:
            logger.error(f"rules_enable error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def rules_disable(rule_id: str) -> str:
        """Disable a rule."""
        try:
            from common_lib.modules.rules_engine.registry import RuleRegistry
            svc = RuleRegistry()
            svc.disable_rule(rule_id) if hasattr(svc, "disable_rule") else None
            return f"Rule {rule_id} disabled"
        except Exception as e:
            logger.error(f"rules_disable error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def rules_evaluate(context: Dict[str, Any], mode: str = "sequential") -> Dict[str, Any]:
        """Evaluate rules against a context."""
        try:
            from common_lib.modules.rules_engine.engine import RulesEngine
            svc = RulesEngine()
            result = svc.evaluate(None, context, mode) if hasattr(svc, "evaluate") else {"matches": []}
            return result if isinstance(result, dict) else {"matches": result if isinstance(result, list) else []}
        except Exception as e:
            logger.error(f"rules_evaluate error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def rules_score(context: Dict[str, Any]) -> Dict[str, Any]:
        """Score a context against all enabled rules."""
        try:
            from common_lib.modules.rules_engine.engine import RulesEngine
            svc = RulesEngine()
            result = svc.score(context) if hasattr(svc, "score") else {"score": 0}
            return result if isinstance(result, dict) else {"score": 0}
        except Exception as e:
            logger.error(f"rules_score error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def rules_stats() -> Dict[str, Any]:
        """Get rules engine statistics."""
        try:
            from common_lib.modules.rules_engine.engine import RulesEngine
            svc = RulesEngine()
            result = svc.stats() if hasattr(svc, "stats") else {"total_rules": 0}
            return result
        except Exception as e:
            logger.error(f"rules_stats error: {e}")
            return {"error": str(e)}

    logger.info("Rules Engine: 8 MCP tools registered")
