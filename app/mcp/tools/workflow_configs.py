import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP
from app.core.common_lib_integration import common_memory, sync_entity_to_fs

logger = logging.getLogger("mcp.tools.workflow_configs")


def register_workflow_config_tools(mcp: FastMCP):
    """Register MCP tools for workflow config CRUD, comments, and image gallery."""

    @mcp.tool()
    async def list_workflow_configs(
        workflow_id: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all workflow configuration presets.

        Args:
            workflow_id: Optional filter by parent workflow ID.
            category: Optional filter by category.
            status: Optional filter by status (ACTIVE, DRAFT, ARCHIVED).
        """
        if workflow_id:
            configs = common_memory.get_workflow_configs_by_workflow_id(workflow_id)
        else:
            configs = common_memory.list_workflow_config_definitions()

        if category:
            configs = [c for c in configs if c.get("category") == category]
        if status:
            configs = [c for c in configs if c.get("status") == status]

        return configs

    @mcp.tool()
    async def get_workflow_config(config_id: str) -> Dict[str, Any]:
        """Get a single workflow config by ID including its definition, field schema, and image gallery."""
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            return {"error": f"Config '{config_id}' not found"}
        return config

    @mcp.tool()
    async def create_workflow_config(
        name: str,
        workflow_id: Optional[str] = None,
        description: str = "",
        category: str = "General",
        tags: List[str] = None,
        definition: Dict[str, Any] = None,
        field_schema: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Create a new workflow configuration preset.

        Args:
            name: Display name for the config.
            workflow_id: Parent workflow ID this config belongs to.
            description: Human-readable description.
            category: Category for grouping (e.g., General, Art, Portrait).
            tags: List of tags for search.
            definition: Node field values {node_id: {field: value}}.
            field_schema: Field metadata {node_id: {field: {type, label, default, ...}}}.
        """
        import uuid

        config_id = name.lower().replace(" ", "_") or str(uuid.uuid4())[:8]
        existing = common_memory.get_workflow_config_definition(config_id)
        if existing:
            config_id = f"{config_id}_{uuid.uuid4().hex[:6]}"

        success = common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=name,
            definition=definition or {},
            version="1.0.0",
            description=description,
            category=category,
            tags=tags or [],
            status="ACTIVE",
            workflow_id=workflow_id,
            field_schema=field_schema or {},
            image_gallery=[],
            metadata_json={},
            artifacts={"import_source": "mcp"},
        )

        if success:
            sync_entity_to_fs("workflow_config", config_id)
            return common_memory.get_workflow_config_definition(config_id)
        return {"error": "Failed to create config"}

    @mcp.tool()
    async def update_workflow_config(
        config_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        definition: Optional[Dict[str, Any]] = None,
        field_schema: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Update an existing workflow config. Only provided fields are updated."""
        existing = common_memory.get_workflow_config_definition(config_id)
        if not existing:
            return {"error": f"Config '{config_id}' not found"}

        if name is not None:
            existing["name"] = name
        if description is not None:
            existing["description"] = description
        if category is not None:
            existing["category"] = category
        if status is not None:
            existing["status"] = status
        if definition is not None:
            existing["definition"] = definition
        if field_schema is not None:
            existing["field_schema"] = field_schema
        if tags is not None:
            existing["tags"] = tags

        success = common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=existing.get("name"),
            definition=existing.get("definition", {}),
            version=existing.get("version", "1.0.0"),
            description=existing.get("description", ""),
            category=existing.get("category", "General"),
            tags=existing.get("tags", []),
            status=existing.get("status", "ACTIVE"),
            workflow_id=existing.get("workflow_id"),
            field_schema=existing.get("field_schema", {}),
            image_gallery=existing.get("image_gallery", []),
            metadata_json=existing.get("metadata_json", {}),
            artifacts=existing.get("artifacts", {}),
        )

        if success:
            sync_entity_to_fs("workflow_config", config_id)
            return common_memory.get_workflow_config_definition(config_id)
        return {"error": "Failed to update config"}

    @mcp.tool()
    async def delete_workflow_config(config_id: str) -> Dict[str, Any]:
        """Delete a workflow config and all its associated data."""
        existing = common_memory.get_workflow_config_definition(config_id)
        if not existing:
            return {"error": f"Config '{config_id}' not found"}

        success = common_memory.delete_workflow_config_definition(config_id)
        if success:
            return {"status": "deleted", "config_id": config_id}
        return {"error": "Failed to delete config"}

    @mcp.tool()
    async def add_config_comment(
        config_id: str,
        content: str,
        author_name: str = "MCP User",
        parent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a comment to a workflow config. Use parent_id to reply to an existing comment."""
        import uuid
        from datetime import datetime

        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            return {"error": f"Config '{config_id}' not found"}

        comment = {
            "id": str(uuid.uuid4()),
            "config_id": config_id,
            "parent_id": parent_id,
            "author_id": "mcp",
            "author_name": author_name,
            "content": content,
            "reactions": {},
            "is_resolved": False,
            "is_deleted": False,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        metadata = config.get("metadata_json", {})
        comments = metadata.get("comments", [])
        comments.append(comment)
        metadata["comments"] = comments

        common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=config.get("name"),
            definition=config.get("definition", {}),
            version=config.get("version", "1.0.0"),
            description=config.get("description", ""),
            category=config.get("category", "General"),
            tags=config.get("tags", []),
            status=config.get("status", "ACTIVE"),
            workflow_id=config.get("workflow_id"),
            field_schema=config.get("field_schema", {}),
            image_gallery=config.get("image_gallery", []),
            metadata_json=metadata,
            artifacts=config.get("artifacts", {}),
        )

        return comment

    @mcp.tool()
    async def get_config_comments(config_id: str) -> List[Dict[str, Any]]:
        """Get all non-deleted comments for a workflow config."""
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            return [{"error": f"Config '{config_id}' not found"}]

        comments = config.get("metadata_json", {}).get("comments", [])
        return [c for c in comments if not c.get("is_deleted", False)]

    @mcp.tool()
    async def add_config_image(
        config_id: str,
        url: str,
        prompt_used: Optional[str] = None,
        seed: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        generation_params: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Add a generated image to a config's gallery."""
        import uuid
        from datetime import datetime

        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            return {"error": f"Config '{config_id}' not found"}

        image = {
            "id": str(uuid.uuid4()),
            "url": url,
            "thumbnail_url": None,
            "width": width,
            "height": height,
            "file_size": None,
            "seed": seed,
            "prompt_used": prompt_used,
            "negative_prompt_used": None,
            "generation_params": generation_params or {},
            "likes": 0,
            "is_featured": False,
            "created_at": datetime.utcnow().isoformat(),
        }

        gallery = config.get("image_gallery", [])
        gallery.append(image)

        common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=config.get("name"),
            definition=config.get("definition", {}),
            version=config.get("version", "1.0.0"),
            description=config.get("description", ""),
            category=config.get("category", "General"),
            tags=config.get("tags", []),
            status=config.get("status", "ACTIVE"),
            workflow_id=config.get("workflow_id"),
            field_schema=config.get("field_schema", {}),
            image_gallery=gallery,
            metadata_json=config.get("metadata_json", {}),
            artifacts=config.get("artifacts", {}),
        )

        return image

    @mcp.tool()
    async def get_config_images(config_id: str) -> List[Dict[str, Any]]:
        """Get all images in a config's gallery."""
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            return [{"error": f"Config '{config_id}' not found"}]
        return config.get("image_gallery", [])

    @mcp.tool()
    async def get_config_stats() -> Dict[str, Any]:
        """Get workflow config statistics: total count, categories, statuses."""
        configs = common_memory.list_workflow_config_definitions()
        categories = {}
        statuses = {}
        workflow_counts = {}

        for c in configs:
            cat = c.get("category", "General")
            categories[cat] = categories.get(cat, 0) + 1
            status = c.get("status", "ACTIVE")
            statuses[status] = statuses.get(status, 0) + 1
            wf_id = c.get("workflow_id")
            if wf_id:
                workflow_counts[wf_id] = workflow_counts.get(wf_id, 0) + 1

        return {
            "total": len(configs),
            "categories": categories,
            "statuses": statuses,
            "configs_per_workflow": workflow_counts,
        }
