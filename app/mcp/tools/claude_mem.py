"""Claude-Mem MCP Tools — Register claude-mem features as MCP tools.

Exposes all claude-mem memory features (Phases 1-10) to external agents
via the MCP protocol. Tools are organized by phase:

  Phase 1: Core Memory (sessions, observations)
  Phase 2: Search Intelligence (3-layer search, timeline)
  Phase 3: Context Builder (LLM/terminal context)
  Phase 4: MCP Tools (10 memory tools)
  Phase 5: Lifecycle Hooks (session events)
  Phase 6: HTTP API (REST endpoints)
  Phase 7: Code Intelligence (AST search, outline, references)
  Phase 8: Process Management (supervisor, queue)
  Phase 9: Multi-Platform (transcript processing)
  Phase 10: Export/Budget/IDE (memory packs, budgets, IDE configs)
"""

import logging
from typing import Any, Dict, List, Optional

from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.claude_mem")


def register_claude_mem_tools(mcp: FastMCP):
    """Register all claude-mem memory features as MCP tools."""

    # ── Phase 1-3: Core Memory + Search + Context ───────────────

    @mcp.tool()
    async def claude_mem_search(
        query: str,
        project: str = "default",
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """3-layer token-efficient memory search.

        Layer 1: Returns IDs + titles (~50-100 tokens).
        Layer 2: Returns chronological timeline.
        Layer 3: Returns full observation details.

        Achieves 10x token savings vs loading all observations.
        """
        from common_lib.modules.memory.claude_mem_features.three_layer_search import ThreeLayerSearch
        import asyncio

        searcher = ThreeLayerSearch()
        results = await asyncio.to_thread(searcher.search, query)
        return results

    @mcp.tool()
    async def claude_mem_context_build(
        query: str,
        output_target: str = "llm",
        project: str = "default",
    ) -> Dict[str, Any]:
        """Build full context block for LLM or terminal.

        Orchestrates search, timeline, summary, and footer rendering.
        Supports 'llm' (agent) and 'terminal' (human) output modes.
        """
        from common_lib.modules.memory.claude_mem_features.context.builder import ContextBuilder
        import asyncio

        builder = ContextBuilder()
        result = await asyncio.to_thread(
            builder.build, query=query, output_target=output_target, project=project,
        )
        return result if isinstance(result, dict) else {"result": str(result)}

    @mcp.tool()
    async def claude_mem_format(
        observations: List[Dict[str, Any]],
        output_target: str = "llm",
    ) -> Dict[str, Any]:
        """Format observations for LLM or terminal display.

        Args:
            observations: List of observation dicts with id, title, type, etc.
            output_target: 'llm' for agent, 'terminal' for human
        """
        from common_lib.modules.memory.claude_mem_features.dual_formatter import DualFormatter

        formatter = DualFormatter()
        result = formatter.render(observations, output_target=output_target)
        return result

    # ── Phase 5: Lifecycle Hooks ────────────────────────────────

    @mcp.tool()
    async def claude_mem_hook_fire(
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fire a lifecycle hook event.

        Event types: session_start, user_prompt, post_tool_use,
        session_complete, observation, or any custom event.
        """
        from common_lib.modules.memory.claude_mem_features.hooks.handlers import get_hook_registry

        registry = get_hook_registry()
        results = registry.fire(event_type, payload)
        return {"event_type": event_type, "handlers_fired": len(results)}

    @mcp.tool()
    async def claude_mem_hook_status() -> Dict[str, Any]:
        """Get status of all lifecycle hooks and their handler counts."""
        from common_lib.modules.memory.claude_mem_features.hooks.handlers import get_hook_registry

        registry = get_hook_registry()
        return {
            "handler_count": registry.handler_count(),
            "handlers": {
                name: len(handler._callbacks)
                for name, handler in registry._handlers.items()
            },
        }

    # ── Phase 7: Code Intelligence ──────────────────────────────

    @mcp.tool()
    async def claude_mem_code_search(
        query: str,
        path: Optional[str] = None,
        match_types: Optional[List[str]] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search code files for functions, classes, imports by name/pattern.

        Uses tree-sitter AST parsing when available for accurate
        structural analysis, falls back to regex.
        """
        from common_lib.modules.memory.claude_mem_features.code_intelligence.engine import CodeIntelligence
        import asyncio

        ci = CodeIntelligence()
        matches = await asyncio.to_thread(
            ci.smart_search, query, path, match_types, max_results,
        )
        return [m.to_dict() for m in matches]

    @mcp.tool()
    async def claude_mem_code_outline(file_path: str) -> Dict[str, Any]:
        """Get structural outline of a code file.

        Returns imports, classes, functions, methods, decorators,
        variables, call graphs, and inheritance trees.
        """
        from common_lib.modules.memory.claude_mem_features.code_intelligence.engine import CodeIntelligence
        import asyncio

        ci = CodeIntelligence()
        outline = await asyncio.to_thread(ci.smart_outline, file_path)
        return outline.to_dict()

    @mcp.tool()
    async def claude_mem_code_references(
        symbol: str,
        path: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Find all references to a symbol across code files.

        Uses tree-sitter AST for accurate reference detection.
        """
        from common_lib.modules.memory.claude_mem_features.code_intelligence.engine import CodeIntelligence
        import asyncio

        ci = CodeIntelligence()
        refs = await asyncio.to_thread(
            ci.smart_find_references, symbol, path, max_results,
        )
        return refs

    @mcp.tool()
    async def claude_mem_code_call_graph(
        path: str,
        max_depth: int = 3,
    ) -> Dict[str, Any]:
        """Extract function call graph from code files.

        Returns which functions call which other functions.
        Useful for understanding code flow and finding dead code.
        """
        from common_lib.modules.memory.claude_mem_features.code_intelligence.engine import CodeIntelligence
        import asyncio

        ci = CodeIntelligence()
        graph = await asyncio.to_thread(ci.smart_call_graph, path, max_depth)
        return graph

    @mcp.tool()
    async def claude_mem_code_type_hierarchy(path: str) -> Dict[str, Any]:
        """Build class inheritance hierarchy from code files.

        Returns which classes inherit from which base classes.
        """
        from common_lib.modules.memory.claude_mem_features.code_intelligence.engine import CodeIntelligence
        import asyncio

        ci = CodeIntelligence()
        hierarchy = await asyncio.to_thread(ci.smart_type_hierarchy, path)
        return hierarchy

    # ── Phase 8: Process Management ─────────────────────────────

    @mcp.tool()
    async def claude_mem_supervisor_status() -> Dict[str, Any]:
        """Get status of all managed processes (health, restarts, state)."""
        from common_lib.modules.memory.claude_mem_features.process.supervisor import Supervisor

        sup = Supervisor()
        return sup.status()

    @mcp.tool()
    async def claude_mem_supervisor_health_check(
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run health check for a process or all processes."""
        from common_lib.modules.memory.claude_mem_features.process.supervisor import Supervisor

        sup = Supervisor()
        return sup.health_check(name)

    @mcp.tool()
    async def claude_mem_queue_status() -> Dict[str, Any]:
        """Get status of all tasks in the async queue."""
        from common_lib.modules.memory.claude_mem_features.process.queue_processor import SessionQueueProcessor

        queue = SessionQueueProcessor()
        return queue.status()

    @mcp.tool()
    async def claude_mem_queue_enqueue(
        session_id: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Enqueue a task for async processing."""
        from common_lib.modules.memory.claude_mem_features.process.queue_processor import SessionQueueProcessor

        queue = SessionQueueProcessor()
        task = queue.enqueue(session_id, message, metadata)
        return task.to_dict()

    # ── Phase 9: Multi-Platform ─────────────────────────────────

    @mcp.tool()
    async def claude_mem_transcript_parse(
        jsonl_string: str,
    ) -> List[Dict[str, Any]]:
        """Parse multi-line JSONL transcript into normalized events.

        Supports Claude, Gemini, Codex, and OpenCode formats.
        Auto-detects platform for each line.
        """
        from common_lib.modules.memory.claude_mem_features.platforms.transcript_processor import TranscriptEventProcessor

        processor = TranscriptEventProcessor()
        events = processor.parse_string(jsonl_string)
        return [e.to_dict() for e in events]

    @mcp.tool()
    async def claude_mem_transcript_detect_platform(
        jsonl_line: str,
    ) -> Dict[str, Any]:
        """Detect which AI platform a JSONL line belongs to."""
        from common_lib.modules.memory.claude_mem_features.platforms.transcript_processor import TranscriptEventProcessor

        processor = TranscriptEventProcessor()
        platform = processor.detect_platform(jsonl_line)
        return {"platform": platform.value}

    @mcp.tool()
    async def claude_mem_transcript_stats(
        events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Get statistics about parsed transcript events."""
        from common_lib.modules.memory.claude_mem_features.platforms.transcript_processor import TranscriptEventProcessor

        processor = TranscriptEventProcessor()
        return processor.get_stats(events)

    # ── Phase 10: Export/Budget/IDE ─────────────────────────────

    @mcp.tool()
    async def claude_mem_export_create(
        sessions: Optional[List[Dict[str, Any]]] = None,
        observations: Optional[List[Dict[str, Any]]] = None,
        knowledge: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Create a portable MemoryPack for data export.

        Bundles sessions, observations, and knowledge entries into
        a portable format for sharing between instances.
        """
        from common_lib.modules.memory.claude_mem_features.export.exporters import MemoryPack

        pack_creator = MemoryPack()
        return pack_creator.create_pack(
            sessions=sessions,
            observations=observations,
            knowledge=knowledge,
            tags=tags,
            notes=notes,
        )

    @mcp.tool()
    async def claude_mem_export_import(pack: Dict[str, Any]) -> Dict[str, Any]:
        """Import a MemoryPack and extract data."""
        from common_lib.modules.memory.claude_mem_features.export.exporters import MemoryPack

        pack_creator = MemoryPack()
        return pack_creator.import_pack(pack)

    @mcp.tool()
    async def claude_mem_budget_set_limit(
        agent_id: str,
        metric: str,
        limit: float,
    ) -> Dict[str, Any]:
        """Set a budget limit for an agent.

        Metrics: tokens, cost_usd, tool_calls, api_calls.
        """
        from common_lib.modules.memory.claude_mem_features.export.exporters import AgentBudget

        budget = AgentBudget()
        return budget.set_limit(agent_id, metric, limit)

    @mcp.tool()
    async def claude_mem_budget_record_usage(
        agent_id: str,
        metric: str,
        amount: float = 1.0,
    ) -> Dict[str, Any]:
        """Record resource usage for an agent.

        Returns current usage, limit status, and any budget alerts.
        """
        from common_lib.modules.memory.claude_mem_features.export.exporters import AgentBudget

        budget = AgentBudget()
        return budget.record_usage(agent_id, metric, amount)

    @mcp.tool()
    async def claude_mem_budget_get_usage(agent_id: str) -> Dict[str, Any]:
        """Get current usage report for an agent across all metrics."""
        from common_lib.modules.memory.claude_mem_features.export.exporters import AgentBudget

        budget = AgentBudget()
        return budget.get_usage(agent_id)

    @mcp.tool()
    async def claude_mem_budget_alerts(
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get budget alerts, optionally filtered by agent."""
        from common_lib.modules.memory.claude_mem_features.export.exporters import AgentBudget

        budget = AgentBudget()
        return budget.get_alerts(agent_id)

    @mcp.tool()
    async def claude_mem_ide_create_config(
        ide_type: str,
        server_url: str,
        api_key: Optional[str] = None,
        features: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create IDE integration configuration for VS Code, JetBrains, etc."""
        from common_lib.modules.memory.claude_mem_features.export.exporters import IDEIntegrationFactory

        factory = IDEIntegrationFactory()
        return factory.create_config(ide_type, server_url, api_key, features)

    @mcp.tool()
    async def claude_mem_ide_list_supported() -> Dict[str, Any]:
        """List all supported IDE types and their available features."""
        from common_lib.modules.memory.claude_mem_features.export.exporters import IDEIntegrationFactory

        factory = IDEIntegrationFactory()
        return factory.list_supported()

    # ── Feature Flags ───────────────────────────────────────────

    @mcp.tool()
    async def claude_mem_features_list() -> Dict[str, Any]:
        """List all feature flags and their current state."""
        from common_lib.modules.memory.claude_mem_features import FeatureFlags

        return {
            "flags": FeatureFlags.FEATURES.copy(),
            "overrides": dict(FeatureFlags._overrides),
        }

    @mcp.tool()
    async def claude_mem_feature_enable(key: str) -> Dict[str, Any]:
        """Enable a feature flag."""
        from common_lib.modules.memory.claude_mem_features import FeatureFlags

        FeatureFlags.enable(key)
        return {"key": key, "enabled": True}

    @mcp.tool()
    async def claude_mem_feature_disable(key: str) -> Dict[str, Any]:
        """Disable a feature flag."""
        from common_lib.modules.memory.claude_mem_features import FeatureFlags

        FeatureFlags.disable(key)
        return {"key": key, "enabled": False}

    @mcp.tool()
    async def claude_mem_settings_get(key: str) -> Dict[str, Any]:
        """Get a setting value with cascade (env > file > default)."""
        from common_lib.modules.memory.claude_mem_features.settings_cascade import SettingsManager

        mgr = SettingsManager()
        value = mgr.get(key)
        return {"key": key, "value": value}

    @mcp.tool()
    async def claude_mem_settings_set(key: str, value: str) -> Dict[str, Any]:
        """Set a setting value."""
        from common_lib.modules.memory.claude_mem_features.settings_cascade import SettingsManager

        mgr = SettingsManager()
        mgr.set(key, value)
        mgr.save()
        return {"key": key, "value": value, "persisted": True}

    logger.info(
        "Claude-Mem MCP tools registered: 30+ tools across 10 phases"
    )
