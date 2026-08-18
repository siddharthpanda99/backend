"""Memory MQL (Memory Query Language) API Routes."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/mql", tags=["Memory MQL"])

logger = logging.getLogger(__name__)


@router.post("/execute")
async def execute(
    query: str = Body(...),
    params: Optional[Dict[str, Any]] = Body(None),
):
    try:
        from common_lib.modules.memory.memory_mql.executor import get_mql_executor

        executor = get_mql_executor()
        return await executor.execute(query=query, params=params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate(query: str = Body(...)):
    try:
        from common_lib.modules.memory.memory_mql.validator import get_mql_validator

        validator = get_mql_validator()
        return await validator.validate(query=query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse")
async def parse(query: str = Body(...)):
    try:
        from common_lib.modules.memory.memory_mql.parser import get_mql_parser

        parser = get_mql_parser()
        return await parser.parse(query=query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain")
async def explain(query: str = Body(...)):
    try:
        from common_lib.modules.memory.memory_mql.explainer import get_mql_explainer

        explainer = get_mql_explainer()
        return await explainer.explain(query=query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/functions")
async def list_functions():
    try:
        from common_lib.modules.memory.memory_mql.functions import (
            get_mql_function_registry,
        )

        registry = get_mql_function_registry()
        return await registry.list_functions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
