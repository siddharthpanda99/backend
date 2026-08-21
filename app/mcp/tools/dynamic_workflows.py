"""
MCP Tool: Dynamic Workflow Execution

Exposes workflow execution to AI agents (OpenCode, Claude, etc.) via MCP.
Agents can list workflows, list configs, validate merges, and run workflows.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("mcp.tools.dynamic_workflows")


def register_dynamic_workflow_tools(mcp):
    """Register dynamic workflow tools with the MCP server."""

    @mcp.tool()
    async def list_vision_workflows() -> List[Dict[str, Any]]:
        """
        List all available YAML workflows for image generation, face editing,
        segmentation, depth estimation, pose estimation, and other vision tasks.

        Returns a list of workflow summaries with id, name, category, node count.
        Use the workflow_id with run_vision_workflow to execute.
        """
        from common_lib.modules.workflows.dynamic_runner import get_dynamic_runner
        runner = get_dynamic_runner()
        workflows = runner.list_workflows()
        return [
            {
                "id": w.get("id"),
                "name": w.get("name"),
                "description": w.get("description", ""),
                "category": w.get("category", ""),
                "node_count": w.get("node_count", 0),
            }
            for w in workflows
        ]

    @mcp.tool()
    async def list_workflow_configs(workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available data-config YAML files for workflows.
        Each config is a named parameter set (prompt, steps, CFG, resolution, etc.)

        Args:
            workflow_id: Optional filter — only show configs for this workflow_id.

        Returns config summaries with id, name, workflow_id, file path, and parameter keys.
        """
        from common_lib.modules.workflows.dynamic_runner import get_dynamic_runner
        runner = get_dynamic_runner()
        return runner.list_configs(workflow_id=workflow_id)

    @mcp.tool()
    async def validate_workflow_merge(
        workflow: str,
        config: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Dry-run: merge a workflow YAML with a data-config and show the resolved
        graph without executing. Useful for debugging parameter resolution.

        Args:
            workflow: Workflow YAML path, dict, or workflow_id from registry.
            config: Data-config YAML path or dict (optional).
            overrides: Runtime parameter overrides (optional).

        Returns the merged workflow with resolved node properties and parameters.
        """
        from common_lib.modules.workflows.dynamic_runner import get_dynamic_runner
        runner = get_dynamic_runner()

        wf = runner.load_workflow(workflow)
        if not wf:
            return {"error": f"Workflow not found: {workflow}"}

        cfg = runner.load_config(config) if config else {}
        merged = runner.merge(wf, cfg, overrides)

        return {
            "workflow_id": merged.get("id"),
            "node_count": len(merged.get("nodes", [])),
            "edge_count": len(merged.get("edges", [])),
            "resolved_params": merged.get("metadata", {}).get("resolved_params", {}),
            "nodes": [
                {
                    "id": n.get("id"),
                    "type": n.get("type"),
                    "properties": n.get("properties") or n.get("inputs", {}),
                }
                for n in merged.get("nodes", [])
            ],
        }

    @mcp.tool()
    async def run_vision_workflow(
        workflow: str,
        config: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a vision workflow with a data-config. This is the primary tool
        for running image generation, face editing, segmentation, depth estimation,
        pose estimation, and other visual AI pipelines.

        Args:
            workflow: Workflow YAML path, dict, or workflow_id (e.g. "sd15", "depth_anything_v2",
                      "face_swap_codeformer", "dwpose_estimation", "yolo_world_detect").
            config: Data-config YAML path or dict with data_config block containing
                    prompt, steps, cfg, width, height, etc.
            overrides: Runtime parameter overrides applied last (highest priority).

        Returns:
            status: "completed" or "failed"
            workflow_id: The workflow that was executed
            params: Resolved parameters used
            outputs: Output data (file paths, etc.)
            duration_ms: Execution time in milliseconds
            error: Error message if failed

        Examples:
            run_vision_workflow("sd15", "data-config/sd15/cyberpunk_streetscape.yaml")
            run_vision_workflow("depth_anything_v2", overrides={"image_path": "photo.png"})
            run_vision_workflow("face_swap_codeformer", overrides={
                "source_image": "face.png",
                "target_image": "portrait.png"
            })
        """
        from common_lib.modules.workflows.dynamic_runner import get_dynamic_runner
        runner = get_dynamic_runner()

        result = await runner.run(
            workflow=workflow,
            config=config,
            overrides=overrides,
        )
        return result

    @mcp.tool()
    async def run_workflow_sse(
        workflow: str,
        config: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a workflow and return all SSE events as a list.
        Same as run_vision_workflow but returns the full event stream
        for debugging and detailed progress tracking.

        Args:
            workflow: Workflow YAML path or workflow_id.
            config: Data-config YAML path or dict.
            overrides: Runtime parameter overrides.

        Returns:
            events: List of all SSE events from the execution
            final_status: "completed" or "failed"
        """
        from common_lib.modules.workflows.dynamic_runner import get_dynamic_runner
        runner = get_dynamic_runner()

        events = []
        async for event in runner.run_stream(
            workflow=workflow,
            config=config,
            overrides=overrides,
        ):
            events.append(event)

        final_status = "completed"
        for event in reversed(events):
            if isinstance(event, dict):
                et = event.get("event_type", "")
                if "failed" in et:
                    final_status = "failed"
                    break
                if "completed" in et:
                    final_status = "completed"
                    break

        return {
            "events": events,
            "event_count": len(events),
            "final_status": final_status,
        }

    logger.info("Dynamic workflow MCP tools registered")
