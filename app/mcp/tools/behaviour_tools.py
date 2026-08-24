"""
MCP Tools for Agent Behaviour Modifier System
──────────────────────────────────────────────
Exposes all behaviour operations as MCP tools so external agents
can query and modify behavioural configurations.

Categories:
  - Toggle: tool groups, modes, reasoning
  - Resolve: full resolution pipeline
  - Registry: traits, strategies, flavours, profiles
  - Planning: behaviour-aware execution plans
  - Evaluation: 8-dimension scoring, simulation, golden tests
  - Memory: episodes, patterns, feedback
  - Observability: decisions, drift, provenance, timeline
"""
import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.behaviour")


def register_behaviour_tools(mcp: FastMCP):
    """Register tools for managing agent behaviour configurations."""

    # ── Toggle Tools ────────────────────────────────────────────────────

    @mcp.tool()
    async def get_behaviour_state() -> Dict[str, Any]:
        """Get the complete behaviour modifier state across all three tiers (tool groups, modes, reasoning)."""
        from common_lib.modules.orchestration.behaviour.service import BehaviourModifierService
        svc = BehaviourModifierService()
        return svc.get_state().model_dump()

    @mcp.tool()
    async def toggle_behaviour_feature(feature: str, enabled: bool = True, value: Optional[str] = None) -> Dict[str, Any]:
        """Toggle any behaviour feature. Feature paths: tool_groups.*, modes.*, reasoning.*"""
        from common_lib.modules.orchestration.behaviour.service import BehaviourModifierService
        svc = BehaviourModifierService()
        return svc.toggle(feature, enabled=enabled, value=value)

    @mcp.tool()
    async def apply_behaviour_profile(profile_name: str) -> Dict[str, Any]:
        """Apply a named behaviour preset (production, development, research, minimal)."""
        from common_lib.modules.orchestration.behaviour.service import BehaviourModifierService
        svc = BehaviourModifierService()
        success = svc.apply_profile(profile_name)
        return {"success": success, "profile": profile_name}

    # ── Resolver Tools ──────────────────────────────────────────────────

    @mcp.tool()
    async def resolve_behaviour(context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the full behaviour resolution pipeline — precedence, conflicts, overrides, conditions."""
        from common_lib.modules.orchestration.behaviour.resolver.resolver import BehaviourResolver, LayerConfig
        from common_lib.modules.orchestration.behaviour.service import BehaviourModifierService
        resolver = BehaviourResolver()
        svc = BehaviourModifierService()
        for key in ["reasoning_level", "autonomy_level"]:
            val = svc.get_reasoning_config().model_dump().get(key)
            if val:
                resolver.add_layer(LayerConfig(scope="system", dimensions={key: val}))
        state = resolver.resolve(context)
        return state.model_dump()

    @mcp.tool()
    async def compile_behaviour_prompt(state: Optional[Dict[str, Any]] = None) -> str:
        """Compile behaviour state into a minimal system prompt section for token-efficient injection."""
        from common_lib.modules.orchestration.behaviour.compiler.compiler import BehaviourCompiler
        from common_lib.modules.orchestration.behaviour.resolver.resolver import ResolvedState
        compiler = BehaviourCompiler()
        rs = ResolvedState(**(state or {}))
        return compiler.compile_for_prompt(rs)

    # ── Registry Tools ──────────────────────────────────────────────────

    @mcp.tool()
    async def list_behaviour_traits() -> List[Dict[str, Any]]:
        """List all registered behaviour traits (rigorous, curious, skeptical, etc.)."""
        from common_lib.modules.orchestration.behaviour.registry.registry import BehaviourRegistry
        reg = BehaviourRegistry()
        return [t.model_dump() for t in reg.list_by_kind("trait")]

    @mcp.tool()
    async def list_behaviour_strategies() -> List[Dict[str, Any]]:
        """List all registered behaviour strategies (evidence-first, breadth-first, etc.)."""
        from common_lib.modules.orchestration.behaviour.registry.registry import BehaviourRegistry
        reg = BehaviourRegistry()
        return [s.model_dump() for s in reg.list_by_kind("strategy")]

    @mcp.tool()
    async def list_behaviour_flavours() -> List[Dict[str, Any]]:
        """List all registered behaviour flavours (rigorous-researcher, creative-explorer, etc.)."""
        from common_lib.modules.orchestration.behaviour.registry.registry import BehaviourRegistry
        reg = BehaviourRegistry()
        return [f.model_dump() for f in reg.list_by_kind("flavour")]

    @mcp.tool()
    async def search_behaviour_registry(query: str, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search the behaviour registry by keyword across traits, strategies, flavours, policies."""
        from common_lib.modules.orchestration.behaviour.registry.search import BehaviourSearch
        from common_lib.modules.orchestration.behaviour.registry.registry import BehaviourRegistry
        search = BehaviourSearch(BehaviourRegistry())
        results = search.query(query, kind=kind)
        return [r.model_dump() for r in results]

    # ── Planning Tools ──────────────────────────────────────────────────

    @mcp.tool()
    async def plan_behaviour_execution(exploration: str = "balanced", rigour: str = "normal", risk: str = "moderate") -> Dict[str, Any]:
        """Generate a behaviour-aware execution plan with decomposition, retry, validation, and escalation config."""
        from common_lib.modules.orchestration.behaviour.planning.planner import BehaviourPlanner
        planner = BehaviourPlanner()
        planner.from_dimensions(exploration=exploration, rigour=rigour, risk=risk)
        return {
            "max_depth": planner.decomposition.max_depth,
            "max_breadth": planner.decomposition.max_breadth,
            "max_retries": planner.retry.max_retries,
            "validation_passes": planner.validation.max_validation_passes,
            "escalation_risk_threshold": planner.escalation.risk_threshold,
        }

    # ── Evaluation Tools ────────────────────────────────────────────────

    @mcp.tool()
    async def evaluate_behaviour(behaviour_id: str, episode: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Evaluate a behaviour across 8 dimensions (quality, correctness, satisfaction, reliability, novelty, risk, latency, cost)."""
        from common_lib.modules.orchestration.behaviour.evaluation.evaluator import BehaviourEvaluator
        evaluator = BehaviourEvaluator()
        result = evaluator.evaluate(behaviour_id, episode or {})
        return result.model_dump()

    @mcp.tool()
    async def simulate_behaviour(config: Dict[str, Any], task_type: str = "general") -> Dict[str, Any]:
        """Simulate behaviour outcome before execution — predicts quality, cost, latency, success rate."""
        from common_lib.modules.orchestration.behaviour.evaluation.simulator import BehaviourSimulator
        simulator = BehaviourSimulator()
        result = simulator.simulate(config, task_type=task_type)
        return result.model_dump()

    @mcp.tool()
    async def run_golden_tests() -> Dict[str, Any]:
        """Run golden behaviour invariant tests (no negative cost, safety override works, guardrails immutable, etc.)."""
        from common_lib.modules.orchestration.behaviour.evaluation.golden import GoldenTestRunner
        runner = GoldenTestRunner()
        for test in runner.get_built_in_tests():
            runner.register(test)
        suite = runner.run({})
        return {"pass_rate": suite.pass_rate, "all_passed": suite.all_passed, "total": len(suite.results)}

    # ── Memory Tools ────────────────────────────────────────────────────

    @mcp.tool()
    async def list_behaviour_episodes(task_type: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        """List recent behavioural episodes with outcome tracking."""
        from common_lib.modules.orchestration.behaviour.memory.episodic import EpisodicStore
        store = EpisodicStore()
        eps = store.query(task_type=task_type or None, limit=limit)
        return [e.model_dump() for e in eps]

    @mcp.tool()
    async def get_episode_stats() -> Dict[str, Any]:
        """Get aggregate statistics across all behavioural episodes."""
        from common_lib.modules.orchestration.behaviour.memory.episodic import EpisodicStore
        return EpisodicStore().stats()

    # ── Observability Tools ─────────────────────────────────────────────

    @mcp.tool()
    async def record_behaviour_decision(stage: str, question: str, selected: str, confidence: float = 0.5, reason: str = "") -> Dict[str, Any]:
        """Record a behavioural decision for traceability and explainability."""
        from common_lib.modules.orchestration.behaviour.integration.observability_adapter import get_observability_behaviour_adapter
        adapter = get_observability_behaviour_adapter()
        return adapter.emit_decision(stage, question, selected, confidence=confidence, reason=reason)

    @mcp.tool()
    async def check_behaviour_drift() -> List[Dict[str, Any]]:
        """Check for behavioural drift — quality decline, cost increase, unexpected choices."""
        from common_lib.modules.orchestration.behaviour.integration.observability_adapter import get_observability_behaviour_adapter
        adapter = get_observability_behaviour_adapter()
        return adapter.check_drift()

    @mcp.tool()
    async def explain_behaviour_choice(dimension: str) -> Dict[str, Any]:
        """Explain why the system chose a specific value for a behavioural dimension."""
        from common_lib.modules.orchestration.behaviour.observability.explainability import ExplainabilityEngine
        engine = ExplainabilityEngine()
        exp = engine.explain(dimension, {"resolved_value": "auto", "winning_scope": "system"})
        return exp.model_dump()

    @mcp.tool()
    async def get_behaviour_timeline(execution_id: str = "") -> Dict[str, Any]:
        """Get the behaviour timeline for debugging — all decisions, state transitions, events, errors."""
        from common_lib.modules.orchestration.behaviour.observability.debugger import BehaviourTimelineDebugger
        debugger = BehaviourTimelineDebugger(execution_id)
        return debugger.get_summary()

    logger.info(f"[MCP] Registered 18 behaviour tools")
