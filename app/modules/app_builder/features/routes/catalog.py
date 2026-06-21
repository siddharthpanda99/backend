"""
Feature Picker — Aggregated Feature Catalog

Provides the unified feature catalog that combines:
  1. Platform features from the entity registry catalog
     (tools, agents, workflows, skills, prompts, etc.)
  2. Custom features from the feature_definitions table
  3. Aggregated access summary (agent_only, human_only, both)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.features.schemas import (
    CatalogResponse,
    CatalogFeatureItem,
    APIResponse,
)
from common_lib.modules.app_builder.features.service import FeatureService

logger = logging.getLogger(__name__)
router = APIRouter()
service = FeatureService()


@router.get("/catalog", response_model=APIResponse)
async def get_feature_catalog(db: Session = Depends(get_session)):
    """
    Get the aggregated feature catalog combining:
    - Platform features from the entity registry (tools, agents, workflows, etc.)
    - Custom features from feature_definitions table
    """
    catalog = service.get_aggregated_catalog(db)
    return APIResponse(data=catalog)


@router.get("/catalog/{source}/{item_id}", response_model=APIResponse)
async def get_catalog_item(source: str, item_id: str, db: Session = Depends(get_session)):
    """
    Get a single catalog item by its source and ID.
    Falls back to custom features if not found in registry.
    """
    item = service.get_catalog_item(db, source, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Catalog item '{source}/{item_id}' not found")
    return APIResponse(data=item)
