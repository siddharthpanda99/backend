"""Code Review Config Routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from common_lib.modules.integration.adapters.database_adapter import get_db_port
from common_lib.modules.open_code_review.schemas import (
    CodeReviewConfigCreate,
    CodeReviewConfigList,
    CodeReviewConfigRead,
    CodeReviewConfigUpdate,
)
from common_lib.modules.open_code_review.service import get_open_code_review_service


def get_db_session() -> Session:
    """Get database session via integration port."""
    engine = get_db_port().get_engine()
    return Session(engine)


router = APIRouter()


@router.post(
    "", response_model=CodeReviewConfigRead, summary="Create/update review config"
)
def create_or_update_config(
    config_data: CodeReviewConfigCreate,
    db: Session = Depends(get_db_session),
):
    """Create or update review configuration for a repository."""
    service = get_open_code_review_service(db)
    try:
        result = service.configure_review(config_data.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{repo_url:path}", response_model=CodeReviewConfigRead, summary="Get review config"
)
def get_config(
    repo_url: str,
    db: Session = Depends(get_db_session),
):
    """Get review configuration for a repository."""
    service = get_open_code_review_service(db)
    result = service.get_review_config(repo_url)
    if not result:
        raise HTTPException(status_code=404, detail="Config not found")
    return result


@router.get("", response_model=CodeReviewConfigList, summary="List review configs")
def list_configs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: str | None = Query(None),
    db: Session = Depends(get_db_session),
):
    """List all review configurations."""
    service = get_open_code_review_service(db)
    try:
        result = service.list_review_configs(
            page=page, page_size=page_size, project_id=project_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/{repo_url:path}",
    response_model=CodeReviewConfigRead,
    summary="Update review config",
)
def update_config(
    repo_url: str,
    config_data: CodeReviewConfigUpdate,
    db: Session = Depends(get_db_session),
):
    """Update review configuration for a repository."""
    service = get_open_code_review_service(db)
    try:
        # Get existing config
        existing = service.get_review_config(repo_url)
        if not existing:
            raise HTTPException(status_code=404, detail="Config not found")

        # Merge updates
        data = config_data.model_dump(exclude_unset=True)
        data["repo_url"] = repo_url
        result = service.configure_review(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{repo_url:path}", summary="Delete review config")
def delete_config(
    repo_url: str,
    db: Session = Depends(get_db_session),
):
    """Soft delete a review configuration."""
    service = get_open_code_review_service(db)
    # This would need a delete method in service
    # For now, return not implemented
    raise HTTPException(status_code=501, detail="Not implemented")
