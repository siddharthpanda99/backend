"""Ask endpoint for NLP-to-SQL."""

from fastapi import APIRouter, Body, HTTPException
from common_lib.modules.nlp2sql.schemas import (
    AskRequest,
    AskResponse,
)
from common_lib.modules.nlp2sql.service import service

router = APIRouter(prefix="/ask", tags=["NLP-to-SQL"])


@router.post("", response_model=AskResponse)
async def ask_question(payload: AskRequest = Body(...)):
    """Process a natural language question and return SQL + results."""
    try:
        return await service.ask(payload.question, payload.schema_id, payload.dialect)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=str(exc))
