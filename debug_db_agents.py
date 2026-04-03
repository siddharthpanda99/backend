import sys
import os

# Add relevant paths
sys.path.append(r'c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend')
sys.path.append(r'c:\Users\91797\Documents\Dev\JS\Monorepo\Python Libs\common_lib\src')

import json
from app.core.common_lib_integration import common_memory

agents = common_memory.list_agent_definitions()
if agents:
    print(json.dumps(agents[0], indent=2))
