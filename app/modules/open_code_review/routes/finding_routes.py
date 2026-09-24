"""Code Review Finding Routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from common_lib.modules.integration.adapters.database_adapter import get_db_port
from common_lib.modules.open_code_review.schemas import (
    CodeReviewFindingList,
    CodeReviewFindingRead,
)
from common_lib.modules.open_code_review.service import get_open_code_review_service


def get_db_session() -> Session:
    """Get database session via integration port."""
    engine = get_db_port().get_engine()
    return Session(engine)


router = APIRouter()


@router.get(
    "/{session_id}/findings",
    response_model=CodeReviewFindingList,
    summary="Get findings for session",
)
def get_findings(
    session_id: str,
    severity: str | None = Query(
        None, description="Filter by severity: critical, high, medium, low, info"
    ),
    file_path: str | None = Query(None, description="Filter by file path"),
    rule_id: str | None = Query(None, description="Filter by rule ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db_session),
):
    """Get findings for a code review session with filters."""
    service = get_open_code_review_service(db)
    try:
        from common_lib.modules.open_code_review.models import FindingSeverity

        severity_enum = FindingSeverity(severity) if severity else None
        result = service.get_findings(
            session_id=session_id,
            severity=severity_enum,
            file_path=file_path,
            rule_id=rule_id,
            page=page,
            page_size=page_size,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
