"""
PM Component Routes — Issue/project components CRUD.

RBAC permissions: component.read, component.create, component.update, component.delete
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from pydantic import BaseModel

from app.modules.auth.dependencies import require_permission

router = APIRouter(prefix="/components", tags=["project_management", "components"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class ComponentCreate(BaseModel):
    name: str
    description: str = ""


class ComponentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.get("")
def list_components(
    project_id: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("component.read", "*", "component"),
):
    """List all components for a project."""
    from common_lib.modules.project_management.components.service import ComponentService
    svc = ComponentService(session)
    components = svc.list_components(project_id=project_id)
    return {"items": [c.model_dump() for c in components], "total": len(components)}


@router.post("", status_code=201)
def create_component(
    data: ComponentCreate,
    project_id: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("component.create", "*", "component"),
):
    """Create a new component."""
    from common_lib.modules.project_management.components.service import ComponentService
    svc = ComponentService(session)
    comp = svc.create_component(name=data.name, description=data.description, project_id=project_id)
    return comp.model_dump()


@router.put("/{component_id}")
def update_component(
    component_id: str,
    data: ComponentUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("component.update", "*", "component"),
):
    """Update a component."""
    from common_lib.modules.project_management.components.service import ComponentService
    svc = ComponentService(session)
    comp = svc.update_component(component_id, data.model_dump(exclude_unset=True))
    if not comp:
        raise HTTPException(status_code=404, detail="Component not found")
    return comp.model_dump()


@router.delete("/{component_id}", status_code=204)
def delete_component(
    component_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("component.delete", "*", "component"),
):
    """Delete a component."""
    from common_lib.modules.project_management.components.service import ComponentService
    svc = ComponentService(session)
    if not svc.delete_component(component_id):
        raise HTTPException(status_code=404, detail="Component not found")
    return None
