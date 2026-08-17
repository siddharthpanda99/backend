"""SD News API Routes.

Provides REST endpoints for browsing, searching, and managing
the SD News article archive.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/sd-news", tags=["sd-news"])

logger = logging.getLogger(__name__)


class ArchiveArticlesRequest(BaseModel):
    articles: list
    source: str = "reddit"


@router.get("/articles")
async def list_articles(
    query: Optional[str] = Query(None),
    subreddit: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("fetched_at"),
):
    """Search and browse SD News articles."""
    try:
        from common_lib.modules.core_infrastructure.scheduler.news_archive import get_news_archive

        archive = get_news_archive()
        result = archive.search(
            query=query,
            subreddit=subreddit,
            min_score=min_score,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
        )
        return {"status": "ok", **result}
    except Exception as e:
        logger.error(f"Failed to list articles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def news_stats():
    """Get archive statistics."""
    try:
        from common_lib.modules.core_infrastructure.scheduler.news_archive import get_news_archive

        archive = get_news_archive()
        return {"status": "ok", "stats": archive.get_stats()}
    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/archive")
async def archive_articles(request: ArchiveArticlesRequest):
    """Add articles to the archive (called by SD News workflow)."""
    try:
        from common_lib.modules.core_infrastructure.scheduler.news_archive import get_news_archive

        archive = get_news_archive()
        archive.add_articles(request.articles, source=request.source)
        return {"status": "ok", "archived": len(request.articles)}
    except Exception as e:
        logger.error(f"Failed to archive articles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_archive():
    """Clear all articles from the archive."""
    try:
        from common_lib.modules.core_infrastructure.scheduler.news_archive import get_news_archive

        archive = get_news_archive()
        archive.save_all([])
        return {"status": "ok", "message": "Archive cleared"}
    except Exception as e:
        logger.error(f"Failed to clear archive: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/post/{post_id}")
async def get_post_details(post_id: str, subreddit: Optional[str] = Query(None)):
    """Fetch full post details including body and comments."""
    try:
        from common_lib.plugins.web_scraper.spiders.reddit import RedditSpider
        from common_lib.plugins.web_scraper.core.engine import ScraperCore

        core = ScraperCore()
        spider = RedditSpider(core.get_fetcher())

        url = (
            f"https://www.reddit.com/r/{subreddit}/comments/{post_id}"
            if subreddit
            else f"https://www.reddit.com/comments/{post_id}"
        )
        details = spider.fetch_post_details(url)

        if details.get("success"):
            return {"status": "ok", "post": details}
        else:
            raise HTTPException(
                status_code=404, detail=details.get("error", "Post not found")
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch post details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
