"""Auto-Ontology Term routes.

Thin router layer — delegates to common_lib.modules.auto_ontology.service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Query

from common_lib.modules.auto_ontology.config import AutoOntologySettings, get_settings
from common_lib.modules.auto_ontology.exceptions import (
    AutoOntologyError,
    FeatureDisabledError,
    InvalidArgumentError,
    ResourceNotFoundError,
)
from common_lib.modules.auto_ontology.feature_flags import is_qa_enabled
from common_lib.modules.auto_ontology.schemas import (
    TermDetailRead,
    TermRead,
    TermSearchRequest,
    TermSearchResponse,
    TermColumnsRead,
    TermSQLAttributesRead,
)
from common_lib.modules.auto_ontology.service import AutoOntologyService

router = APIRouter(prefix="/terms", tags=["auto-ontology terms"])


def get_auto_ontology_service() -> AutoOntologyService:
    """Dependency that provides an AutoOntologyService instance."""
    settings: AutoOntologySettings = get_settings()
    return AutoOntologyService(db_url=settings.db_url, settings=settings)


def require_qa_flag() -> None:
    """Dependency that checks the QA feature flag."""
    if not is_qa_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auto-ontology QA is disabled. Enable AUTO_ONTOLOGY_QA flag.",
        )


@router.get(
    "/search",
    response_model=TermSearchResponse,
    dependencies=[Depends(require_qa_flag)],
)
async def search_terms(
    q: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(10, ge=1, le=100, description="Maximum results"),
    connection_id: str | None = Query(None, description="Filter by connection ID"),
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> TermSearchResponse:
    """Search for ontology terms by keyword."""
    try:
        result = service.search_terms(query=q, top_k=top_k, connection_id=connection_id)
        return TermSearchResponse(**result)
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@router.get(
    "/{term_id}",
    response_model=TermDetailRead,
    dependencies=[Depends(require_qa_flag)],
)
async def get_term(
    term_id: str,
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> TermDetailRead:
    """Retrieve a term by ID with its columns, SQL attributes, and related terms."""
    try:
        result = service.get_term(term_id)
        return TermDetailRead(**result)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@router.get(
    "/{term_id}/columns",
    response_model=TermColumnsRead,
    dependencies=[Depends(require_qa_flag)],
)
async def get_term_columns(
    term_id: str,
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> TermColumnsRead:
    """List the fully-qualified column names mapped to a term."""
    try:
        result = service.get_term_columns(term_id)
        return TermColumnsRead(**result)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@router.get(
    "/{term_id}/sql-attributes",
    response_model=TermSQLAttributesRead,
    dependencies=[Depends(require_qa_flag)],
)
async def get_term_sql_attributes(
    term_id: str,
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> TermSQLAttributesRead:
    """List the SQLAttribute objects owned by a term."""
    try:
        result = service.get_term_sql_attributes(term_id)
        return TermSQLAttributesRead(**result)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc
