"""``app.modules.i2w.routes.search`` — universal search endpoints.

Per docs/08_api_contract.md §1.6:

* ``POST /api/v1/i2w/search/commands``
* ``POST /api/v1/i2w/search/workflows``
* ``POST /api/v1/i2w/search/history``
* ``POST /api/v1/i2w/search/templates``
* ``POST /api/v1/i2w/search/tutorials``
* ``POST /api/v1/i2w/search/universal``

Each endpoint is a thin delegate to the corresponding ``i2w_search_*``
@node wrapper in ``common_lib``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status

from app.modules.i2w.routes._helpers import invoke_i2w
from app.modules.i2w.routes.dependencies import (
    I2W_SCOPE_READ,
    _audit_request,
    i2w_deps,
    i2w_identity,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _invoke_search(
    request: Request,
    body: Dict[str, Any],
    *,
    wrapper: str,
    action: str,
) -> Dict[str, Any]:
    identity = await i2w_identity(request=request)
    _audit_request(request, identity, action=action)
    try:
        return invoke_i2w(wrapper, **body)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/search/commands",
    summary="Search the @node command catalog.",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="search"),
    response_model=None,
)
async def search_commands(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_search(
        request,
        body,
        wrapper="i2w_search_commands",
        action="i2w.search.commands",
    )


@router.post(
    "/search/workflows",
    summary="Search the workflow library.",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="search"),
    response_model=None,
)
async def search_workflows(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_search(
        request,
        body,
        wrapper="i2w_search_workflows",
        action="i2w.search.workflows",
    )


@router.post(
    "/search/history",
    summary="Search execution history.",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="search"),
    response_model=None,
)
async def search_history(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_search(
        request,
        body,
        wrapper="i2w_search_history",
        action="i2w.search.history",
    )


@router.post(
    "/search/templates",
    summary="Search templates.",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="search"),
    response_model=None,
)
async def search_templates(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_search(
        request,
        body,
        wrapper="i2w_search_templates",
        action="i2w.search.templates",
    )


@router.post(
    "/search/tutorials",
    summary="Search tutorials.",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="search"),
    response_model=None,
)
async def search_tutorials(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_search(
        request,
        body,
        wrapper="i2w_search_tutorials",
        action="i2w.search.tutorials",
    )


@router.post(
    "/search/universal",
    summary="Composite RAG search across commands + workflows + history.",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="search"),
    response_model=None,
)
async def search_universal(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _invoke_search(
        request,
        body,
        wrapper="i2w_universal_search",
        action="i2w.search.universal",
    )


@router.post(
    "/rag",
    summary="Alias of /search/universal for backwards compatibility.",
    dependencies=i2w_deps(scope=I2W_SCOPE_READ, stage="search"),
    response_model=None,
)
async def rag_alias(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience alias — the brief lists ``POST /i2w/rag`` as a top-level
    RAG endpoint. Same wrapper as ``/search/universal``."""
    return await _invoke_search(
        request,
        body,
        wrapper="i2w_universal_search",
        action="i2w.rag",
    )


__all__ = ["router"]
