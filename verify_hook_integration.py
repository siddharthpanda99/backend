import asyncio
import logging
import json
from common_lib.modules.orchestration.hooks.loader import get_hook_engine
from common_lib.modules.orchestration.hooks.base import HookContext

# Setup logging to see the Hook outputs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_destructive_blocking():
    print("\n--- TEST: Destructive Action Blocking ---")
    engine = get_hook_engine()
    
    # Context for a DESTRUCTIVE action with safety config requiring approval
    context = HookContext(
        task_id="task_123",
        step_id="step_1",
        agent_id="security_agent",
        skill="delete_database_records",
        input={"query": "DELETE FROM users"},
        metadata={
            "safety": {
                "human_in_the_loop": {
                    "required_for": ["destructive"],
                    "escalation_policy": "halt"
                }
            }
        }
    )
    
    async def dummy_executor(ctx):
        return "DATABASE DELETED!" # This should NOT be reached

    result = await engine.execute_with_hooks(context, dummy_executor)
    
    print(f"Final Result: {result}")
    if "Blocked" in str(result):
        print("[SUCCESS] Destructive action was correctly blocked.")
    else:
        print("[FAILURE] Destructive action was NOT blocked.")

async def test_read_allow():
    print("\n--- TEST: Read Action Allowance ---")
    engine = get_hook_engine()
    
    # Context for a READ action
    context = HookContext(
        task_id="task_456",
        step_id="step_1",
        agent_id="research_agent",
        skill="web_search",
        input={"query": "Claude Code++ specs"},
        metadata={"safety": {}}
    )
    
    async def dummy_executor(ctx):
        return "Search results: Claude Code++ is amazing."

    result = await engine.execute_with_hooks(context, dummy_executor)
    
    print(f"Final Result: {result}")
    if "Search results" in str(result):
        print("[SUCCESS] Read action was allowed.")
    else:
        print("[FAILURE] Read action was blocked unexpectedly.")

if __name__ == "__main__":
    asyncio.run(test_destructive_blocking())
    asyncio.run(test_read_allow())
