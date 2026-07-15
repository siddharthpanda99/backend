"""Thin backend route wrappers for Import, Export & Data Exchange (UDS Module 14)."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.data_exchange import (
    DataExchangeService,
    ImportRequest, ImportOut,
    ExportRequest, ExportOut,
    MappingTemplateCreate, MappingTemplateOut,
    ValidationRequest, ValidationOut,
    TransformationRuleCreate, TransformationRuleOut,
    ExchangeDashboardOut,
    TransferHistoryOut, ExchangeAuditOut,
)

service = DataExchangeService()


def get_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/data-exchange", tags=["Import, Export & Data Exchange"])

    @router.get("/dashboard", response_model=ExchangeDashboardOut)
    async def get_dashboard():
        return service.get_dashboard()

    # ── Import ────────────────────────────────────────────────────────

    @router.post("/imports", response_model=ImportOut)
    async def run_import(req: ImportRequest):
        return service.run_import(req)

    @router.get("/imports", response_model=list[ImportOut])
    async def list_imports(connection_id: str = None, status: str = None, limit: int = 50):
        return service.list_imports(connection_id, status, limit)

    @router.get("/imports/{import_id}", response_model=ImportOut)
    async def get_import(import_id: str):
        result = service.get_import(import_id)
        if not result:
            raise HTTPException(status_code=404, detail="Import not found")
        return result

    # ── Export ────────────────────────────────────────────────────────

    @router.post("/exports", response_model=ExportOut)
    async def run_export(req: ExportRequest):
        return service.run_export(req)

    @router.get("/exports", response_model=list[ExportOut])
    async def list_exports(connection_id: str = None, status: str = None, limit: int = 50):
        return service.list_exports(connection_id, status, limit)

    @router.get("/exports/{export_id}", response_model=ExportOut)
    async def get_export(export_id: str):
        result = service.get_export(export_id)
        if not result:
            raise HTTPException(status_code=404, detail="Export not found")
        return result

    # ── Mapping Templates ────────────────────────────────────────────

    @router.post("/mappings", response_model=MappingTemplateOut)
    async def create_mapping(req: MappingTemplateCreate):
        return service.create_mapping(req)

    @router.get("/mappings", response_model=list[MappingTemplateOut])
    async def list_mappings(source_format: str = None, target_format: str = None, limit: int = 50):
        return service.list_mappings(source_format, target_format, limit)

    # ── Validation ───────────────────────────────────────────────────

    @router.post("/validate", response_model=ValidationOut)
    async def validate(req: ValidationRequest):
        return service.validate(req)

    # ── Transformation Rules ─────────────────────────────────────────

    @router.post("/transform-rules", response_model=TransformationRuleOut)
    async def create_transform_rule(req: TransformationRuleCreate):
        return service.create_transform_rule(req)

    @router.get("/transform-rules", response_model=list[TransformationRuleOut])
    async def list_transform_rules(rule_type: str = None, is_active: bool = None, limit: int = 50):
        return service.list_transform_rules(rule_type, is_active, limit)

    # ── Transfer History ─────────────────────────────────────────────

    @router.get("/history", response_model=list[TransferHistoryOut])
    async def list_transfer_history(direction: str = None, connection_id: str = None, limit: int = 50):
        return service.list_transfer_history(direction, connection_id, limit)

    # ── Audit ────────────────────────────────────────────────────────

    @router.get("/audit", response_model=list[ExchangeAuditOut])
    async def list_audit_logs(
        action: str = None, target_type: str = None,
        severity: str = None, limit: int = 50,
    ):
        return service.list_audit_logs(action, target_type, severity, limit)

    return router
