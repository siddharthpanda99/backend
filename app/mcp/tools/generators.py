import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from ..mcp_dependencies import resolve_db_session

logger = logging.getLogger("mcp.tools.generators")


def register_generator_tools(mcp: FastMCP):
    """Register all generator engine tools — data-driven content generation."""
    from common_lib.modules.external_platforms.writing_studio.generator_engine import (
        GeneratorEngine,
        get_generator_engine,
    )

    @mcp.tool()
    async def generator_list(
        entity_type: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all available generator definitions.

        Args:
            entity_type: Optional filter by entity type (e.g., 'name', 'place', 'character')
            category: Optional filter by category (e.g., 'character', 'worldbuilding', 'writing')
        """
        session = resolve_db_session()
        engine = get_generator_engine(session=session)
        gens = engine.list_generators(
            entity_type=entity_type, category=category
        )
        return [
            {
                "id": g.id,
                "name": g.name,
                "entity_type": g.entity_type,
                "description": g.description,
                "icon": g.icon,
                "category": g.category,
                "is_builtin": g.is_builtin,
                "version": g.version,
                "source": g.source,
                "tags": g.tags,
                "entity_types": g.entity_types,
                "parameter_count": len(g.parameters),
                "output_field_count": len(g.output_fields),
            }
            for g in gens
        ]

    @mcp.tool()
    async def generator_get(gen_id: str) -> Dict[str, Any]:
        """Get full details of a specific generator definition.

        Args:
            gen_id: Generator ID (e.g., 'gen_name', 'gen_character', or custom ID)
        """
        session = resolve_db_session()
        engine = get_generator_engine(session=session)
        gen = engine.get_generator(gen_id)
        if not gen:
            return {"status": "error", "message": f"Generator '{gen_id}' not found"}
        return {
            "id": gen.id,
            "name": gen.name,
            "entity_type": gen.entity_type,
            "description": gen.description,
            "icon": gen.icon,
            "prompt_template": gen.prompt_template,
            "parameters": gen.parameters,
            "output_fields": gen.output_fields,
            "entity_types": gen.entity_types,
            "tags": gen.tags,
            "category": gen.category,
            "is_builtin": gen.is_builtin,
            "version": gen.version,
            "source": gen.source,
        }

    @mcp.tool()
    async def generator_create(
        name: str,
        entity_type: str,
        prompt_template: str,
        description: str = "",
        icon: str = "🔧",
        parameters_schema: Optional[str] = None,
        output_fields_schema: Optional[str] = None,
        entity_types: Optional[str] = None,
        tags: Optional[str] = None,
        category: str = "general",
    ) -> Dict[str, Any]:
        """Create a new custom generator definition.

        This allows users to define any entity type with a custom system prompt
        entirely from the UI. Pass JSON arrays as strings for parameters and fields.

        Args:
            name: Name of the generator
            entity_type: What this generates (e.g., 'character', 'place', 'plot', 'custom')
            prompt_template: LLM system prompt template using {{variable}} syntax
            description: Optional description of what this generator creates
            icon: Emoji icon for the generator
            parameters_schema: JSON string of parameter definitions array
            output_fields_schema: JSON string of output field definitions array
            entity_types: Comma-separated list of entity types (supports multi-entity)
            tags: Comma-separated list of tags
            category: Generator category (e.g., 'character', 'worldbuilding', 'writing')
        """
        session = resolve_db_session()
        engine = get_generator_engine(session=session)

        try:
            params = []
            if parameters_schema:
                params = __import__("json").loads(parameters_schema)

            output_fields = []
            if output_fields_schema:
                output_fields = __import__("json").loads(output_fields_schema)

            entity_type_list = []
            if entity_types:
                entity_type_list = [et.strip() for et in entity_types.split(",")]

            tag_list = []
            if tags:
                tag_list = [t.strip() for t in tags.split(",")]

            gen = engine.create_generator(
                name=name,
                entity_type=entity_type,
                prompt_template=prompt_template,
                description=description,
                icon=icon,
                parameters_schema=params,
                output_fields_schema=output_fields,
                entity_types=entity_type_list or [entity_type],
                tags=tag_list,
                category=category,
                source="user_created",
            )
            return {"status": "success", "id": gen.id, "name": gen.name}
        except Exception as e:
            logger.error(f"Failed to create generator: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def generator_update(
        gen_id: str,
        name: Optional[str] = None,
        prompt_template: Optional[str] = None,
        description: Optional[str] = None,
        icon: Optional[str] = None,
        parameters_schema: Optional[str] = None,
        output_fields_schema: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing generator definition.

        Args:
            gen_id: Generator ID to update
            name: New name
            prompt_template: New prompt template
            description: New description
            icon: New icon
            parameters_schema: JSON string of parameter definitions
            output_fields_schema: JSON string of output field definitions
        """
        session = resolve_db_session()
        engine = get_generator_engine(session=session)
        updates = {}
        if name is not None:
            updates["name"] = name
        if prompt_template is not None:
            updates["prompt_template"] = prompt_template
        if description is not None:
            updates["description"] = description
        if icon is not None:
            updates["icon"] = icon
        if parameters_schema is not None:
            updates["parameters_schema"] = __import__("json").loads(parameters_schema)
        if output_fields_schema is not None:
            updates["output_fields_schema"] = __import__("json").loads(output_fields_schema)

        result = engine.update_generator(gen_id, updates)
        if not result:
            return {"status": "error", "message": f"Generator '{gen_id}' not found or is built-in"}
        return {"status": "success", "id": result.id, "name": result.name}

    @mcp.tool()
    async def generator_delete(gen_id: str) -> Dict[str, Any]:
        """Delete a custom generator definition (builtins cannot be deleted).

        Args:
            gen_id: Generator ID to delete
        """
        session = resolve_db_session()
        engine = get_generator_engine(session=session)
        success = engine.delete_generator(gen_id)
        if not success:
            return {
                "status": "error",
                "message": f"Generator '{gen_id}' not found or is built-in (builtins cannot be deleted)",
            }
        return {"status": "success", "message": f"Generator '{gen_id}' deleted"}

    @mcp.tool()
    async def generator_execute(
        gen_id: str,
        params_json: str,
    ) -> Dict[str, Any]:
        """Execute a generator with the given parameters.

        Args:
            gen_id: Generator ID to execute
            params_json: JSON string of parameter values (e.g., '{\"count\": 5, \"genre\": \"fantasy\"}')
        """
        session = resolve_db_session()
        engine = get_generator_engine(session=session)
        try:
            params = __import__("json").loads(params_json)
        except Exception as e:
            return {"status": "error", "message": f"Invalid JSON params: {e}"}

        result = await engine.execute(gen_id, params)
        return result.to_json()

    @mcp.tool()
    async def generator_list_executions(
        generator_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List generator execution history.

        Args:
            generator_id: Optional filter by generator ID
            limit: Maximum number of results (default 20)
        """
        session = resolve_db_session()
        engine = get_generator_engine(session=session)
        records = engine.list_executions(generator_id=generator_id, limit=limit)
        return [
            {
                "id": r.id,
                "generator_id": r.generator_id,
                "generator_name": r.generator_name,
                "entity_type": r.entity_type,
                "success": r.success,
                "items_count": r.items_count,
                "execution_time_ms": r.execution_time_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]

    @mcp.tool()
    async def generator_seed_defaults() -> Dict[str, Any]:
        """Seed built-in generator definitions from JSON data into the database.

        Only seeds generators that don't already exist.
        """
        session = resolve_db_session()
        engine = get_generator_engine(session=session)
        count = engine.seed_defaults()
        return {
            "status": "success",
            "seeded_count": count,
            "message": f"Seeded {count} built-in generator definitions",
        }

    @mcp.tool()
    async def generator_generate_from_description(description: str) -> Dict[str, Any]:
        """Use AI to design a generator from a natural language description.

        The LLM will create a custom generator with entity type, prompt template,
        parameters, and output fields — all saved to the database.

        Args:
            description: Natural language description (e.g., 'a noble family name generator for my fantasy world')
        """
        session = resolve_db_session()
        engine = get_generator_engine(session=session)
        gen = await engine.generate_from_description(description)
        if not gen:
            return {
                "status": "error",
                "message": "Failed to generate generator. LLM may not be available.",
            }
        return {
            "status": "success",
            "id": gen.id,
            "name": gen.name,
            "entity_type": gen.entity_type,
        }
