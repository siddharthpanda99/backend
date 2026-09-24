"""Code Review Session Routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from common_lib.modules.integration.adapters.database_adapter import get_db_port
from common_lib.modules.open_code_review.schemas import (
    CodeReviewSessionCreate,
    CodeReviewSessionList,
    CodeReviewSessionRead,
    CodeReviewSessionUpdate,
    TriggerReviewRequest,
)
from common_lib.modules.open_code_review.service import get_open_code_review_service


def get_db_session() -> Session:
    """Get database session via integration port."""
    engine = get_db_port().get_engine()
    return Session(engine)


router = APIRouter()


@router.post(
    "", response_model=CodeReviewSessionRead, summary="Create code review session"
)
def create_review_session(
    session_data: CodeReviewSessionCreate,
    db: Session = Depends(get_db_session),
):
    """Create a new code review session."""
    service = get_open_code_review_service(db)
    try:
        result = service.create_review_session(session_data.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/trigger", response_model=CodeReviewSessionRead, summary="Trigger code review"
)
def trigger_review(
    request: TriggerReviewRequest,
    db: Session = Depends(get_db_session),
):
    """Trigger a full code review (create session + run)."""
    service = get_open_code_review_service(db)
    try:
        result = service.create_review_session(request.model_dump())
        # Run the review
        result = service.run_review(result["id"])
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "", response_model=CodeReviewSessionList, summary="List code review sessions"
)
def list_review_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    repo_url: str | None = Query(None),
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    pr_id: str | None = Query(None),
    db: Session = Depends(get_db_session),
):
    """List code review sessions with pagination and filters."""
    service = get_open_code_review_service(db)
    try:
        from common_lib.modules.open_code_review.models import ReviewStatus

        status_enum = ReviewStatus(status) if status else None
        result = service.list_review_sessions(
            page=page,
            page_size=page_size,
            repo_url=repo_url,
            project_id=project_id,
            status=status_enum,
            pr_id=pr_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{session_id}",
    response_model=CodeReviewSessionRead,
    summary="Get code review session",
)
def get_review_session(
    session_id: str,
    db: Session = Depends(get_db_session),
):
    """Get a code review session by ID with findings."""
    service = get_open_code_review_service(db)
    result = service.get_review_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.patch(
    "/{session_id}",
    response_model=CodeReviewSessionRead,
    summary="Update code review session",
)
def update_review_session(
    session_id: str,
    session_data: CodeReviewSessionUpdate,
    db: Session = Depends(get_db_session),
):
    """Update a code review session."""
    service = get_open_code_review_service(db)
    try:
        data = session_data.model_dump(exclude_unset=True)
        result = service.update_review_session(session_id, data)
        if not result:
            raise HTTPException(status_code=404, detail="Session not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{session_id}", summary="Delete code review session")
def delete_review_session(
    session_id: str,
    db: Session = Depends(get_db_session),
):
    """Soft delete a code review session."""
    service = get_open_code_review_service(db)
    success = service.delete_review_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "message": "Session deleted"}


@router.post(
    "/{session_id}/run", response_model=CodeReviewSessionRead, summary="Run code review"
)
def run_review(
    session_id: str,
    db: Session = Depends(get_db_session),
):
    """Execute a code review session."""
    service = get_open_code_review_service(db)
    try:
        result = service.run_review(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
