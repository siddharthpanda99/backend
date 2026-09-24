"""Code Review Ruleset Routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from common_lib.modules.integration.adapters.database_adapter import get_db_port
from common_lib.modules.open_code_review.schemas import (
    CodeReviewRulesetCreate,
    CodeReviewRulesetRead,
    CodeReviewRulesetUpdate,
)
from common_lib.modules.open_code_review.service import get_open_code_review_service


def get_db_session() -> Session:
    """Get database session via integration port."""
    engine = get_db_port().get_engine()
    return Session(engine)


router = APIRouter()


@router.get("", summary="List rulesets")
def list_rulesets(
    language: str | None = Query(None, description="Filter by language"),
    ruleset_type: str | None = Query(None, description="builtin or custom"),
    enabled: bool | None = Query(None, description="Filter by enabled status"),
    db: Session = Depends(get_db_session),
):
    """List available rulesets."""
    service = get_open_code_review_service(db)
    try:
        from common_lib.modules.open_code_review.models import RulesetType

        type_enum = RulesetType(ruleset_type) if ruleset_type else None
        result = service.get_rulesets(
            language=language,
            ruleset_type=type_enum,
            enabled=enabled,
        )
        return {"items": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("", response_model=CodeReviewRulesetRead, summary="Create custom ruleset")
def create_ruleset(
    ruleset_data: CodeReviewRulesetCreate,
    db: Session = Depends(get_db_session),
):
    """Create a custom ruleset."""
    service = get_open_code_review_service(db)
    try:
        result = service.create_custom_ruleset(ruleset_data.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{ruleset_id}", response_model=CodeReviewRulesetRead, summary="Get ruleset"
)
def get_ruleset(
    ruleset_id: str,
    db: Session = Depends(get_db_session),
):
    """Get a ruleset by ID."""
    service = get_open_code_review_service(db)
    result = service.get_rulesets()
    for r in result:
        if r["id"] == ruleset_id:
            return r
    raise HTTPException(status_code=404, detail="Ruleset not found")


@router.patch(
    "/{ruleset_id}", response_model=CodeReviewRulesetRead, summary="Update ruleset"
)
def update_ruleset(
    ruleset_id: str,
    ruleset_data: CodeReviewRulesetUpdate,
    db: Session = Depends(get_db_session),
):
    """Update a custom ruleset."""
    service = get_open_code_review_service(db)
    try:
        data = ruleset_data.model_dump(exclude_unset=True)
        result = service.update_ruleset(ruleset_id, data)
        if not result:
            raise HTTPException(
                status_code=404, detail="Ruleset not found or not custom"
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{ruleset_id}", summary="Delete ruleset")
def delete_ruleset(
    ruleset_id: str,
    db: Session = Depends(get_db_session),
):
    """Soft delete a custom ruleset."""
    service = get_open_code_review_service(db)
    success = service.delete_ruleset(ruleset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Ruleset not found or not custom")
    return {"success": True, "message": "Ruleset deleted"}


@router.post("/initialize-builtin", summary="Initialize built-in rulesets")
def initialize_builtin_rulesets(
    db: Session = Depends(get_db_session),
):
    """Initialize built-in rulesets (NPE, thread-safety, XSS, SQL injection, etc.)."""
    service = get_open_code_review_service(db)
    try:
        result = service.initialize_builtin_rulesets()
        return {"results": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
