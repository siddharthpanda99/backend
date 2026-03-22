from common_lib.modules.orchestration.workflow.execution.core import ExecutionEngine
from common_lib.modules.orchestration.workflow.execution.context import ExecutionContext
from common_lib.modules.core_infrastructure.registry import RegistryService

registry = RegistryService()
registry.auto_register_common_lib_tools()

engine = ExecutionEngine(registry=registry)
context = ExecutionContext(agent_id="test", role="executor")

print("Executing Save Character Profile...")
handler_path = "common_lib.modules.image_processing.nodes.output.save_profile.SaveCharacterProfile.save_profile"
try:
    func = engine._load_handler(handler_path)
    print("Direct load: SUCCESS")
except Exception as e:
    print(f"Direct load: FAILED: {e}")
