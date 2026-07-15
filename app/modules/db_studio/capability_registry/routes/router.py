"""Thin API routes for Capability Registry & Database Abstraction Layer (UDS Module 09)."""

from fastapi import APIRouter, HTTPException
from typing import List, Optional

from common_lib.modules.db_studio.capability_registry.service import CapabilityRegistryService
from common_lib.modules.db_studio.capability_registry.schemas import (
    CapabilityRegister, CapabilityUpdate, CapabilityOut,
    ConnectorCapabilityAssign, ConnectorCapabilityUpdate, ConnectorCapabilityOut,
    TypeMappingCreate, TypeMappingOut,
    CompatibilityCreate, CompatibilityUpdate, CompatibilityOut,
    NormalizationRuleCreate, NormalizationRuleOut,
    NegotiationRequest, NegotiationResult,
    CapabilityVersionOut,
)

svc = CapabilityRegistryService()


def get_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/capabilities", tags=["Capability Registry"])

    # ── Canonical Capabilities ──────────────────────────────────────

    @router.post("/", response_model=CapabilityOut, status_code=201)
    def create_capability(req: CapabilityRegister):
        return svc.register_capability(req)

    @router.get("/", response_model=List[CapabilityOut])
    def list_capabilities(
        engine: Optional[str] = None,
        capability_group: Optional[str] = None,
        supported: Optional[bool] = None,
        offset: int = 0,
        limit: int = 50,
    ):
        return svc.list_capabilities(engine, capability_group, supported, offset, limit)

    @router.get("/{capability_id}", response_model=CapabilityOut)
    def get_capability(capability_id: str):
        r = svc.get_capability(capability_id)
        if not r:
            raise HTTPException(404, "Capability not found")
        return r

    @router.put("/{capability_id}", response_model=CapabilityOut)
    def update_capability(capability_id: str, req: CapabilityUpdate):
        r = svc.update_capability(capability_id, req)
        if not r:
            raise HTTPException(404, "Capability not found")
        return r

    @router.delete("/{capability_id}", status_code=204)
    def delete_capability(capability_id: str):
        if not svc.delete_capability(capability_id):
            raise HTTPException(404, "Capability not found")

    # ── Capability Versions ──────────────────────────────────────────

    @router.post("/{capability_id}/versions", response_model=CapabilityVersionOut)
    def create_version(capability_id: str, change_notes: Optional[str] = None):
        r = svc.create_version_snapshot(capability_id, change_notes)
        if not r:
            raise HTTPException(404, "Capability not found")
        return r

    @router.get("/{capability_id}/versions", response_model=List[CapabilityVersionOut])
    def list_versions(capability_id: str):
        return svc.list_capability_versions(capability_id)

    # ── Connector Capabilities ───────────────────────────────────────

    @router.post("/connector", response_model=ConnectorCapabilityOut, status_code=201)
    def assign_connector_capability(req: ConnectorCapabilityAssign):
        return svc.assign_connector_capability(req)

    @router.get("/connector", response_model=List[ConnectorCapabilityOut])
    def list_connector_capabilities(
        connector_id: Optional[str] = None,
        capability_group: Optional[str] = None,
        supported: Optional[bool] = None,
    ):
        return svc.list_connector_capabilities(connector_id, capability_group, supported)

    @router.get("/connector/{cc_id}", response_model=ConnectorCapabilityOut)
    def get_connector_capability(cc_id: str):
        r = svc.get_connector_capability(cc_id)
        if not r:
            raise HTTPException(404, "Connector capability not found")
        return r

    @router.put("/connector/{cc_id}", response_model=ConnectorCapabilityOut)
    def update_connector_capability(cc_id: str, req: ConnectorCapabilityUpdate):
        r = svc.update_connector_capability(cc_id, req)
        if not r:
            raise HTTPException(404, "Connector capability not found")
        return r

    @router.delete("/connector/{cc_id}", status_code=204)
    def delete_connector_capability(cc_id: str):
        if not svc.delete_connector_capability(cc_id):
            raise HTTPException(404, "Connector capability not found")

    # ── Negotiation ──────────────────────────────────────────────────

    @router.post("/negotiate", response_model=NegotiationResult)
    def negotiate(req: NegotiationRequest):
        return svc.negotiate(req)

    # ── Type Mappings ───────────────────────────────────────────────

    @router.post("/types", response_model=TypeMappingOut, status_code=201)
    def create_type_mapping(req: TypeMappingCreate):
        return svc.create_type_mapping(req)

    @router.get("/types", response_model=List[TypeMappingOut])
    def list_type_mappings(
        engine: Optional[str] = None,
        canonical_type: Optional[str] = None,
    ):
        return svc.list_type_mappings(engine, canonical_type)

    @router.delete("/types/{mapping_id}", status_code=204)
    def delete_type_mapping(mapping_id: str):
        if not svc.delete_type_mapping(mapping_id):
            raise HTTPException(404, "Type mapping not found")

    @router.get("/types/resolve")
    def resolve_type(engine: str, native_type: str):
        r = svc.resolve_type(engine, native_type)
        if not r:
            raise HTTPException(404, f"No mapping found for {engine}.{native_type}")
        return {"engine": engine, "native_type": native_type, "canonical_type": r}

    # ── Compatibility Matrix ────────────────────────────────────────

    @router.post("/compatibility", response_model=CompatibilityOut, status_code=201)
    def create_compatibility(req: CompatibilityCreate):
        return svc.create_compatibility(req)

    @router.get("/compatibility", response_model=List[CompatibilityOut])
    def list_compatibility(
        source_engine: Optional[str] = None,
        target_engine: Optional[str] = None,
        capability: Optional[str] = None,
    ):
        return svc.list_compatibility(source_engine, target_engine, capability)

    @router.put("/compatibility/{comp_id}", response_model=CompatibilityOut)
    def update_compatibility(comp_id: str, req: CompatibilityUpdate):
        r = svc.update_compatibility(comp_id, req)
        if not r:
            raise HTTPException(404, "Compatibility record not found")
        return r

    @router.delete("/compatibility/{comp_id}", status_code=204)
    def delete_compatibility(comp_id: str):
        if not svc.delete_compatibility(comp_id):
            raise HTTPException(404, "Compatibility record not found")

    # ── Normalization Rules ─────────────────────────────────────────

    @router.post("/normalization", response_model=NormalizationRuleOut, status_code=201)
    def create_normalization_rule(req: NormalizationRuleCreate):
        return svc.create_normalization_rule(req)

    @router.get("/normalization", response_model=List[NormalizationRuleOut])
    def list_normalization_rules(
        engine: Optional[str] = None,
        rule_type: Optional[str] = None,
        is_active: Optional[bool] = None,
    ):
        return svc.list_normalization_rules(engine, rule_type, is_active)

    @router.delete("/normalization/{rule_id}", status_code=204)
    def delete_normalization_rule(rule_id: str):
        if not svc.delete_normalization_rule(rule_id):
            raise HTTPException(404, "Normalization rule not found")

    return router
