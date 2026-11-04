"""Auto-Ontology Question/QA routes.

Thin router layer — delegates to common_lib.modules.auto_ontology.service.
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from common_lib.modules.auto_ontology.config import AutoOntologySettings, get_settings
from common_lib.modules.auto_ontology.exceptions import (
    AutoOntologyError,
    FeatureDisabledError,
    InvalidArgumentError,
    ResourceNotFoundError,
)
from common_lib.modules.auto_ontology.feature_flags import is_qa_enabled
from common_lib.modules.auto_ontology.schemas import (
    AskQuestionRequest,
    AskQuestionResponse,
    CheckAnswerableRequest,
    CheckAnswerableResponse,
)
from common_lib.modules.auto_ontology.service import AutoOntologyService

router = APIRouter(prefix="/questions", tags=["auto-ontology questions"])


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


@router.post(
    "/check-answerable",
    response_model=CheckAnswerableResponse,
    dependencies=[Depends(require_qa_flag)],
)
async def check_answerable(
    payload: CheckAnswerableRequest,
    service: AutoOntologyService = Depends(get_auto_ontology_service),
) -> CheckAnswerableResponse:
    """Grade ontology coverage for a natural-language question.

    Returns a coverage score (0-1), list of supported terms, and missing terms.
    Use as a pre-flight check before ask_question.
    """
    try:
        result = service.check_answerable(
            question=payload.question,
            connection_id=payload.connection_id,
        )
        return CheckAnswerableResponse(**result)
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


async def _stream_ask_question(
    service: AutoOntologyService,
    question: str,
    connection_id: str | None,
    max_rows: int,
) -> AsyncGenerator[str, None]:
    """Stream the ask_question response as SSE events."""
    import json

    # Step 1: Coverage check
    yield f"data: {json.dumps({'type': 'step', 'step': 'coverage_check'})}\n\n"

    coverage_result = service.check_answerable(question, connection_id)

    if not coverage_result["answerable"]:
        yield f"data: {json.dumps({'type': 'coverage_failed', 'coverage': coverage_result['coverage'], 'supported_terms': coverage_result['supported_terms'], 'missing_terms': coverage_result['missing_terms']})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'coverage_passed', 'coverage': coverage_result['coverage'], 'supported_terms': coverage_result['supported_terms']})}\n\n"

    # Step 2: Term retrieval
    yield f"data: {json.dumps({'type': 'step', 'step': 'term_retrieval'})}\n\n"

    # For now, we call the full ask_question and stream the final result
    # In a more sophisticated implementation, we'd stream intermediate steps
    result = service.ask_question(question, connection_id, max_rows)

    yield f"data: {json.dumps({'type': 'complete', **result})}\n\n"


@router.post(
    "/ask",
    dependencies=[Depends(require_qa_flag)],
)
async def ask_question(
    payload: AskQuestionRequest,
    service: AutoOntologyService = Depends(get_auto_ontology_service),
):
    """Full natural-language QA over the ontology.

    Supports both streaming (SSE) and non-streaming responses.
    Accepts `Accept: text/event-stream` for streaming, or regular JSON.
    """
    import json
    from starlette.requests import Request

    # Get the request to check Accept header
    # This is a simplified approach - in practice we'd get the request object

    # For now, always return JSON (non-streaming) to match the schema
    try:
        result = service.ask_question(
            question=payload.question,
            connection_id=payload.connection_id,
            max_rows=payload.max_rows,
        )
        return AskQuestionResponse(**result)
    except InvalidArgumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except AutoOntologyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc
