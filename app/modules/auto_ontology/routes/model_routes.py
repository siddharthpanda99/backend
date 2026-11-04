"""Auto-Ontology Model portability routes.

Thin router layer — delegates to common_lib.modules.auto_ontology.service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from common_lib.modules.auto_ontology.config import AutoOntologySettings, get_settings
from common_lib.modules.auto_ontology.exceptions import (
    AutoOntologyError,
    FeatureDisabledError,
    InvalidArgumentError,
    ResourceNotFoundError,
)
from common_lib.modules.auto_ontology.feature_flags import is_ingestion_enabled
from common_lib.modules.auto_ontology.schemas import (
    ModelExportResponse,
    ModelImportRequest,
    ModelImportResponse,
)
from common_lib.modules.auto_ontology.service import AutoOntologyService

router = APIRouter(prefix="/model", tags=["auto-ontology model"])


def get_auto_ontology_service() -> AutoOntologyService:
    """Dependency that provides an AutoOntologyService instance."""
    settings = get_settings()
    return AutoOntologyService(db_url=settings.db_url, settings=settings)


def require_ingestion_flag() -> None:
    """Dependency that checks the ingestion feature flag."""
    if not is_ingestion_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auto-ontology ingestion is disabled. Enable AUTO_ONTOLOGY_INGESTION flag.",
        )


@router.post(
    "/import",
    response_model=ModelImportResponse,
    dependencies=[Depends(require_ingestion_flag)],
)
async def import_model(
    payload: ModelImportRequest,
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> ModelImportResponse:
    """Import an Apache Ossie semantic model (YAML) into the ontology."""
    try:
        result = service.import_model(
            ossie_yaml=payload.ossie_yaml,
            connection_id=payload.connection_id,
            replace=payload.replace,
        )
        return ModelImportResponse(**result)
    except InvalidArgumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except FeatureDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=exc.message
        ) from exc
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@router.get(
    "/export",
    response_model=ModelExportResponse,
    dependencies=[Depends(require_ingestion_flag)],
)
async def export_model(
    connection_id: str | None = None,
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> ModelExportResponse:
    """Export the compiled ontology as Apache Ossie YAML."""
    try:
        result = service.export_model(connection_id=connection_id)
        return ModelExportResponse(**result)
    except ResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc
