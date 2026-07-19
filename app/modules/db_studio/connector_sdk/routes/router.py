"""Connector SDK API routes. Thin wrapper — all logic in common_lib."""

from fastapi import APIRouter, HTTPException, Query
from common_lib.modules.db_studio.connector_sdk import (
    ConnectorSDKService,
    ConnectorCreate,
    ConnectorUpdate,
    ConnectorOut,
    DriverCreate,
    DriverOut,
    PluginRegister,
    PluginOut,
    CapabilityCreate,
    CapabilityOut,
    CertificationCreate,
    CertificationOut,
    EngineCatalogOut,
)

router = APIRouter(prefix="", tags=["Connector SDK"])
svc = ConnectorSDKService()


# ── Engine Catalog (DB-backed source for the DB Configurator gallery) ──


@router.get("/engine-catalog", response_model=list[EngineCatalogOut])
def list_engine_catalog(category: str = None, enabled_only: bool = True):
    return svc.list_engine_catalog(category, enabled_only)


@router.post("/engine-catalog/seed")
def seed_engine_catalog(force: bool = False):
    return {"seeded": svc.seed_engine_catalog(force)}


@router.post("/connectors", response_model=ConnectorOut)
def register_connector(req: ConnectorCreate):
    return svc.register_connector(req)


@router.get("/connectors", response_model=list[ConnectorOut])
def list_connectors(
    connector_type: str = None,
    is_enabled: bool = None,
    offset: int = Query(0),
    limit: int = Query(50),
):
    return svc.list_connectors(connector_type, is_enabled, offset, limit)


@router.get("/connectors/{connector_id}", response_model=ConnectorOut)
def get_connector(connector_id: str):
    c = svc.get_connector(connector_id)
    if not c:
        raise HTTPException(404)
    return c


@router.put("/connectors/{connector_id}", response_model=ConnectorOut)
def update_connector(connector_id: str, req: ConnectorUpdate):
    c = svc.update_connector(connector_id, req)
    if not c:
        raise HTTPException(404)
    return c


@router.delete("/connectors/{connector_id}")
def delete_connector(connector_id: str):
    if not svc.delete_connector(connector_id):
        raise HTTPException(404)
    return {"ok": True}


@router.post("/drivers", response_model=DriverOut)
def register_driver(req: DriverCreate):
    return svc.register_driver(req)


@router.get("/drivers", response_model=list[DriverOut])
def list_drivers(database_type: str = None, driver_type: str = None):
    return svc.list_drivers(database_type, driver_type)


@router.delete("/drivers/{driver_id}")
def delete_driver(driver_id: str):
    if not svc.delete_driver(driver_id):
        raise HTTPException(404)
    return {"ok": True}


@router.post("/plugins", response_model=PluginOut)
def register_plugin(req: PluginRegister):
    return svc.register_plugin(req)


@router.get("/plugins", response_model=list[PluginOut])
def list_plugins(plugin_type: str = None, is_enabled: bool = None):
    return svc.list_plugins(plugin_type, is_enabled)


@router.put("/plugins/{plugin_id}/toggle")
def toggle_plugin(plugin_id: str, enable: bool = True):
    p = svc.toggle_plugin(plugin_id, enable)
    if not p:
        raise HTTPException(404)
    return p


@router.delete("/plugins/{plugin_id}")
def delete_plugin(plugin_id: str):
    if not svc.delete_plugin(plugin_id):
        raise HTTPException(404)
    return {"ok": True}


@router.post("/capabilities", response_model=CapabilityOut)
def register_capability(req: CapabilityCreate):
    return svc.register_capability(req)


@router.get("/capabilities", response_model=list[CapabilityOut])
def list_capabilities(connector_id: str = None, category: str = None):
    return svc.list_capabilities(connector_id, category=category)


@router.delete("/capabilities/{capability_id}")
def delete_capability(capability_id: str):
    if not svc.delete_capability(capability_id):
        raise HTTPException(404)
    return {"ok": True}


@router.post("/certifications", response_model=CertificationOut)
def create_certification(req: CertificationCreate):
    return svc.create_certification(req)


@router.post(
    "/certifications/{certification_id}/certify", response_model=CertificationOut
)
def certify_connector(certification_id: str):
    c = svc.certify_connector(certification_id)
    if not c:
        raise HTTPException(404)
    return c


@router.get("/certifications", response_model=list[CertificationOut])
def list_certifications(connector_id: str = None, status: str = None):
    return svc.list_certifications(connector_id, status)
