import sys
import os
import json
import asyncio

# Add relevant paths
sys.path.append(r'c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend')
sys.path.append(r'c:\Users\91797\Documents\Dev\JS\Monorepo\Python Libs\common_lib\src')

from app.modules.entities.routes.registry import list_entities

async def main():
    resp = await list_entities(entity_type=None)
    data = resp.data
    print(f"Keys in registry: {data.keys()}")
    print(f"Total agents in response: {len(data.get('agents', []))}")
    print(f"Total models in response: {len(data.get('models', []))}")
    
    # Check the format of the first agent
    if data.get('agents'):
        print(f"First agent ID: {data['agents'][0].get('id')}")
        # print(json.dumps(data['agents'][0], indent=2))

if __name__ == "__main__":
    asyncio.run(main())
