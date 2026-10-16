"""nlp2sql catalog browser routes — thin transport (G1)."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.nlp2sql.routes import _shared as shared

router = APIRouter(prefix="/data-intelligence", tags=["NLP-to-SQL — Catalog"])


@router.get("/catalog/{schema_version}", response_model=dict)
async def get_catalog_route(schema_version: str) -> dict:
    try:
        from common_lib.modules.nlp2sql.catalog import adapter

        return adapter.get_snapshot(schema_version)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.get("/catalog-search", response_model=dict)
async def search_catalog_route(q: str = "", top_k: int = 12) -> dict:
    from common_lib.modules.nlp2sql.retrieval.hybrid import lexical_search

    return {"items": lexical_search(q, [], top_k)}
