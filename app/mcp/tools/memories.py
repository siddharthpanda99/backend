import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP
from app.mcp.mcp_dependencies import resolve_memory_service

logger = logging.getLogger("mcp.tools.memories")


def register_memory_tools(mcp: FastMCP):
    """Register tools for deep cognitive memory operations and semantic search."""

    @mcp.tool()
    async def list_memories(
        skip: int = 0, limit: int = 20, memory_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List cognitive memories with optional type filtering."""
        service = resolve_memory_service()
        memories = await service.list_memories(
            skip=skip, limit=limit, memory_type=memory_type
        )
        return memories

    @mcp.tool()
    async def create_memory(
        content: str,
        memory_type: str = "episodic",
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store a new cognitive fragment in the memory system."""
        service = resolve_memory_service()
        memory_id = await service.store_memory(
            content=content,
            memory_type=memory_type,
            importance=importance,
            metadata=metadata,
        )
        return {"id": memory_id, "status": "stored"}

    @mcp.tool()
    async def update_memory(
        memory_id: str,
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Manually update a memory record's importance or metadata."""
        service = resolve_memory_service()
        success = await service.update_memory(
            memory_id=memory_id, importance=importance, metadata=metadata
        )
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
    async def adapt_cognitive_behavior(
        task_type: str = "introspection", input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Trigger a cognitive adaptation or reflection cycle to evolve behavior."""
        service = resolve_memory_service()
        result = await service.adapt({"type": task_type, "input": input_data or {}})
        return result

    @mcp.tool()
    async def reinforce_cognitive_signal(
        target_id: str, reward: float, target_type: str = "behavior"
    ) -> Dict[str, Any]:
        """Inject a reinforcement signal into the cognitive engine to improve future performance."""
        service = resolve_memory_service()
        success = await service.reinforce(
            {"target_id": target_id, "reward": reward, "target_type": target_type}
        )
        return {"success": success}

    @mcp.tool()
    async def create_strategic_goal(
        name: str, priority: str = "balanced"
    ) -> Dict[str, Any]:
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
    async def forecast_memory_scenario(
        scenario_type: str, parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run a cognitive simulation to forecast future states based on memory data."""
        service = resolve_memory_service()
        result = await service.run_forecast(
            {"type": scenario_type, "parameters": parameters or {}}
        )
        return result

    @mcp.tool()
    async def get_memory_system_stats() -> Dict[str, Any]:
        """Get live telemetry for the entire memory, adaptation, and strategy ecosystem."""
        service = resolve_memory_service()
        stats = await service.get_stats()
        adaptation = await service.get_adaptation_telemetry()
        strategy = await service.get_strategic_telemetry()
        return {"stats": stats, "adaptation": adaptation, "strategy": strategy}

    @mcp.tool()
    async def build_cognitive_context(
        session_id: str, max_tokens: int = 4000
    ) -> Dict[str, Any]:
        """Assemble prioritized cognitive context for a session."""
        service = resolve_memory_service()
        context = await service.build_context(
            session_id=session_id, max_tokens=max_tokens
        )
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
    async def manage_memory_cache(
        action: str = "stats", cache_type: str = "all"
    ) -> Dict[str, Any]:
        """Get cache performance stats or clear specific memory caches."""
        service = resolve_memory_service()
        if action == "clear":
            success = await service.clear_cache(cache_type)
            return {"success": success}
        else:
            stats = await service.get_cache_stats()
            return stats

    @mcp.tool()
    async def start_reasoning_chain(
        session_id: str, mode: str = "chain_of_thought"
    ) -> Dict[str, Any]:
        """Start a structured logic trace for a cognitive session."""
        service = resolve_memory_service()
        chain_id = await service.start_reasoning_chain(session_id, mode)
        return {"chain_id": chain_id}

    @mcp.tool()
    async def add_reasoning_step(
        session_id: str,
        chain_id: str,
        thought: str,
        action: Optional[str] = None,
        observation: Optional[str] = None,
        confidence: float = 1.0,
    ) -> Dict[str, Any]:
        """Add a logical step to an active reasoning chain."""
        service = resolve_memory_service()
        step_id = await service.add_reasoning_step(
            session_id, chain_id, thought, action, observation, confidence
        )
        return {"step_id": step_id}

    @mcp.tool()
    async def finalize_reasoning_trace(
        session_id: str, chain_id: str, conclusion: str
    ) -> Dict[str, Any]:
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

    @mcp.tool()
    async def query_memories_mql(mql: str) -> Dict[str, Any]:
        """Execute an MQL (Memory Query Language) query for advanced filtering."""
        from common_lib.modules.memory.memory_mql import MQLEngine

        engine = MQLEngine()
        result = await engine.query(mql)
        return result.dict()

    @mcp.tool()
    async def get_memory_system_health() -> Dict[str, Any]:
        """Get memory system health metrics and alerts."""
        from common_lib.modules.memory.memory_observability import (
            MemoryMetricsCollector,
            AlertEngine,
        )

        collector = MemoryMetricsCollector()
        alert_engine = AlertEngine()
        await alert_engine.check_rules()
        return {
            "health_summary": collector.get_summary().dict(),
            "alerts": alert_engine.get_summary().dict(),
        }

    @mcp.tool()
    async def get_memory_timeline(memory_id: str) -> Dict[str, Any]:
        """Get the full edit history timeline of a memory."""
        from common_lib.modules.memory.memory_versioning import (
            MemoryTimeline,
            DiffStore,
        )

        diff_store = DiffStore()
        timeline = MemoryTimeline(diff_store)
        return await timeline.get_timeline_summary(memory_id)

    @mcp.tool()
    async def run_retrieval_benchmark(
        test_set_id: str, n_queries: int = 50
    ) -> Dict[str, Any]:
        """Run retrieval quality benchmarks (NDCG, MRR)."""
        from common_lib.modules.memory.memory_testing import (
            RetrievalEvaluator,
            EvalQuery,
        )

        evaluator = RetrievalEvaluator()
        queries = [
            EvalQuery(
                id=f"q_{i}",
                text=f"test query {i}",
                agent_id="benchmark",
                relevant_ids=[],
            )
            for i in range(n_queries)
        ]
        report = await evaluator.evaluate(queries, lambda q, a: [])
        return report.dict()

    @mcp.tool()
    async def detect_memory_drift(window_days: int = 7) -> Dict[str, Any]:
        """Detect retrieval quality drift over time."""
        from common_lib.modules.memory.memory_testing import MemoryDriftDetector

        detector = MemoryDriftDetector()
        return {
            "status": "Drift detection requires baseline and test queries to be configured"
        }

    @mcp.tool()
    async def cross_modal_memory_search(
        query: str, modality: Optional[str] = None, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Search memories across different modalities (text, image, code, audio)."""
        from common_lib.modules.memory.memory_multimodal import (
            MultiModalEmbeddingPipeline,
            ModalityType,
        )

        pipeline = MultiModalEmbeddingPipeline()
        results = await pipeline.cross_modal_search(
            query, ModalityType(modality) if modality else None, top_k
        )
        return [
            {
                "memory_id": r.memory.id,
                "score": r.score,
                "modality": r.memory.modality.value,
            }
            for r in results
        ]

    @mcp.tool()
    async def trigger_memory_consolidation(
        agent_id: str, memory_count: int = 100
    ) -> Dict[str, Any]:
        """Trigger memory consolidation with the latency budget."""
        from common_lib.modules.memory.memory_execution import LatencyBudget

        budget = LatencyBudget(total_budget_ms=500)
        return {
            "budget_status": budget.get_status().dict(),
            "consolidation": "simulated",
        }

    @mcp.tool()
    async def get_agent_memory_budget(agent_id: str) -> Dict[str, Any]:
        """Get memory budget status for an agent."""
        from common_lib.modules.memory.memory_economics import BudgetManager

        manager = BudgetManager()
        return (await manager.get_budget_status(agent_id)).dict()

    @mcp.tool()
    async def set_agent_memory_budget(
        agent_id: str, limit_dollars: float
    ) -> Dict[str, Any]:
        """Set memory budget limit for an agent."""
        from common_lib.modules.memory.memory_economics import BudgetManager

        manager = BudgetManager()
        await manager.set_budget_limit(agent_id, limit_dollars)
        return {"agent_id": agent_id, "limit_dollars": limit_dollars, "status": "set"}

    @mcp.tool()
    async def get_cost_effective_retrieval(
        query: str, quality_threshold: float = 0.8, cost_limit: float = 0.001
    ) -> Dict[str, Any]:
        """Retrieve memories using cost-effective strategy selection."""
        from common_lib.modules.memory.memory_economics import CostAwareRetriever

        retriever = CostAwareRetriever()
        result = await retriever.retrieve(query, quality_threshold, cost_limit)
        return {
            "strategy": result.strategy.value,
            "quality_score": result.quality_score,
            "cost": result.cost,
            "latency_ms": result.latency_ms,
            "result_count": len(result.memories),
        }

    @mcp.tool()
    async def get_agent_persona(agent_id: str) -> Dict[str, Any]:
        """Get or create persona for an agent."""
        from common_lib.modules.memory.memory_persona import PersonaManager

        manager = PersonaManager()
        persona = await manager.get_persona(agent_id)
        return persona.dict()

    @mcp.tool()
    async def update_persona_from_interaction(
        agent_id: str,
        user_id: str,
        trust_delta: float = 0.0,
        preferred_shorter: bool = False,
    ) -> Dict[str, Any]:
        """Update agent persona based on user interaction."""
        from common_lib.modules.memory.memory_persona import (
            PersonaManager,
            InteractionSummary,
        )

        manager = PersonaManager()
        interaction = InteractionSummary(
            user_id=user_id,
            trust_delta=trust_delta,
            user_preferred_shorter=preferred_shorter,
        )
        persona = await manager.update_from_interaction(agent_id, interaction)
        return {"status": "updated", "persona_id": persona.agent_id}

    @mcp.tool()
    async def generate_persona_context(agent_id: str, user_id: str) -> str:
        """Generate system prompt from agent persona and user relationship."""
        from common_lib.modules.memory.memory_persona import PersonaManager

        manager = PersonaManager()
        return await manager.generate_context_from_persona(agent_id, user_id)

    @mcp.tool()
    async def discover_causal_graph(
        agent_id: str, method: str = "granger"
    ) -> Dict[str, Any]:
        """Discover causal relationships from agent memories."""
        from common_lib.modules.memory.memory_causal import CausalDiscoveryEngine

        engine = CausalDiscoveryEngine()
        graph = await engine.discover_from_memories([], method=method)
        return engine.get_graph_summary(graph)

    @mcp.tool()
    async def compute_causal_effect(
        agent_id: str, intervention: str, query_var: str
    ) -> Dict[str, Any]:
        """Compute causal effect of an intervention (do-calculus)."""
        from common_lib.modules.memory.memory_causal import (
            CausalDiscoveryEngine,
            CausalGraph,
        )

        engine = CausalDiscoveryEngine()
        graph = CausalGraph()
        result = await engine.do_calculus(graph, intervention, query_var)
        return result.dict()

    @mcp.tool()
    async def find_root_causes(agent_id: str, effect_node: str) -> List[Dict[str, Any]]:
        """Find root causes of a memory node."""
        from common_lib.modules.memory.memory_causal import CausalDiscoveryEngine

        engine = CausalDiscoveryEngine()
        graph = await engine.discover_from_memories([])
        causes = await engine.find_root_causes(graph, effect_node)
        return [c.dict() for c in causes]
