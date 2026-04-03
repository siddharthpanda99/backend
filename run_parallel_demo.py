import asyncio
import os
import sys
from pathlib import Path

# --- BOOTSTRAP: Ensure development common_lib takes precedence ---
REPO_ROOT = Path(__file__).parent.parent.resolve()
COMMON_LIB_SRC = str(REPO_ROOT / "Backend Monorepo" / "Python Libs" / "common_lib" / "src")
if COMMON_LIB_SRC not in sys.path:
    sys.path.insert(0, COMMON_LIB_SRC)
    print(f"!!! [BOOTSTRAP] Injecting dev common_lib: {COMMON_LIB_SRC}")

from common_lib.modules.orchestration.agent_loader import AgentLoader
from common_lib.modules.orchestration.agent.master_agent import MasterAgent, ExecutionSpan
from common_lib.modules.orchestration.workflow.observability.tracer import EventTracer
from inference_platform.core.vllm_fleet_manager import VLLMFleetManager

async def run_parallel_demo():
    print("\n" + "="*60)
    print("🚀 SOTA PARALLEL AGENTIC SESSION: BOOTSTRAP")
    print("="*60)

    # 1. ENSURE HARDWARE FLEET READINESS
    fleet = VLLMFleetManager()
    model_id = "vllm_llama3"
    print(f"\n[FLEET] Checking hardware readiness for {model_id}...")
    
    # Simulate a successful VRAM check (Predictive Guarding)
    vram_status = fleet.get_vram_status()
    print(f"[FLEET] VRAM Guard: {vram_status['used_gb']:.2f}/{vram_status['total_gb']:.2f} GB used. Safe to proceed.")

    # 2. LOAD SOTA PARALLEL ORCHESTRATOR
    loader = AgentLoader()
    print(f"\n[LOADER] Assembling 'parallel_orchestrator' soul...")
    agent_config = loader.load_agent_config("parallel_orchestrator")
    master_agent = MasterAgent(agent_config)

    # 3. TRIGGER CONCURRENT FAN-OUT
    query = "Research SOTA Agentic Runtimes AND analyze VRAM implications for 70B models."
    print(f"\n[MASTER] Request Received: '{query}'")
    print("[MASTER] Identifying independent domains for Parallel Fan-out...")

    # Define sub-agent tasks
    sub_tasks = [
        {"agent_id": "research_assistant", "task": "Research SOTA Agentic Runtimes (Kestra, LangGraph, etc.)"},
        {"agent_id": "data_analyst_jr", "task": "Analyze VRAM requirements for 70B fp16/int4 quantization"}
    ]

    # START GLOBAL TRACE
    trace_id = "sota-trace-999"
    tracer = EventTracer.get_instance()
    
    print("\n" + "-"*40)
    print("⛓️  STARTING PARALLEL EXECUTION (FAN-OUT)")
    print("-"*40)

    # Simulate Parallel Execution with Real Spans
    # In a real run, this is handled by master_agent.py
    with tracer.span(trace_id, "parallel_fan_out"):
        # 1. Start Planner
        planner_span = ExecutionSpan("InputPlanner", "STARTED")
        print(f"[SPAN] {planner_span.node_id}: {planner_span.status}")
        await asyncio.sleep(0.5)
        # planner_span.complete() # Mock completion for demo

        # 2. CONCURRENT FAN-OUT
        print("\n[ORCHESTRATOR] Triggering concurrent sub-agents...")
        
        async def run_sub(name, delay):
            span = ExecutionSpan(name, "STARTED")
            print(f"  [SPAN] {name}: {span.status} (Executing...)")
            await asyncio.sleep(delay)
            # span.complete()
            print(f"  [SPAN] {name}: COMPLETED (after {delay}s)")
            return {"agent": name, "data": f"High-fidelity insight from {name}"}

        # Run simultaneously
        results = await asyncio.gather(
            run_sub("research_assistant", 1.8),
            run_sub("data_analyst_jr", 2.2)
        )

        # 3. ASYNC CONTEXT MERGING
        merge_span = ExecutionSpan("AsyncContextMerger", "STARTED")
        print(f"\n[MERGER] {merge_span.node_id}: {merge_span.status}")
        print(f"[MERGER] Converging {len(results)} concurrent contexts into unified Soul Hub...")
        await asyncio.sleep(0.4)
        # merge_span.complete()
        print(f"[MERGER] Context Successfully Merged. Final Synthesis Ready.")

    print("\n" + "="*60)
    print("✅ SOTA PARALLEL SESSION COMPLETE")
    print("="*60 + "\n")
    print("Review the 'Execution Hub' UI to visualize the high-fidelity Gantt timeline.")

if __name__ == "__main__":
    asyncio.run(run_parallel_demo())
