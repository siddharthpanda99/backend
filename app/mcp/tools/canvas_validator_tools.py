"""MCP Tools — Canvas Validation.

Provides workflow YAML validation: cycle detection, missing nodes,
type mismatches, dangling references, and orphan nodes.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_validator = None


def _get_validator():
    global _validator
    if _validator is None:
        from common_lib.modules.orchestration.workflow.canvas_validator import CanvasValidator
        _validator = CanvasValidator()
    return _validator


def register_canvas_validation_tools(mcp):
    """Register Canvas Validation MCP tools."""

    @mcp.tool()
    def validate_workflow(workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a workflow YAML dict for correctness.

        Checks for: cycles, missing nodes, type mismatches, dangling references,
        orphan nodes, self-loops, unresolved variables, and unknown node types.

        Args:
            workflow_data: Workflow as a dict with 'nodes', 'edges', 'name' keys

        Returns:
            Dict with 'valid' (bool), 'issues' (list of {severity, category, message}),
            'node_count', 'edge_count', 'summary'
        """
        v = _get_validator()
        result = v.validate(workflow_data)
        return {
            "valid": result.valid,
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                    "node_id": i.node_id,
                    "edge_index": i.edge_index,
                }
                for i in result.issues
            ],
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "node_types_found": result.node_types_found,
            "summary": result.summary,
        }

    @mcp.tool()
    def validate_workflow_yaml(yaml_string: str) -> Dict[str, Any]:
        """Validate a workflow YAML string for correctness.

        Parses YAML and runs all canvas validation checks.

        Args:
            yaml_string: Raw YAML content of the workflow

        Returns:
            Dict with 'valid', 'issues', 'node_count', 'edge_count', 'summary'
        """
        v = _get_validator()
        result = v.validate_yaml_string(yaml_string)
        return {
            "valid": result.valid,
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                    "node_id": i.node_id,
                }
                for i in result.issues
            ],
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "summary": result.summary,
        }

    @mcp.tool()
    def validate_workflow_file(file_path: str) -> Dict[str, Any]:
        """Validate a workflow YAML file from disk.

        Args:
            file_path: Path to the workflow YAML file

        Returns:
            Dict with 'valid', 'issues', 'node_count', 'edge_count', 'summary'
        """
        v = _get_validator()
        result = v.validate_file(file_path)
        return {
            "valid": result.valid,
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                    "node_id": i.node_id,
                }
                for i in result.issues
            ],
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "summary": result.summary,
        }

    @mcp.tool()
    def node_type_registry_stats() -> Dict[str, Any]:
        """Get statistics about the node type definitions registry.

        Returns total types loaded from templates/node_definitions/ (603+ types),
        category breakdown, and registry health.

        Returns:
            Dict with 'total_types', 'categories', 'category_counts'
        """
        v = _get_validator()
        return v.get_registry_stats()

    @mcp.tool()
    def list_available_node_types(category_filter: Optional[str] = None) -> List[str]:
        """List all available node type definitions usable in workflows.

        Args:
            category_filter: Filter by category prefix (e.g. 'vision', 'audio', 'data')

        Returns:
            List of node type IDs (e.g. 'vision.generate_image', 'audio.tts')
        """
        v = _get_validator()
        types = v._registry.list_types()
        if category_filter:
            types = [t for t in types if t.startswith(category_filter)]
        return types

    logger.info("Canvas Validation MCP tools registered (5 tools)")
