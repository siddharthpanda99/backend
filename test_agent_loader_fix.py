import sys
import os
import asyncio

# Add relevant paths
sys.path.append(r'c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend')
sys.path.append(r'c:\Users\91797\Documents\Dev\JS\Monorepo\Python Libs\common_lib\src')

from app.modules.agents.runtime.core.agent_loader import load_agent

def test_load():
    try:
        # Test with a known agent ID
        agent_id = "product_manager_ai"
        print(f"Loading agent: {agent_id}")
        agent = load_agent(
            agent_id=agent_id,
            preload=False # Don't actually load weights
        )
        print("Agent loaded successfully!")
        print(f"Agent ID: {agent.definition.identity.id}")
        print(f"Agent Name: {agent.definition.identity.name}")
    except Exception as e:
        print(f"Load failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_load()
