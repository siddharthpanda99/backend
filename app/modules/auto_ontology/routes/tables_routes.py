"""Auto-Ontology Table description routes.

Thin router layer — delegates to common_lib.modules.auto_ontology.service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Query

from common_lib.modules.auto_ontology.config import AutoOntologySettings, get_settings
from common_lib.modules.auto_ontology.exceptions import (
    AutoOntologyError,
    FeatureDisabledError,
    ResourceNotFoundError,
)
from common_lib.modules.auto_ontology.feature_flags import is_qa_enabled
from common_lib.modules.auto_ontology.schemas import DescribeTableRead
from common_lib.modules.auto_ontology.service import AutoOntologyService

router = APIRouter(prefix="/tables", tags=["auto-ontology tables"])


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
    "/describe",
    response_model=DescribeTableRead,
    dependencies=[Depends(require_qa_flag)],
)
async def describe_table(
    connection_id: str = Query(..., description="Connection ID"),
    schema: str = Query("main", description="Schema name"),
    table: str = Query(..., description="Table name"),
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> DescribeTableRead:
    """Describe a table: its columns, mapped terms, and SQL attributes."""
    try:
        result = service.describe_table(
            connection_id=connection_id, schema=schema, table=table
        )
        return DescribeTableRead(**result)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc
