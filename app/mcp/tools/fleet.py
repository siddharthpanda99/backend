import json
import asyncio
from ..mcp_dependencies import resolve_fleet_manager, resolve_model_container

def register_fleet_tools(mcp_server):
    
    @mcp_server.tool()
    def list_fleet_engines() -> str:
        """List all provisioned vLLM engines and their real-time health status."""
        try:
            fleet = resolve_fleet_manager()
            status = fleet.get_cached_status()
            return f"### Fleet Engines:\n```json\n{json.dumps(status, indent=2)}\n```"
        except Exception as e:
            return f"Fleet status error: {str(e)}"

    @mcp_server.tool()
    def sync_fleet() -> str:
        """Sync the engine registry with Docker state and prune ghost containers."""
        try:
            fleet = resolve_fleet_manager()
            fleet.sync_registry_with_docker()
            fleet.prune_ghost_containers()
            return "Fleet synchronization and pruning completed successfully."
        except Exception as e:
            return f"Fleet sync error: {str(e)}"

    @mcp_server.tool()
    def terminate_fleet_engine(engine_id: str) -> str:
        """Hard shutdown of an inference node."""
        try:
            fleet = resolve_fleet_manager()
            result = fleet.terminate_engine_node(engine_id)
            return f"Termination result: {json.dumps(result, indent=2)}"
        except Exception as e:
            return f"Termination error: {str(e)}"

    @mcp_server.tool()
    async def deploy_fleet_engine(model_path: str, engine_id: str = "main", gpu_memory_utilization: float = 0.85) -> str:
        """
        Deploy or reconfigure an inference engine node (vLLM container).
        model_path: Path to the model files in the registry.
        engine_id: Unique ID for the engine instance.
        gpu_memory_utilization: Fraction of GPU memory to reserve (0.0 to 1.0).
        """
        try:
            fleet = resolve_fleet_manager()
            container = resolve_model_container()
            # Trigger node deployment
            await asyncio.to_thread(fleet.deploy_engine_node, model_path=model_path, engine_id=engine_id, gpu_memory_utilization=gpu_memory_utilization, mirror_service=container.mirror_service)
            return f"Fleet engine '{engine_id}' deployment initiated for '{model_path}'."
        except Exception as e:
            return f"Fleet deployment error: {str(e)}"

    @mcp_server.tool()
    def get_fleet_engine_logs(engine_id: str, last_lines: int = 100) -> str:
        """Retrieve the recent execution logs for a fleet engine node."""
        try:
            import subprocess
            container_name = f"vllm-server-{engine_id}"
            result = subprocess.check_output(["docker", "logs", "--tail", str(last_lines), container_name], encoding="utf-8", stderr=subprocess.STDOUT)
            return f"### Logs for {engine_id}:\n```\n{result}\n```"
        except Exception as e:
            return f"Log retrieval error: {str(e)}"

    @mcp_server.tool()
    def list_provisioning_engines() -> str:
        """List available hardware engines available for provisioning (e.g., Docker nodes)."""
        try:
            fleet = resolve_fleet_manager()
            engines = fleet.discover_engines()
            return f"### Available Provisioning Engines:\n```json\n{json.dumps(engines, indent=2)}\n```"
        except Exception as e:
            return f"Engine discovery error: {str(e)}"
