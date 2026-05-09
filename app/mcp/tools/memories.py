import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from app.mcp.mcp_dependencies import resolve_memory_service

logger = logging.getLogger("mcp.tools.memories")

def register_memory_tools(mcp: FastMCP):
    """Register tools for deep cognitive memory operations and semantic search."""

    @mcp.tool()
    async def list_memories(skip: int = 0, limit: int = 20, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List cognitive memories with optional type filtering."""
        service = resolve_memory_service()
        memories = await service.list_memories(skip=skip, limit=limit, memory_type=memory_type)
        return memories

    @mcp.tool()
    async def create_memory(content: str, memory_type: str = "episodic", importance: float = 0.5, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store a new cognitive fragment in the memory system."""
        service = resolve_memory_service()
        memory_id = await service.store_memory(
            content=content,
            memory_type=memory_type,
            importance=importance,
            metadata=metadata
        )
        return {"id": memory_id, "status": "stored"}

    @mcp.tool()
    async def update_memory(memory_id: str, importance: Optional[float] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Manually update a memory record's importance or metadata."""
        service = resolve_memory_service()
        success = await service.update_memory(memory_id=memory_id, importance=importance, metadata=metadata)
        return {"success": success}

    @mcp.tool()
    async def delete_memory(memory_id: str) -> Dict[str, Any]:
        """Manually prune a specific cognitive fragment from the memory system."""
        service = resolve_memory_service()
        success = await service.delete_memory(memory_id)
        return {"success": success}

    @mcp.tool()
    async def get_memory_configuration() -> Dict[str, Any]:
        """Retrieve the current cognitive memory system configuration and feature flags."""
        service = resolve_memory_service()
        config = await service.get_configuration()
        return config

    @mcp.tool()
    async def search_memories(query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Execute a semantic search across the cognitive memory stores."""
        service = resolve_memory_service()
        results = await service.search(query=query, limit=limit)
        return results

    @mcp.tool()
    async def get_semantic_topology() -> Dict[str, Any]:
        """Retrieve the current semantic topology, including clusters and concept maps."""
        service = resolve_memory_service()
        clusters = await service.get_semantic_clusters()
        topology = await service.get_semantic_topology()
        return {"clusters": clusters, "topology": topology}

    @mcp.tool()
    async def crystallize_knowledge(focus_area: str) -> Dict[str, Any]:
        """Consolidate conceptual fragments into stable knowledge structures."""
        service = resolve_memory_service()
        result = await service.crystallize_knowledge(focus_area)
        return result

    @mcp.tool()
    async def run_memory_maintenance() -> Dict[str, Any]:
        """Trigger the cognitive maintenance pipeline (pruning, consolidation, and indexing)."""
        service = resolve_memory_service()
        result = await service.run_maintenance()
        return result

    @mcp.tool()
    async def adapt_cognitive_behavior(task_type: str = "introspection", input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Trigger a cognitive adaptation or reflection cycle to evolve behavior."""
        service = resolve_memory_service()
        result = await service.adapt({"type": task_type, "input": input_data or {}})
        return result

    @mcp.tool()
    async def reinforce_cognitive_signal(target_id: str, reward: float, target_type: str = "behavior") -> Dict[str, Any]:
        """Inject a reinforcement signal into the cognitive engine to improve future performance."""
        service = resolve_memory_service()
        success = await service.reinforce({"target_id": target_id, "reward": reward, "target_type": target_type})
        return {"success": success}

    @mcp.tool()
    async def create_strategic_goal(name: str, priority: str = "balanced") -> Dict[str, Any]:
        """Register a new strategic goal for the cognitive system."""
        service = resolve_memory_service()
        goal = await service.create_goal(name=name, priority=priority)
        return goal

    @mcp.tool()
    async def generate_strategic_plan(goal_id: str) -> Dict[str, Any]:
        """Decompose an active goal into a multi-step strategic plan."""
        service = resolve_memory_service()
        plan = await service.generate_strategic_plan(goal_id)
        return plan

    @mcp.tool()
    async def forecast_memory_scenario(scenario_type: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a cognitive simulation to forecast future states based on memory data."""
        service = resolve_memory_service()
        result = await service.run_forecast({"type": scenario_type, "parameters": parameters or {}})
        return result

    @mcp.tool()
    async def get_memory_system_stats() -> Dict[str, Any]:
        """Get live telemetry for the entire memory, adaptation, and strategy ecosystem."""
        service = resolve_memory_service()
        stats = await service.get_stats()
        adaptation = await service.get_adaptation_telemetry()
        strategy = await service.get_strategic_telemetry()
        return {
            "stats": stats,
            "adaptation": adaptation,
            "strategy": strategy
        }

    @mcp.tool()
    async def build_cognitive_context(session_id: str, max_tokens: int = 4000) -> Dict[str, Any]:
        """Assemble prioritized cognitive context for a session."""
        service = resolve_memory_service()
        context = await service.build_context(session_id=session_id, max_tokens=max_tokens)
        return context

    @mcp.tool()
    async def list_cognitive_policies() -> List[Dict[str, Any]]:
        """List active cognitive governance policies (Decay, Dedupe, etc.)."""
        service = resolve_memory_service()
        policies = await service.get_active_policies()
        return policies

    @mcp.tool()
    async def toggle_cognitive_policy(policy_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable a specific cognitive governance policy."""
        service = resolve_memory_service()
        success = await service.toggle_policy(policy_id, enabled)
        return {"success": success}

    @mcp.tool()
    async def list_memory_stores() -> List[Dict[str, Any]]:
        """List registered cognitive stores (Semantic Hub, Episodic Log, etc.)."""
        service = resolve_memory_service()
        stores = await service.get_available_stores()
        return stores

    @mcp.tool()
    async def manage_memory_cache(action: str = "stats", cache_type: str = "all") -> Dict[str, Any]:
        """Get cache performance stats or clear specific memory caches."""
        service = resolve_memory_service()
        if action == "clear":
            success = await service.clear_cache(cache_type)
            return {"success": success}
        else:
            stats = await service.get_cache_stats()
            return stats

    @mcp.tool()
    async def start_reasoning_chain(session_id: str, mode: str = "chain_of_thought") -> Dict[str, Any]:
        """Start a structured logic trace for a cognitive session."""
        service = resolve_memory_service()
        chain_id = await service.start_reasoning_chain(session_id, mode)
        return {"chain_id": chain_id}

    @mcp.tool()
    async def add_reasoning_step(session_id: str, chain_id: str, thought: str, action: Optional[str] = None, observation: Optional[str] = None, confidence: float = 1.0) -> Dict[str, Any]:
        """Add a logical step to an active reasoning chain."""
        service = resolve_memory_service()
        step_id = await service.add_reasoning_step(session_id, chain_id, thought, action, observation, confidence)
        return {"step_id": step_id}

    @mcp.tool()
    async def finalize_reasoning_trace(session_id: str, chain_id: str, conclusion: str) -> Dict[str, Any]:
        """Finalize and persist a reasoning trace with a final conclusion."""
        service = resolve_memory_service()
        chain = await service.complete_reasoning_chain(session_id, chain_id, conclusion)
        return chain

    @mcp.tool()
    async def get_reasoning_trace(session_id: str, chain_id: str) -> Dict[str, Any]:
        """Retrieve the current state of a reasoning trace."""
        service = resolve_memory_service()
        chain = await service.get_reasoning_chain(session_id, chain_id)
        return chain
