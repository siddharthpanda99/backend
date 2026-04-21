import sys
import os
import json
import asyncio

# Setup path
sys.path.append(os.getcwd())

from app.modules.plugins.routes.router import _load_kb_graph

async def test():
    print("Loading KB graph from database...")
    try:
        from app.modules.plugins.routes.router import _load_kb_graph
        graph = _load_kb_graph()
        print(f"Nodes: {len(graph['nodes'])}")
        print(f"Edges: {len(graph['edges'])}")
        print(f"Categories: {len(graph['categories'])}")
        
        if len(graph['nodes']) > 0:
            print("\nSample Node:")
            import json
            print(json.dumps(graph['nodes'][0], indent=2))
        else:
            print("\n!!! NO NODES FOUND !!!")
    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
