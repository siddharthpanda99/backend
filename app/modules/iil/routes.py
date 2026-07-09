"""IIL (Internet Intelligence Layer) — FastAPI routes.

All business logic lives in common_lib.modules.iil.service.
Routes are thin wrappers that handle HTTP concerns (parsing, status codes, error mapping).
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Body

from common_lib.modules.iil.service import IILService
from common_lib.modules.iil.schemas import (
    SearchRequest,
    SearchResponse,
    ScrapeRequest,
    ScrapeResponse,
    ResearchRequest,
    ResearchResponse,
    VerifyFactRequest,
    VerifyFactResponse,
    IngestRequest,
    IngestResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    CacheStats,
    CacheClearRequest,
    CacheClearResponse,
    SecurityScanResult,
    MonitorTargetCreate,
    MonitorTargetUpdate,
    MonitorTargetResponse,
    MonitorCheckResponse,
    MonitorListResponse,
    BrowserRequest,
    BrowserResponse,
    IILResult,
    AnalyticsResponse,
    CacheHitRatePoint,
    AnalyticsConfigResponse,
)
from common_lib.modules.iil.core.security import (
    scan_content,
    check_url_safety,
    add_blocked_domain,
    remove_blocked_domain,
)
from common_lib.modules.iil.core.analytics import get_analytics
from common_lib.modules.data_storage.database.constants import DEFAULT_DB_URL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/iil", tags=["Internet Intelligence Layer"])

# Global service instance (lazy init)
_iil_service: Optional[IILService] = None


def _get_service() -> IILService:
    global _iil_service
    if _iil_service is None:
        _iil_service = IILService()
    return _iil_service


_analytics_inited = False


def _get_analytics():
    """Get the analytics singleton, initializing with DB URL on first call."""
    global _analytics_inited
    if not _analytics_inited:
        import os
        db_url = os.getenv("DATABASE_URL", DEFAULT_DB_URL)
        get_analytics(db_url=db_url)
        _analytics_inited = True
    return get_analytics()


# =============================================================================
# Search Endpoints
# =============================================================================


@router.post("/search", response_model=IILResult)
async def search(request: SearchRequest):
    """Search the web using the Internet Intelligence Layer.

    Uses RRF fusion across multiple search providers for best results.
    Supports intent-based routing, time range filtering, and caching.
    """
    service = _get_service()
    _get_analytics().track_request("search")
    result = await service.search(
        query=request.query,
        intent=request.intent,
        n=request.n,
        time_range=request.time_range,
        bypass_cache=request.bypass_cache,
        providers=request.providers,
    )
    if result.error:
        raise HTTPException(status_code=502, detail=result.error)
    if hasattr(result, "cache_hit"):
        _get_analytics().track_cache_event(hit=bool(result.cache_hit))
    return result


@router.get("/search", response_model=IILResult)
async def search_get(
    q: str = Query(..., description="Search query"),
    intent: str = Query("general", description="Query intent"),
    n: int = Query(10, ge=1, le=100),
    time_range: Optional[str] = Query(None),
):
    """GET variant of search (simple queries via URL params)."""
    service = _get_service()
    _get_analytics().track_request("search")
    result = await service.search(query=q, intent=intent, n=n, time_range=time_range)
    if hasattr(result, "cache_hit"):
        _get_analytics().track_cache_event(hit=bool(result.cache_hit))
    return result


# =============================================================================
# Scrape / Fetch Endpoints
# =============================================================================


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape(request: ScrapeRequest):
    """Fetch and extract content from a URL.

    Auto-detects the best fetch method (HTTP, Playwright, or specialized extractor).
    Applies security scanning for prompt injection before returning content.
    """
    service = _get_service()
    _get_analytics().track_request("scrape")
    result = await service.scrape(
        url=request.url,
        extract_mode=request.extract_mode,
        js_required=request.js_required,
        max_chars=request.max_chars,
        screenshot=request.screenshot,
        bypass_cache=request.bypass_cache,
        scroll_to_bottom=request.scroll_to_bottom,
        wait_for_selector=request.wait_for_selector,
    )
    if result.error:
        _get_analytics().track_error("scrape")
    _get_analytics().track_cache_event(hit=bool(result.cache_hit))
    return result


@router.get("/scrape", response_model=ScrapeResponse)
async def scrape_get(
    url: str = Query(..., description="URL to fetch and extract"),
    extract_mode: str = Query("markdown"),
):
    """GET variant of scrape (simple URL fetch via query param)."""
    service = _get_service()
    _get_analytics().track_request("scrape")
    result = await service.scrape(url=url, extract_mode=extract_mode)
    if result.error:
        _get_analytics().track_error("scrape")
    _get_analytics().track_cache_event(hit=bool(result.cache_hit))
    return result


# =============================================================================
# Research Endpoints
# =============================================================================


@router.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest):
    """Multi-step deep research with verification.

    Searches, fetches top pages, extracts content, cross-references claims,
    and synthesizes a research summary.
    """
    service = _get_service()
    _get_analytics().track_request("research")
    result = await service.research(
        query=request.query,
        depth=request.depth,
        verify=request.verify,
        min_sources=request.min_sources,
        include_code=request.include_code,
        include_papers=request.include_papers,
        include_news=request.include_news,
        max_pages=request.max_pages,
        bypass_cache=request.bypass_cache,
    )
    if result.error:
        _get_analytics().track_error("research")
        raise HTTPException(status_code=502, detail=result.error)
    if hasattr(result, "cache_hit"):
        _get_analytics().track_cache_event(hit=bool(result.cache_hit))
    return result


# =============================================================================
# Fact Verification Endpoints
# =============================================================================


@router.post("/verify", response_model=VerifyFactResponse)
async def verify_fact(request: VerifyFactRequest):
    """Cross-reference a factual claim across multiple independent sources."""
    service = _get_service()
    _get_analytics().track_request("verify")
    result = await service.verify_fact(
        claim=request.claim,
        min_agreeing_sources=request.min_agreeing_sources,
        search_providers=request.search_providers,
    )
    if result.error:
        raise HTTPException(status_code=502, detail=result.error)
    return result


# =============================================================================
# Knowledge Base Endpoints
# =============================================================================


@router.post("/knowledge/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest):
    """Ingest a URL into the IIL knowledge base."""
    service = _get_service()
    _get_analytics().track_request("ingest")
    result = await service.ingest(request)
    if result.error:
        raise HTTPException(status_code=502, detail=result.error)
    return result


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def knowledge_search(request: KnowledgeSearchRequest):
    """Search the accumulated IIL knowledge base."""
    service = _get_service()
    return service.search_knowledge(request)


@router.get("/knowledge/stats")
async def knowledge_stats():
    """Get knowledge base statistics."""
    service = _get_service()
    return service.get_knowledge_stats()


# =============================================================================
# Monitor Target Endpoints
# =============================================================================


@router.get("/monitors", response_model=MonitorListResponse)
async def list_monitors(
    search: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    enabled_only: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List monitor targets."""
    from common_lib.modules.iil.monitoring.monitor import MonitorService

    return MonitorService().list_targets(
        search=search,
        target_type=target_type,
        enabled_only=enabled_only,
        offset=offset,
        limit=limit,
    )


