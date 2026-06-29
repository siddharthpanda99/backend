"""Agentic OS — CRUD Routes for config management, sections, builders, and system composition.

Every functionality block has full CRUD support for storing a list of configs.
Clients can:
  - List schemas (what can be configured) grouped by category
  - List/default/create/update/delete/duplicate config instances
  - List sections and builders
  - Compose systems from selected configs
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from common_lib.modules.agentic_os import (
    get_config_registry, get_section_registry, get_builder_registry,
)
from common_lib.modules.data_storage.database.connection import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agentic-os", tags=["Agentic OS"])

_config_registry = get_config_registry()
_section_registry = get_section_registry()
_builder_registry = get_builder_registry()


def _inject_session(session: Session = Depends(get_session)) -> None:
    """FastAPI dependency that injects the DB session into the config registry."""
    _config_registry.set_session(session)


# ── Schemas ────────────────────────────────────────────────────────────

class ConfigCreateRequest(BaseModel):
    section_type: str = Field(description="Section type (extraction, embedding, rag, etc.)")
    name: str = Field(description="Config name")
    description: str = Field(default="", description="Config description")
    values: Dict[str, Any] = Field(description="Config field values")
    tags: List[str] = Field(default_factory=list, description="Tags for filtering")


class ConfigUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    values: Optional[Dict[str, Any]] = Field(default=None)
    tags: Optional[List[str]] = Field(default=None)


class ComposeSystemRequest(BaseModel):
    name: str = Field(description="System name")
    description: str = Field(default="", description="System description")
    sections: Dict[str, str] = Field(description="Map of section_type -> config_id for each section")
    builder_type: str = Field(default="agent_builder", description="Builder type to use for composition")


# ── Schema Endpoints ───────────────────────────────────────────────────

@router.get("/schemas")
async def list_schemas(_: None = Depends(_inject_session)):
    """List all config schemas grouped by category."""
    return {
        "schemas": [s.to_dict() for s in _config_registry.list_schemas()],
        "by_category": {
            cat: [s.to_dict() for s in schemas]
            for cat, schemas in _config_registry.get_schemas_by_category().items()
        },
    }


@router.get("/schemas/{section_type}")
async def get_schema(section_type: str, _: None = Depends(_inject_session)):
    """Get the schema for a specific section type."""
    schema = _config_registry.get_schema(section_type)
    if not schema:
        raise HTTPException(status_code=404, detail=f"No schema for section type: {section_type}")
    return schema.to_dict()


# ── Config Endpoints (Full CRUD) ───────────────────────────────────────

@router.get("/configs")
async def list_configs(_: None = Depends(_inject_session), section_type: Optional[str] = None):
    """List all config instances, optionally filtered by section type.

    Each section type has a list of usable configs: system defaults + user-created.
    """
    configs = _config_registry.list_configs(section_type)
    return {
        "configs": [c.to_dict() for c in configs],
        "total": len(configs),
        "section_type": section_type or "all",
    }


@router.get("/configs/{config_id}")
async def get_config(config_id: str, _: None = Depends(_inject_session)):
    """Get a specific config by ID."""
    cfg = _config_registry.get_config(config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Config not found: {config_id}")
    return cfg.to_dict()


@router.post("/configs")
async def create_config(payload: ConfigCreateRequest, _: None = Depends(_inject_session)):
    """Create a new user config for a section type."""
    errors = _config_registry.validate_config_values(payload.section_type, payload.values)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})
    cfg = _config_registry.create_config(
        section_type=payload.section_type,
        values=payload.values,
        name=payload.name,
        description=payload.description,
        tags=payload.tags,
    )
    return cfg.to_dict()


@router.put("/configs/{config_id}")
async def update_config(config_id: str, payload: ConfigUpdateRequest, _: None = Depends(_inject_session)):
    """Update an existing user config."""
    cfg = _config_registry.update_config(
        config_id=config_id,
        values=payload.values,
        name=payload.name,
        description=payload.description,
        tags=payload.tags,
    )
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found or is read-only (system)")
    return cfg.to_dict()


@router.delete("/configs/{config_id}")
async def delete_config(config_id: str, _: None = Depends(_inject_session)):
    """Delete a user config. System configs cannot be deleted."""
    success = _config_registry.delete_config(config_id)
    if not success:
        raise HTTPException(status_code=404, detail="Config not found or is read-only (system)")
    return {"success": True, "id": config_id}


@router.post("/configs/{config_id}/duplicate")
async def duplicate_config(config_id: str, name: Optional[str] = None, _: None = Depends(_inject_session)):
    """Clone a config (system or user) as a new user-created config."""
    cfg = _config_registry.duplicate_config(config_id, new_name=name or "")
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Config not found: {config_id}")
    return cfg.to_dict()


# ── Section Endpoints ──────────────────────────────────────────────────

@router.get("/sections")
async def list_sections():
    """List all section definitions grouped by category."""
    return {
        "sections": [s.to_dict() for s in _section_registry.list_all()],
        "by_category": {
            cat: [s.to_dict() for s in sections]
            for cat, sections in _section_registry.list_by_category().items()
        },
    }


@router.get("/sections/{section_type}")
async def get_section(section_type: str):
    """Get a section definition by type."""
    section = _section_registry.get_by_str(section_type)
    if not section:
        raise HTTPException(status_code=404, detail=f"Section not found: {section_type}")
    return section.to_dict()


# ── Builder Endpoints ──────────────────────────────────────────────────

@router.get("/builders")
async def list_builders():
    """List all builder definitions grouped by category."""
    return {
        "builders": [b.to_dict() for b in _builder_registry.list_all()],
        "by_category": {
            cat: [b.to_dict() for b in builders]
            for cat, builders in _builder_registry.list_by_category().items()
        },
    }


@router.get("/builders/{builder_type}")
async def get_builder(builder_type: str):
    """Get a builder definition by type."""
    builder = _builder_registry.get_by_str(builder_type)
    if not builder:
        raise HTTPException(status_code=404, detail=f"Builder not found: {builder_type}")
    return builder.to_dict()


# ── System Composition Endpoints ───────────────────────────────────────

@router.post("/compose")
async def compose_system(payload: ComposeSystemRequest):
    """Compose a system from selected config sections.

    Takes a map of section_type -> config_id and produces a fully composed
    system configuration that can be deployed as an agentic system.

    The composed output includes:
    - Merged config values for each section
    - Tool bindings for each configured section
    - Builder blueprint for deployment
    """
    builder = _builder_registry.get_by_str(payload.builder_type)
    if not builder:
        raise HTTPException(status_code=404, detail=f"Builder not found: {payload.builder_type}")

    sections_config = {}
    errors = []

    for section_type, config_id in payload.sections.items():
        # Get the config instance
        cfg = _config_registry.get_config(config_id)
        if not cfg:
            errors.append(f"Config '{config_id}' not found for section '{section_type}'")
            continue

        # Validate section type
        schema = _config_registry.get_schema(section_type)
        if not schema:
            errors.append(f"No schema for section type: {section_type}")
            continue

        # Validate config values against schema
        validation_errors = schema.validate(cfg.values)
        if validation_errors:
            errors.append(f"Section '{section_type}': {validation_errors}")

        sections_config[section_type] = {
            "config_id": config_id,
            "config_name": cfg.name,
            "values": cfg.values,
            "schema": schema.to_dict(),
            "valid": len(validation_errors) == 0,
        }

    if errors:
        return {
            "success": False,
            "system": None,
            "errors": errors,
            "sections": sections_config,
        }

    # Build the composed system blueprint
    composed = {
        "name": payload.name,
        "description": payload.description,
        "builder_type": payload.builder_type,
        "builder_name": builder.name,
        "sections": sections_config,
        "section_count": len(sections_config),
        "mcp_tool_names": [
            f"agentic_os_{section_type}_{cfg.get('config_name', 'default')}".lower().replace(" ", "_")
            for section_type, cfg in sections_config.items()
        ],
    }

    return {
        "success": True,
        "system": composed,
        "errors": [],
    }
