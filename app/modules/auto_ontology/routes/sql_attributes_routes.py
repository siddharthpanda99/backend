"""Auto-Ontology SQL Attribute routes.

Thin router layer — delegates to common_lib.modules.auto_ontology.service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from common_lib.modules.auto_ontology.config import AutoOntologySettings, get_settings
from common_lib.modules.auto_ontology.exceptions import (
    AutoOntologyError,
    FeatureDisabledError,
    ResourceNotFoundError,
)
from common_lib.modules.auto_ontology.feature_flags import is_qa_enabled
from common_lib.modules.auto_ontology.schemas import SQLAttributeRead
from common_lib.modules.auto_ontology.service import AutoOntologyService

router = APIRouter(prefix="/sql-attributes", tags=["auto-ontology sql-attributes"])


def get_auto_ontology_service() -> AutoOntologyService:
    """Dependency that provides an AutoOntologyService instance."""
    settings = get_settings()
    return AutoOntologyService(db_url=settings.db_url, settings=settings)


def require_qa_flag() -> None:
    """Dependency that checks the QA feature flag."""
    if not is_qa_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auto-ontology QA is disabled. Enable AUTO_ONTOLOGY_QA flag.",
        )


@router.get(
    "/{attr_id}",
    response_model=SQLAttributeRead,
    dependencies=[Depends(require_qa_flag)],
)
async def get_sql_attribute(
    attr_id: str,
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> SQLAttributeRead:
    """Retrieve a single SQLAttribute by its ID."""
    try:
        from common_lib.modules.auto_ontology.exceptions import ResourceNotFoundError

        result = service.get_sql_attribute(attr_id)
        return SQLAttributeRead(**result)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc
