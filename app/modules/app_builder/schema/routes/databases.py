"""
Schema Builder — Database Environment Configuration & Provisioning Routes

/api/v1/schema/databases — CRUD and operations (provision, migrate, run-e2e)
for app-specific database instances across environments (dev, uat, prod).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import (
    SchemaService, AppDatabaseConfigCreate, AppDatabaseConfigResponse,
    AppDatabaseConfigListResponse, E2ERunResponse, APIResponse
)
from common_lib.modules.exceptions import NotFoundError, BadRequestError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/databases", tags=["Schema Databases"])
service = SchemaService()


@router.get("/", response_model=AppDatabaseConfigListResponse)
async def list_databases(
    app_id: str = Query(..., description="The ID of the application"),
    db: Session = Depends(get_session),
):
    items = service.list_databases(db, app_id)
    return AppDatabaseConfigListResponse(
        items=[AppDatabaseConfigResponse.model_validate(item) for item in items],
        total=len(items)
    )


@router.post("/", response_model=AppDatabaseConfigResponse, status_code=201)
async def save_database_config(
    data: AppDatabaseConfigCreate,
    db: Session = Depends(get_session),
):
    record = service.save_database_config(db, data)
    logger.info(f"Saved DB configuration for app '{data.app_id}' env '{data.environment}'")
    return AppDatabaseConfigResponse.model_validate(record)


@router.post("/{config_id}/provision", response_model=APIResponse)
async def provision_database(
    config_id: str,
    db: Session = Depends(get_session),
):
    """
    Spin Up Database. Creates the physical DB and runs table DDL schemas.
    """
    try:
        db_name = service.provision_database(db, config_id)
        return APIResponse(success=True, message=f"Database '{db_name}' spun up and tables created.")
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{config_id}/migrate", response_model=APIResponse)
async def migrate_database(
    config_id: str,
    db: Session = Depends(get_session),
):
    """
    Apply pending migrations to the target database environment.
    """
    try:
        applied_count = service.migrate_database(db, config_id)
        return APIResponse(
            success=True,
            message=f"Applied {applied_count} migrations successfully. target is up to date."
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/run-e2e", response_model=E2ERunResponse)
async def run_e2e_test(
    config_id: str,
    db: Session = Depends(get_session),
):
    """
    Runs integration checks, pings the target database, verifies that tables exist,
    and runs a test transaction to verify write/read/delete operational health.
    """
    try:
        success, traces, error_msg = service.run_e2e_test(db, config_id)
        return E2ERunResponse(success=success, traces=traces, error=error_msg)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