@router.get("/monitors/{target_id}", response_model=MonitorTargetResponse)
async def get_monitor(target_id: str):
    """Get a monitor target by ID."""
    from common_lib.modules.iil.monitoring.monitor import MonitorService

    try:
        return MonitorService().get_target(target_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/monitors", response_model=MonitorTargetResponse, status_code=201)
async def create_monitor(request: MonitorTargetCreate):
    """Create a new monitor target."""
    from common_lib.modules.iil.monitoring.monitor import MonitorService

    return MonitorService().create_target(request)


@router.put("/monitors/{target_id}", response_model=MonitorTargetResponse)
async def update_monitor(target_id: str, request: MonitorTargetUpdate):
    """Update a monitor target."""
    from common_lib.modules.iil.monitoring.monitor import MonitorService

    try:
        return MonitorService().update_target(target_id, request)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/monitors/{target_id}")
async def delete_monitor(target_id: str):
    """Delete a monitor target."""
    from common_lib.modules.iil.monitoring.monitor import MonitorService

    try:
        return MonitorService().delete_target(target_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/monitors/{target_id}/check", response_model=MonitorCheckResponse)
async def check_monitor(target_id: str):
    """Check a monitor target for changes immediately."""
    from common_lib.modules.iil.monitoring.monitor import MonitorService

    try:
        return MonitorService().check_target(target_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitors/check-all", response_model=List[MonitorCheckResponse])
async def check_all_monitors():
    """Check all due monitor targets."""
    from common_lib.modules.iil.monitoring.monitor import MonitorService

    return MonitorService().check_all_due()


# =============================================================================
# Cache Management Endpoints
# =============================================================================


@router.get("/cache/stats", response_model=CacheStats)
async def cache_stats():
    """Get IIL cache statistics."""
    service = _get_service()
    return service.get_cache_stats()


@router.post("/cache/clear", response_model=CacheClearResponse)
async def clear_cache(request: CacheClearRequest):
    """Clear the IIL cache."""
    service = _get_service()
    if request.clear_all:
        cleared = service.clear_cache()
        return CacheClearResponse(
            entries_cleared=cleared,
            success=True,
            message=f"Cleared {cleared} hot cache entries",
        )
    if request.older_than_hours:
        cleared = service.clear_cache()
        return CacheClearResponse(
            entries_cleared=cleared,
            success=True,
            message=f"Cleared {cleared} cache entries older than {request.older_than_hours}h",
        )
    return CacheClearResponse(
        entries_cleared=0, success=True, message="No action taken"
    )


# =============================================================================
# Security Endpoints
# =============================================================================


@router.post("/security/scan", response_model=SecurityScanResult)
async def security_scan(
    url: str = Body(..., embed=True), content: str = Body("", embed=True)
):
    """Scan a URL and/or content for security threats (SSRF, prompt injection)."""
    from common_lib.modules.iil.core.security import check_url_and_content

    result = check_url_and_content(url, content)
    return result


@router.post("/security/domains/block")
async def block_domain(domain: str = Body(..., embed=True)):
    """Add a domain to the block list."""
    add_blocked_domain(domain)
    return {
        "status": "success",
        "domain": domain,
        "message": f"Domain '{domain}' added to block list",
    }


@router.post("/security/domains/unblock")
async def unblock_domain(domain: str = Body(..., embed=True)):
    """Remove a domain from the block list."""
    remove_blocked_domain(domain)
    return {
        "status": "success",
        "domain": domain,
        "message": f"Domain '{domain}' removed from block list",
    }


# =============================================================================
# Browser Use — Autonomous navigation (§4.2)
# =============================================================================


@router.post("/browse", response_model=BrowserResponse)
async def browse_endpoint(request: BrowserRequest):
    """Execute an autonomous browsing task using an LLM-guided browser agent.

    The agent navigates a website interactively (click, type, scroll, fill forms)
    to complete a natural language task. Requires browser-use and langchain-ollama
    to be installed on the server.

    Use for: login flows, multi-page forms, authenticated data extraction,
    interactive search requiring javascript execution.
    """
    service = _get_service()
    result = await service.browse(
        task=request.task,
        start_url=request.start_url,
        max_steps=request.max_steps,
    )
    if result.error:
        raise HTTPException(status_code=502, detail=result.error)
    return result


# =============================================================================
# OCR — Image & scanned PDF text extraction (§5.2)
# =============================================================================


@router.post("/ocr", response_model=ScrapeResponse)
async def ocr_endpoint(
    url: str = Body(..., description="URL of image or PDF to OCR"),
    language: str = Body(
        "eng", description="Language code (eng, fra, deu, jpn, chi_sim)"
    ),
    max_chars: int = Body(50000, ge=100, le=500000),
):
    """Extract text from an image or scanned PDF using OCR.

    Auto-selects the best available OCR backend:
    PaddleOCR → Tesseract → EasyOCR (in order of preference).

    Supports images (PNG, JPG, WebP, BMP, GIF) and scanned PDFs.
    Applies SSRF protection before fetching.
    """
    service = _get_service()
    result = await service.ocr_extract(
        url=url,
        language=language,
        max_chars=max_chars,
    )
    if result.error:
        raise HTTPException(status_code=502, detail=result.error)
    return result


# =============================================================================
# Robots.txt — Crawl policy compliance (§11.4)
# =============================================================================


@router.post("/robots-check", response_model=Dict[str, Any])
async def robots_check_endpoint(
    url: str = Body(..., description="URL to check robots.txt for"),
    user_agent: str = Body("IIL-Bot/1.0", description="User agent string"),
):
    """Check if a URL can be crawled according to its robots.txt policy.

    Returns whether crawling is allowed, the crawl delay, and any sitemaps
    declared in the site's robots.txt. Results are cached per-domain.
    """
    service = _get_service()
    result = await service.check_robots(
        url=url,
        user_agent=user_agent,
    )
    return result


# =============================================================================
# Debug — Read-only table browser for IIL database tables
# =============================================================================


@router.get("/debug/tables")
async def list_debug_tables():
    """List available IIL debug tables."""
    return {
        "tables": [
            {
                "name": "iil_artifacts",
                "label": "Artifacts",
                "description": "Retrieved knowledge artifacts (search results, scraped pages)",
                "columns": [
                    "id",
                    "source_url",
                    "source_type",
                    "title",
                    "author",
                    "language",
                    "word_count",
                    "trust_score",
                    "retrieved_at",
                ],
            },
            {
                "name": "iil_chunks",
                "label": "Chunks",
                "description": "Chunked content for embedding and vector search",
                "columns": [
                    "id",
                    "artifact_id",
                    "content",
                    "chunk_index",
                    "chunk_total",
                    "content_tokens",
                    "embedding_model",
                    "created_at",
                ],
            },
            {
                "name": "iil_cache",
                "label": "Cache",
                "description": "Semantic cache for queries and fetch results",
                "columns": [
                    "id",
                    "query",
                    "source_url",
                    "ttl_seconds",
                    "trust_score",
                    "is_fresh",
                    "created_at",
                    "expires_at",
                ],
            },
            {
                "name": "iil_prompt_injection_log",
                "label": "Prompt Injection Log",
                "description": "Audit log for detected prompt injection attempts during search/scrape operations",
                "columns": [
                    "id",
                    "source_url",
                    "pattern_matched",
                    "severity",
                    "content_preview",
                    "is_blocked",
                    "detected_at",
                ],
            },
        ]
    }


@router.get("/debug/tables/{table_name}")
async def get_debug_table(
    table_name: str,
    order_by: str = Query("created_at", description="Sort column"),
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    filters: Optional[str] = Query(None, description="JSON column filters e.g. {\"severity\":[\"high\",\"critical\"]}"),
    date_range_hours: Optional[int] = Query(None, description="Date range in trailing hours (e.g. 24 for last 24h)"),
    date_column: Optional[str] = Query(None, description="Date column to apply date_range to"),
):
    """Query a debug table with pagination + server-side filtering.

    Supports column-specific filters and date-range presets via SQL WHERE clauses.
    """
    import json

    allowed_tables = {
        "iil_artifacts",
        "iil_chunks",
        "iil_cache",
        "iil_prompt_injection_log",
    }
    if table_name not in allowed_tables:
        raise HTTPException(
            status_code=404, detail=f"Unknown debug table: {table_name}"
        )

    column_filters = None
    if filters:
        try:
            column_filters = json.loads(filters)
            if not isinstance(column_filters, dict):
                column_filters = None
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid filters JSON")

    date_cutoff = None
    if date_range_hours and date_column:
        import time as time_module
        date_cutoff = (time_module.time() - date_range_hours * 3600) * 1000

    service = _get_service()
    try:
        rows, total = await service._query_table(
            table_name,
            order_by=order_by,
            direction=direction,
            limit=limit,
            offset=offset,
            column_filters=column_filters,
            date_column=date_column,
            date_cutoff=date_cutoff,
        )
        return {
            "table": table_name,
            "total": total,
            "rows": rows,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Health Check
# =============================================================================


@router.get("/analytics", response_model=AnalyticsResponse)
async def iil_analytics(
    hours: int = Query(24, ge=1, le=48, description="Trailing hours to include"),
):
    """Get request volume analytics for sparkline display.

    Returns hourly request counts for the last N hours.
    Hours with no activity are included as zero-count data points.
    """
    analytics = _get_analytics()
    data_points = analytics.get_request_volume(hours=hours)
    total = analytics.get_total_requests()
    max_count = max((dp.count for dp in data_points), default=0)
    operations_total = analytics.get_operations_breakdown()
    cache_data = analytics.get_cache_hit_rate_data(hours=hours)
    overall_cache_rate = analytics.get_overall_cache_hit_rate()
    total_errors = analytics.get_total_errors()
    error_rate_scrape = round(analytics.get_error_rate("scrape") * 100, 1)
    error_rate_research = round(analytics.get_error_rate("research") * 100, 1)
    return AnalyticsResponse(
        data_points=data_points,
        total_tracked=total,
        max_count=max_count,
        operations_total=operations_total,
        cache_hit_rate_data=[
            CacheHitRatePoint(**cd) for cd in cache_data
        ],
        overall_cache_hit_rate=round(overall_cache_rate * 100, 1),
        total_errors=total_errors,
        error_rate_scrape=error_rate_scrape,
        error_rate_research=error_rate_research,
    )


@router.get("/analytics/config", response_model=AnalyticsConfigResponse)
async def analytics_config():
    """Get current analytics retention policy configuration."""
    analytics = _get_analytics()
    return AnalyticsConfigResponse(
        retention_days=analytics.get_retention_days(),
    )


@router.put("/analytics/config", response_model=AnalyticsConfigResponse)
async def update_analytics_config(body: dict = Body(...)):
    """Update analytics retention policy at runtime.

    Accepts {"retention_days": <int>}. The new value takes effect
    on the next periodic prune cycle (up to 24h delay).
    """
    days = body.get("retention_days")
    if not isinstance(days, int) or days < 1 or days > 365:
        raise HTTPException(
            status_code=400,
            detail="retention_days must be an integer between 1 and 365",
        )
    analytics = _get_analytics()
    analytics.set_retention_days(days)
    return AnalyticsConfigResponse(
        retention_days=analytics.get_retention_days(),
    )


@router.post("/analytics/reset")
async def reset_analytics():
    """Reset all IIL analytics data.

    Clears in-memory buckets and deletes all rows from the
    iil_analytics_buckets table. Use with care — historical
    sparkline data will be lost.
    """
    analytics = _get_analytics()
    analytics.reset()
    return {"status": "success", "message": "All analytics data cleared"}


@router.get("/health")
async def iil_health():
    """IIL module health check."""
    service = _get_service()
    import os
    max_capacity = int(os.getenv("IIL_MAX_CAPACITY", "0"))
    return {
        "status": "healthy",
        "module": "Internet Intelligence Layer",
        "cache": service.get_cache_stats().model_dump(),
        "max_capacity": max_capacity,
    }
