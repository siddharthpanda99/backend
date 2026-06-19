import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from common_lib.modules.orchestration.infrastructure.sd.models import SdModelRecord
from common_lib.modules.orchestration.infrastructure.sd.service import SdModelService
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.data_storage.database.repository import NotFoundError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sd-models", tags=["SD Models"])
_svc = SdModelService()


class SdModelSchema(BaseModel):
    id: str
    name: str
    type: str
    fs_path: str
    trigger_words: List[str] = []
    is_active: bool = True
    metadata_json: Dict[str, Any] = {}
    created_at: Any = None
    updated_at: Any = None

    class Config:
        from_attributes = True


class SdModelUpdateRequest(BaseModel):
    name: Optional[str] = None
    trigger_words: Optional[List[str]] = None
    is_active: Optional[bool] = None
    metadata_json: Optional[Dict[str, Any]] = None


@router.get("/", response_model=List[SdModelSchema])
async def list_sd_models(
    type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    offset: int = Query(0),
    limit: int = Query(100),
):
    with next(get_session()) as session:
        return _svc.list_models(
            session, type=type, search=search, offset=offset, limit=limit
        )


@router.get("/{model_id}", response_model=SdModelSchema)
async def get_sd_model(model_id: str):
    with next(get_session()) as session:
        try:
            return _svc.get_model(session, model_id)
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Model not found")


@router.patch("/{model_id}", response_model=SdModelSchema)
async def update_sd_model(model_id: str, request: SdModelUpdateRequest):
    with next(get_session()) as session:
        try:
            return _svc.update_model(
                session, model_id, request.dict(exclude_unset=True)
            )
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Model not found")


@router.post("/sync")
async def sync_sd_models():
    with next(get_session()) as session:
        try:
            return _svc.sync_from_filesystem(session)
        except FileNotFoundError as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{model_id}")
async def delete_sd_model_record(model_id: str):
    with next(get_session()) as session:
        try:
            _svc.delete_model(session, model_id)
            return {"status": "success", "message": "Model record deleted"}
        except NotFoundError:
            raise HTTPException(status_code=404, detail="Model not found")
