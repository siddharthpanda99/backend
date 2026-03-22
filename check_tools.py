from common_lib.modules.core_infrastructure.registry import RegistryService
import logging

logging.basicConfig(level=logging.INFO)
registry = RegistryService()
registry.auto_register_common_lib_tools()

print("REGISTERED TOOLS:")
for tool_id in sorted(registry.tools.keys()):
    print(f" - {tool_id}")
