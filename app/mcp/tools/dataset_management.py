"""MCP Tools — Dataset Management.

Provides dataset CRUD, import/export, and versioning via the MCP server.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def register_dataset_management_tools(mcp):
    """Register Dataset Management MCP tools."""

    @mcp.tool()
    def create_dataset(
        name: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        data: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create a new dataset with name, description, tags, and optional initial data.

        Args:
            name: Dataset name
            description: What this dataset contains
            tags: Tags for organization
            data: Initial data rows

        Returns:
            Dict with 'id', 'name', 'row_count', 'version'
        """
        from common_lib.modules.data_forge.dataset_nodes import create_dataset as _create
        return _create(name=name, description=description, tags=tags or [], data=data or [])

    @mcp.tool()
    def list_datasets(
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List all datasets with optional filtering.

        Args:
            query: Search by name/description
            tags: Filter by tags
            status: Filter by status (active, archived, deleted)
            limit: Max results

        Returns:
            Dict with 'datasets' list and 'total' count
        """
        from common_lib.modules.data_forge.dataset_nodes import list_datasets as _list
        return _list(query=query, tags=tags, status=status, limit=limit)

    @mcp.tool()
    def get_dataset(dataset_id: str) -> Dict[str, Any]:
        """Get a dataset by ID with all its data, schema, and metadata.

        Args:
            dataset_id: Dataset ID

        Returns:
            Full dataset with data rows, columns, version info
        """
        from common_lib.modules.data_forge.dataset_nodes import get_dataset as _get
        return _get(dataset_id)

    @mcp.tool()
    def import_dataset_data(
        content: str,
        format: str = "csv",
        name: Optional[str] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
        dataset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import data from raw content (CSV, JSON, JSONL, YAML, TSV) into a dataset.

        Auto-detects schema from content. If dataset_id is provided, appends to existing dataset.

        Args:
            content: Raw data content
            format: Format — csv, json, jsonl, yaml, tsv
            name: Dataset name (auto-generated if not provided)
            description: Dataset description
            tags: Tags
            dataset_id: If provided, imports into existing dataset

        Returns:
            Dict with 'id', 'name', 'row_count', 'columns', 'imported'
        """
        from common_lib.modules.data_forge.dataset_nodes import import_data as _import
        return _import(content=content, format=format, name=name, description=description, tags=tags or [], dataset_id=dataset_id)

    @mcp.tool()
    def export_dataset_data(
        dataset_id: str,
        format: str = "json",
        include_metadata: bool = False,
    ) -> Dict[str, Any]:
        """Export a dataset to CSV, JSON, JSONL, or YAML format.

        Args:
            dataset_id: Dataset ID
            format: Export format — csv, json, jsonl, yaml, tsv
            include_metadata: Include schema, tags, description in output

        Returns:
            Dict with 'content' (serialized string), 'format', 'row_count', 'size_bytes'
        """
        from common_lib.modules.data_forge.dataset_nodes import export_data as _export
        return _export(dataset_id, format=format, include_metadata=include_metadata)

    @mcp.tool()
    def update_dataset(
        dataset_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        data: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Update a dataset's metadata or replace its data rows.

        Replacing data auto-creates a new version.

        Args:
            dataset_id: Dataset ID
            name: New name
            description: New description
            tags: New tags
            data: Replace data rows (auto-versions)

        Returns:
            Dict with 'id', 'version', 'row_count'
        """
        from common_lib.modules.data_forge.dataset_nodes import update_dataset as _update
        return _update(dataset_id=dataset_id, name=name, description=description, tags=tags, data=data)

    @mcp.tool()
    def delete_dataset(dataset_id: str) -> Dict[str, Any]:
        """Soft-delete a dataset (marks as deleted, does not remove data).

        Args:
            dataset_id: Dataset ID to delete

        Returns:
            Dict with 'deleted' (bool)
        """
        from common_lib.modules.data_forge.dataset_nodes import delete_dataset as _delete
        return _delete(dataset_id)

    @mcp.tool()
    def list_dataset_versions(dataset_id: str) -> Dict[str, Any]:
        """List all versions of a dataset with timestamps and checksums.

        Args:
            dataset_id: Dataset ID

        Returns:
            Dict with 'versions' list and 'total' count
        """
        from common_lib.modules.data_forge.dataset_nodes import list_versions as _versions
        return _versions(dataset_id)

    @mcp.tool()
    def rollback_dataset(dataset_id: str, to_version: str) -> Dict[str, Any]:
        """Rollback a dataset to a previous version.

        Creates a new major version with the old data.

        Args:
            dataset_id: Dataset ID
            to_version: Version to rollback to

        Returns:
            Dict with 'id', 'version', 'row_count'
        """
        from common_lib.modules.data_forge.dataset_nodes import rollback_version as _rollback
        return _rollback(dataset_id, to_version)

    @mcp.tool()
    def dataset_stats() -> Dict[str, Any]:
        """Get dataset store statistics — total datasets, rows, versions.

        Returns:
            Dict with 'total_datasets', 'total_rows', 'total_versions'
        """
        from common_lib.modules.data_forge.dataset_nodes import dataset_stats as _stats
        return _stats()

    logger.info("Dataset Management MCP tools registered (10 tools)")
