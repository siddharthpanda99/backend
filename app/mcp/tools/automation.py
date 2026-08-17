import json
from typing import Optional
from app.core.common_lib_integration import common_memory
from ..mcp_dependencies import resolve_system_service

def register_automation_tools(mcp_server):
    
    @mcp_server.tool()
    def list_system_services() -> str:
        """List all infrastructure services (vLLM, PostgreSQL, Redis, etc.) and their status."""
        try:
            service = resolve_system_service()
            services = service.get_services()
            if not services:
                return "No system services found."
                
            res = "### System Services Status:\n"
            for s in services:
                res += f"- **{s['name']}** (`{s['id']}`): {s['status'].upper()}\n"
            return res
        except Exception as e:
            return f"Service listing error: {str(e)}"

    @mcp_server.tool()
    def toggle_system_service(service_id: str, action: str) -> str:
        """
        Start or stop a system service.
        service_id: The ID of the service (e.g., 'vllm', 'postgres').
        action: 'up' to start, 'down' to stop.
        """
        if action not in ["up", "down"]:
            return "Error: Action must be 'up' or 'down'."
            
        try:
            service = resolve_system_service()
            success = service.toggle_service(service_id, action)
            if success:
                return f"Service '{service_id}' successfully toggled to {action}."
            else:
                return f"Failed to toggle service '{service_id}' to {action}."
        except Exception as e:
            return f"Service toggle error: {str(e)}"

    @mcp_server.tool()
    def get_system_telemetry() -> str:
        """Retrieve host-level hardware telemetry (VRAM, CPU, etc.)."""
        try:
            from app.modules.agents.runtime.core import get_system_vram_gb
            import os
            vram = get_system_vram_gb()
            return f"### System Telemetry:\n- Total VRAM: {vram:.2f} GB\n- Host OS: {os.name}"
        except Exception as e:
            return f"Telemetry error: {str(e)}"

    @mcp_server.tool()
    def list_macros(workspace_id: Optional[str] = None) -> str:
        """List all automation macros."""
        try:
            from common_lib.modules.file_system.macro_service import get_macros
            macros = get_macros(workspace_id=workspace_id)
            if not macros:
                return "No macros found."
                
            res = "### Automation Macros:\n"
            for m in macros:
                res += f"- **{m['name']}** (`{m['id']}`): {m.get('description', 'No description')}\n"
            return res
        except Exception as e:
            return f"Macro list error: {str(e)}"

    @mcp_server.tool()
    def execute_macro(macro_id: str, trigger_type: str = "manual") -> str:
        """Execute a specific automation macro."""
        try:
            from common_lib.modules.file_system.macro_service import execute_macro as run_macro
            result = run_macro(macro_id=macro_id, trigger_type=trigger_type)
            if "error" in result:
                return f"Macro execution failed: {result['error']}"
            return f"Macro '{macro_id}' execution started. ID: {result.get('execution_id')}, Status: {result.get('status')}"
        except Exception as e:
            return f"Macro execution error: {str(e)}"

    @mcp_server.tool()
    def list_platform_commands() -> str:
        """List all registered slash commands (e.g., /search, /analyze)."""
        try:
            commands = common_memory.list_command_definitions()
            if not commands:
                return "No slash commands registered."
                
            res = "### Platform Commands:\n"
            for c in commands:
                trigger = c.get("trigger") or f"/{c['id']}"
                res += f"- **{trigger}**: {c['description']}\n"
            return res
        except Exception as e:
            return f"Command list error: {str(e)}"
