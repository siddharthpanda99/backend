from common_lib.modules.core_infrastructure.registry import RegistryService
from common_lib.modules.orchestration.workflow.execution.core import ExecutionEngine
from common_lib.modules.orchestration.workflow.execution.context import ExecutionContext
import torch
import numpy as np

registry = RegistryService()
registry.auto_register_common_lib_tools()

engine = ExecutionEngine(registry=registry)
context = ExecutionContext(agent_id="test", role="executor")

# Create a dummy white image tensor [1, 512, 512, 3]
img = torch.ones((1, 512, 512, 3), dtype=torch.float32)

print("Executing Face DNA Analyst...")
result = engine.execute_tool("vision.face_analysis", {"image": img}, context)

print(f"Status: {result.status}")
if result.status == "success":
    print(f"Output type: {type(result.output)}")
    print(f"Output: {result.output}")
else:
    print(f"Error: {result.error}")
