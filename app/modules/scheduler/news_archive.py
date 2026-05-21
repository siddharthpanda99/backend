"""SD News Archive API.

Stores and retrieves SD News articles fetched by the scheduler cron job.
Articles are persisted so they can be browsed, searched, and filtered
in the dedicated SD News UI page.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_ARCHIVE_PATH = (
    Path(__file__).parent.parent.parent.parent.parent / "sd_news_archive.json"
)


class NewsArchive:
    """Persistent JSON archive for SD News articles."""

    def __init__(self, archive_path: Optional[Path] = None):
        self._path = archive_path or DEFAULT_ARCHIVE_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._max_articles = 5000

    def load_all(self) -> List[Dict[str, Any]]:
        """Load all articles from archive."""
        if not self._path.exists():
            return []
        try:
            with open(self._path, "r") as f:
                data = json.load(f)
            return data.get("articles", [])
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load news archive: {e}")
            return []

    def save_all(self, articles: List[Dict[str, Any]]):
        """Save all articles to archive."""
        try:
            with open(self._path, "w") as f:
                json.dump({"articles": articles}, f, indent=2, default=str)
        except IOError as e:
            logger.error(f"Failed to save news archive: {e}")

    def add_articles(self, articles: List[Dict[str, Any]], source: str = "reddit"):
        """Add new articles, deduplicating by URL."""
        existing = self.load_all()
        existing_urls = {a.get("url", "") for a in existing}

        new_count = 0
        for article in articles:
            url = article.get("url", "")
            if url and url not in existing_urls:
                article["archived_at"] = time.time()
                article["source"] = source
                existing.append(article)
                existing_urls.add(url)
                new_count += 1

        # Trim to max
        if len(existing) > self._max_articles:
            existing = existing[-self._max_articles :]

        self.save_all(existing)
        logger.info(f"Archived {new_count} new articles (total: {len(existing)})")

    def search(
        self,
        query: Optional[str] = None,
        subreddit: Optional[str] = None,
        min_score: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "score",
    ) -> Dict[str, Any]:
        """Search and filter articles."""
        articles = self.load_all()

        if query:
            q = query.lower()
            articles = [
                a
                for a in articles
                if q in (a.get("title") or "").lower()
                or q in (a.get("body") or "").lower()
                or q in (a.get("author") or "").lower()
            ]

        if subreddit:
            sub = subreddit.lower()
            articles = [
                a
                for a in articles
                if sub
                in (a.get("source_subreddit") or a.get("subreddit") or "").lower()
            ]

        if min_score is not None:
            articles = [a for a in articles if (a.get("score") or 0) >= min_score]

        # Sort
        reverse = sort_by in ("score", "comments_count", "archived_at", "fetched_at")
        sort_key = (
            sort_by
            if sort_by in ("score", "comments_count", "archived_at", "fetched_at")
            else "fetched_at"
        )
        articles.sort(key=lambda a: a.get(sort_key, 0) or 0, reverse=reverse)

        total = len(articles)
        paginated = articles[offset : offset + limit]

        return {
            "articles": paginated,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get archive statistics."""
        articles = self.load_all()
        subreddits = {}
        for a in articles:
            sub = a.get("source_subreddit") or a.get("subreddit") or "unknown"
            subreddits[sub] = subreddits.get(sub, 0) + 1

        scores = [a.get("score", 0) for a in articles if a.get("score")]
        return {
            "total_articles": len(articles),
            "subreddits": subreddits,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "max_score": max(scores) if scores else 0,
            "total_comments": sum(a.get("comments_count", 0) for a in articles),
        }


_archive: Optional[NewsArchive] = None


def get_news_archive() -> NewsArchive:
    """Get or create the global news archive."""
    global _archive
    if _archive is None:
        _archive = NewsArchive()
    return _archive
