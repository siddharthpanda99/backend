import asyncio
import logging
from common_lib.modules.orchestration.agents.multi_agent import MultiAgentCoordinator

logging.basicConfig(level=logging.INFO)

async def test_loop():
    # The agentic loop handles image generation via ExecutorAgent inside MultiAgentCoordinator
    # The tool parses "image generate" keywords in task description.
    
    # We create a dummy planner that just returns a single task to generate image
    class MockPlanner:
        async def plan(self, req, agents, ctx):
            return [{"agent": "executor", "description": req}]
            
    class MockCritic:
        async def critique(self, *args, **kwargs):
            return {"status": "approved", "feedback": "Looks good"}
            
    coord = MultiAgentCoordinator(planner=MockPlanner(), critic=MockCritic())
    result = await coord.execute("generate an image of a beautiful sunset over the mountains", use_critic=True)
    
    print("Execution completed!")
    for task in result.tasks:
        print(f"Task: {task.description} | Status: {task.status}")
        if task.result:
            print(f"Result: {task.result}")

if __name__ == "__main__":
    asyncio.run(test_loop())
