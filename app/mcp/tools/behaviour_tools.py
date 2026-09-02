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

    # ── Personality Profile Tools ────────────────────────────────

    @mcp.tool()
    async def list_personality_profiles() -> List[Dict[str, Any]]:
        """List all 8 personality profiles (GAUDE, IRONCLAD, MAD SCIENTIST, FEYNMAN, RED TEAM, PRAGMATIST, ARCHITECT, CHAOS GARDENER)."""
        from common_lib.modules.orchestration.behaviour.presets import list_personalities
        profiles = list_personalities()
        return [{"id": p.id, "name": p.name, "description": p.description, "traits": p.traits, "best_for": p.best_for} for p in profiles]

    @mcp.tool()
    async def get_personality_profile(profile_id: str) -> Dict[str, Any]:
        """Get a specific personality profile with full trait vectors."""
        from common_lib.modules.orchestration.behaviour.presets import get_personality
        profile = get_personality(profile_id)
        if not profile:
            return {"error": f"Personality '{profile_id}' not found"}
        return profile.model_dump()

    @mcp.tool()
    async def get_personality_matrix() -> List[Dict[str, Any]]:
        """Get the personality comparison matrix — all profiles side by side."""
        from common_lib.modules.orchestration.behaviour.presets import get_personality_matrix
        return get_personality_matrix()

    @mcp.tool()
    async def ab_test_personalities(profile_a: str, profile_b: str, task_type: str = "general") -> Dict[str, Any]:
        """A/B test two personality profiles — compare trait vectors and determine advantages."""
        from common_lib.modules.orchestration.behaviour.presets import get_personality
        pa = get_personality(profile_a)
        pb = get_personality(profile_b)
        if not pa or not pb:
            return {"error": "Profile not found"}
        all_traits = set(pa.traits.keys()) | set(pb.traits.keys())
        diffs = {t: {"a": pa.traits.get(t, 0), "b": pb.traits.get(t, 0), "delta": round(pa.traits.get(t, 0) - pb.traits.get(t, 0), 3)} for t in all_traits}
        return {"profile_a": profile_a, "profile_b": profile_b, "task_type": task_type, "differences": diffs}

    @mcp.tool()
    async def mutate_personality(profile_id: str, trait: str, delta: float = 0.10) -> Dict[str, Any]:
        """Create a mutated variant by adjusting a single trait."""
        from common_lib.modules.orchestration.behaviour.presets import get_personality
        p = get_personality(profile_id)
        if not p:
            return {"error": f"Profile '{profile_id}' not found"}
        old = p.traits.get(trait, 0.5)
        new = max(0.0, min(1.0, old + delta))
        return {"original": profile_id, "trait": trait, "old": old, "new": round(new, 3), "delta": delta}

    @mcp.tool()
    async def combine_personalities(profile_a: str, profile_b: str, weight_a: float = 0.5, weight_b: float = 0.5) -> Dict[str, Any]:
        """Combine two personalities with weighted averaging."""
        from common_lib.modules.orchestration.behaviour.presets import get_personality
        pa = get_personality(profile_a)
        pb = get_personality(profile_b)
        if not pa or not pb:
            return {"error": "Profile not found"}
        total = weight_a + weight_b or 1.0
        wa, wb = weight_a / total, weight_b / total
        all_traits = set(pa.traits.keys()) | set(pb.traits.keys())
        combined = {t: round(pa.traits.get(t, 0) * wa + pb.traits.get(t, 0) * wb, 3) for t in all_traits}
        return {"profile_a": profile_a, "profile_b": profile_b, "weights": {"a": wa, "b": wb}, "traits": combined}

    @mcp.tool()
    async def list_simulation_scenarios() -> List[Dict[str, Any]]:
        """List all predefined simulation scenarios (ambiguous task, production incident, etc.)."""
        from common_lib.modules.orchestration.behaviour.api import SIMULATION_SCENARIOS
        return SIMULATION_SCENARIOS

    @mcp.tool()
    async def run_personality_simulation(profile_id: str, scenario_id: str) -> Dict[str, Any]:
        """Run a personality against a simulation scenario and score effectiveness."""
        from common_lib.modules.orchestration.behaviour.presets import get_personality
        from common_lib.modules.orchestration.behaviour.api import SIMULATION_SCENARIOS
        p = get_personality(profile_id)
        if not p:
            return {"error": f"Profile '{profile_id}' not found"}
        scenario = next((s for s in SIMULATION_SCENARIOS if s["id"] == scenario_id), None)
        if not scenario:
            return {"error": f"Scenario '{scenario_id}' not found"}
        matches = {t: p.traits.get(t, 0) for t in scenario["expected_traits"]}
        avg = sum(matches.values()) / len(matches) if matches else 0
        risk = {"low": 1.0, "medium": 0.8, "high": 0.6}.get(scenario["risk"], 0.8)
        return {"profile": profile_id, "scenario": scenario_id, "matches": matches, "effectiveness": round(avg * risk, 3)}

    @mcp.tool()
    async def run_personality_regression(profile_id: str) -> Dict[str, Any]:
        """Run regression tests against a personality (safety, bounds, guardrails)."""
        from common_lib.modules.orchestration.behaviour.presets import get_personality
        p = get_personality(profile_id)
        if not p:
            return {"error": f"Profile '{profile_id}' not found"}
        results = [{"test": "trait_bounds", "passed": all(0 <= v <= 1 for v in p.traits.values())}]
        return {"profile": profile_id, "results": results, "all_passed": all(r["passed"] for r in results)}

    @mcp.tool()
    async def get_personality_graph(profile_id: str) -> Dict[str, Any]:
        """Get trait relationship graph for rendering (nodes + edges)."""
        from common_lib.modules.orchestration.behaviour.presets import get_personality
        p = get_personality(profile_id)
        if not p:
            return {"error": f"Profile '{profile_id}' not found"}
        nodes = [{"id": t, "label": t.replace("_", " ").title(), "value": v} for t, v in p.traits.items()]
        edges = []
        tl = list(p.traits.keys())
        for i, t1 in enumerate(tl):
            for t2 in tl[i + 1:]:
                w = round(p.traits[t1] * p.traits[t2], 3)
                if w > 0.5:
                    edges.append({"source": t1, "target": t2, "weight": w})
        return {"profile": profile_id, "nodes": nodes, "edges": edges}

    # ── Evolution Engine (§57) ──────────────────────────────────────

    @mcp.tool()
    async def record_evolution_signal(profile_id: str, task_type: str = "general", outcome: str = "success", quality_score: float = 0.5) -> Dict[str, Any]:
        """Record a feedback signal from task execution for personality evolution."""
        from common_lib.modules.orchestration.behaviour.evolution.engine import EvolutionEngine, FeedbackSignal
        engine = EvolutionEngine()
        signal = engine.record_signal(FeedbackSignal(profile_id=profile_id, task_type=task_type, outcome=outcome, quality_score=quality_score))
        return {"signal_id": signal.id, "profile_id": signal.profile_id}

    @mcp.tool()
    async def analyze_evolution(profile_id: str) -> Dict[str, Any]:
        """Analyze feedback signals and generate mutation proposals for a personality."""
        from common_lib.modules.orchestration.behaviour.evolution.engine import EvolutionEngine
        return EvolutionEngine().analyze(profile_id).model_dump()

    @mcp.tool()
    async def get_evolution_proposals(profile_id: str = "", status: str = "") -> Dict[str, Any]:
        """List mutation proposals from the evolution engine."""
        from common_lib.modules.orchestration.behaviour.evolution.engine import EvolutionEngine
        proposals = EvolutionEngine().get_proposals(profile_id=profile_id, status=status)
        return {"proposals": [p.model_dump() for p in proposals], "total": len(proposals)}

    @mcp.tool()
    async def approve_evolution_proposal(proposal_id: str) -> Dict[str, Any]:
        """Approve a mutation proposal for later application."""
        from common_lib.modules.orchestration.behaviour.evolution.engine import EvolutionEngine
        result = EvolutionEngine().approve_proposal(proposal_id)
        return result.model_dump() if result else {"error": "Not found"}

    # ── Marketplace (§46) ──────────────────────────────────────────

    @mcp.tool()
    async def search_marketplace(query: str = "", entry_type: str = "", sort: str = "rating") -> Dict[str, Any]:
        """Search the personality marketplace for trait packs, profiles, skins, etc."""
        from common_lib.modules.orchestration.behaviour.evolution.marketplace import MarketplaceStore
        results = MarketplaceStore().search(query=query, entry_type=entry_type, sort=sort)
        return {"entries": [e.model_dump() for e in results], "total": len(results)}

    @mcp.tool()
    async def install_marketplace_entry(entry_id: str) -> Dict[str, Any]:
        """Install a marketplace entry (increment download, return content)."""
        from common_lib.modules.orchestration.behaviour.evolution.marketplace import MarketplaceStore
        result = MarketplaceStore().install(entry_id)
        return result or {"error": "Entry not found"}

    @mcp.tool()
    async def rate_marketplace_entry(entry_id: str, rating: float) -> Dict[str, Any]:
        """Rate a marketplace entry (0-5 stars)."""
        from common_lib.modules.orchestration.behaviour.evolution.marketplace import MarketplaceStore
        result = MarketplaceStore().rate(entry_id, rating)
        return result or {"error": "Entry not found"}

    # ── DSL (§47) ──────────────────────────────────────────────────

    @mcp.tool()
    async def compile_personality_dsl(dsl_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and compile a DSL personality definition into a behavioral contract."""
        from common_lib.modules.orchestration.behaviour.evolution.dsl import compile_from_dict, to_prompt_section
        contract = compile_from_dict(dsl_definition)
        prompt = to_prompt_section(contract)
        return {"contract": contract.model_dump(), "prompt_section": prompt}

    # ── CI/CD Pipeline (§60) ───────────────────────────────────────

    @mcp.tool()
    async def start_cicd_pipeline(profile_id: str, version: str = "1.0.0", trigger: str = "manual") -> Dict[str, Any]:
        """Start a CI/CD pipeline for personality version management."""
        from common_lib.modules.orchestration.behaviour.evolution.cicd import CIDCPipeline
        run = CIDCPipeline().start_pipeline(profile_id=profile_id, version=version, trigger=trigger)
        return run.model_dump()

    @mcp.tool()
    async def execute_cicd_all_stages(run_id: str, profile_data: Dict[str, Any] = {}) -> Dict[str, Any]:
        """Execute all stages in a CI/CD pipeline sequentially."""
        from common_lib.modules.orchestration.behaviour.evolution.cicd import CIDCPipeline
        pipeline = CIDCPipeline()
        run = pipeline.get_run(run_id)
        if not run:
            return {"error": "Run not found"}
        for stage in CIDCPipeline.STAGE_NAMES:
            run = pipeline.execute_stage(run_id, stage, profile_data=profile_data)
            if run and run.status == "failed":
                break
        return run.model_dump() if run else {}

    # ── Culture (§54) ──────────────────────────────────────────────

    @mcp.tool()
    async def get_engineering_culture(personality_id: str) -> Dict[str, Any]:
        """Get the engineering culture mapped to a personality profile."""
        from common_lib.modules.orchestration.behaviour.evolution.culture import get_culture
        culture = get_culture(personality_id)
        return culture.model_dump() if culture else {"error": "Culture not found"}

    # ── Demo (§53) ─────────────────────────────────────────────────

    @mcp.tool()
    async def compare_personalities_on_task(task_id: str, profile_ids: List[str] = []) -> Dict[str, Any]:
        """Compare how different personalities approach the same task."""
        from common_lib.modules.orchestration.behaviour.evolution.demo import compare_personalities
        return compare_personalities(task_id, profile_ids)

    # ── Inheritance (§32) ──────────────────────────────────────────

    @mcp.tool()
    async def resolve_personality_inheritance(profile_id: str, modifiers: List[Dict[str, Any]] = []) -> Dict[str, Any]:
        """Resolve the full inheritance chain for a personality profile."""
        from common_lib.modules.orchestration.behaviour.evolution.inheritance import resolve_inheritance, InheritanceModifier
        from common_lib.modules.orchestration.behaviour.presets import list_personalities
        mods = [InheritanceModifier(**m) for m in modifiers]
        profiles = {p.id: p for p in list_personalities()}
        chain = resolve_inheritance(profile_id, profiles, modifiers=mods or None)
        return chain.model_dump()

    logger.info(f"[MCP] Registered 42 behaviour tools")
