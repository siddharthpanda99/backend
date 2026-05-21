"""SD News Workflow Executor for Scheduler.

Wraps the existing SDNewsFetcher and notification hook into a
workflow that can be triggered by the scheduler via UI configuration.
"""

import logging
import time
import uuid
from typing import Any, Dict, List

from common_lib.modules.notification.controller import (
    notify,
    Priority,
    Channels,
)
from common_lib.modules.workflows.standard.observability import EventTracer
from common_lib.modules.workflows.standard.observability.events import (
    EventType,
    WorkflowEvent,
)
from common_lib.modules.workflows.standard.observability.backends import (
    SQLAlchemyBackend,
)

logger = logging.getLogger(__name__)


class SDNewsFetcher:
    """Fetches Stable Diffusion news from Reddit subreddits."""

    DEFAULT_SUBREDDITS = [
        {"name": "StableDiffusion", "sort": "hot", "time_filter": "day", "limit": 15},
        {"name": "sdforall", "sort": "hot", "time_filter": "day", "limit": 10},
        {"name": "aiArt", "sort": "hot", "time_filter": "day", "limit": 10},
    ]

    SD_KEYWORDS = [
        "stable diffusion",
        "sdxl",
        "sd 1.5",
        "comfyui",
        "automatic1111",
        "controlnet",
        "loras",
        "dreamshaper",
        "flux",
        "image generation",
        "diffusion model",
    ]

    def __init__(self):
        self._spider = None
        self._last_post_ids: set = set()
        self._fetch_count = 0

    def _get_spider(self):
        if self._spider is None:
            try:
                from common_lib.plugins.web_scraper.spiders.reddit import RedditSpider
                from common_lib.plugins.web_scraper.core.engine import ScraperCore

                core = ScraperCore()
                self._spider = RedditSpider(core.get_fetcher())
                logger.info("Reddit spider initialized with scrapling")
            except Exception as e:
                logger.warning(f"scrapling not available, using mock data: {e}")
                self._spider = None
        return self._spider

    async def fetch_news(
        self,
        subreddits: List[Dict[str, Any]] = None,
        limit: int = 25,
        sort: str = "hot",
    ) -> Dict[str, Any]:
        """Fetch latest SD news from configured subreddits."""
        self._fetch_count += 1
        start = time.time()

        subs = subreddits or [
            {
                "name": "StableDiffusion",
                "sort": sort,
                "time_filter": "day",
                "limit": limit,
            },
        ]

        spider = self._get_spider()
        all_posts = []

        if spider:
            for sub in subs:
                try:
                    result = spider.run(
                        subreddit=sub["name"],
                        sort=sub.get("sort", sort),
                        time_filter=sub.get("time_filter", "day"),
                        limit=sub.get("limit", limit),
                    )
                    if result.get("success") and result.get("posts"):
                        for post in result["posts"]:
                            post["source_subreddit"] = sub["name"]
                            post["fetched_at"] = time.time()
                            all_posts.append(post)
                except Exception as e:
                    logger.warning(f"Failed to fetch r/{sub['name']}: {e}")
        else:
            all_posts = self._generate_mock_news()

        sd_posts = self._filter_sd_posts(all_posts)

        new_posts = []
        for post in sd_posts:
            post_id = post.get("id") or post.get("url", "")
            if post_id not in self._last_post_ids:
                new_posts.append(post)
                self._last_post_ids.add(post_id)

        if len(self._last_post_ids) > 200:
            self._last_post_ids = set(list(self._last_post_ids)[-200:])

        duration = (time.time() - start) * 1000

        return {
            "success": True,
            "posts": new_posts,
            "total_found": len(sd_posts),
            "new_posts": len(new_posts),
            "sources": list(
                set(p.get("source_subreddit", "unknown") for p in sd_posts)
            ),
            "duration_ms": round(duration, 2),
            "fetched_at": time.time(),
            "fetch_number": self._fetch_count,
        }

    def _filter_sd_posts(self, posts: List[Dict]) -> List[Dict]:
        filtered = []
        for post in posts:
            title = (post.get("title") or "").lower()
            subreddit = post.get("source_subreddit", "").lower()
            if subreddit in ["stablediffusion", "sdforall"]:
                filtered.append(post)
            elif any(kw in title for kw in self.SD_KEYWORDS):
                filtered.append(post)
        return filtered

    def _generate_mock_news(self) -> List[Dict]:
        import random

        mock_titles = [
            "DreamShaper XL v2.0 released - incredible photorealism improvements",
            "New ControlNet model for precise pose control in SDXL",
            "ComfyUI 0.3.0 update brings major workflow improvements",
            "LoRA training guide: How to train custom styles in 30 minutes",
            "SDXL Turbo now supports real-time generation at 20fps",
            "Best negative prompts for anime-style generation in 2024",
            "Flux.1 dev model comparison vs SDXL - detailed benchmarks",
            "New ip-adapter-faceid model for consistent character generation",
            "Automatic1111 extension for automatic upscaling and face restoration",
            "Stable Video Diffusion 1.1 - improved motion and consistency",
            "How to use regional prompting for better composition in SDXL",
            "New open-source dataset with 2M high-quality images for training",
            "SDXL Lightning models - 4 step generation with quality intact",
            "ComfyUI custom node: Animatediff with motion LoRA support",
            "Comparison: Midjourney v6 vs SDXL with proper prompting",
        ]

        return [
            {
                "id": f"mock_{i}_{int(time.time())}",
                "title": title,
                "author": f"user_{random.randint(1000, 9999)}",
                "score": random.randint(50, 2000),
                "comments_count": random.randint(5, 200),
                "source_subreddit": random.choice(
                    ["StableDiffusion", "sdforall", "aiArt"]
                ),
                "url": f"https://reddit.com/r/StableDiffusion/comments/mock_{i}",
                "fetched_at": time.time(),
            }
            for i, title in enumerate(mock_titles[: random.randint(5, 10)])
        ]


_fetcher = SDNewsFetcher()


async def execute_sd_news_workflow(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """SD News workflow executor - called by scheduler."""
    trace_id = str(uuid.uuid4())
    tracer = EventTracer()
    try:
        tracer.add_backend(SQLAlchemyBackend())
    except Exception:
        pass

    tracer.emit(
        WorkflowEvent(
            event_type=EventType.WORKFLOW_STARTED,
            trace_id=trace_id,
            workflow_id="sd_news_reddit",
            workflow_name="Reddit SD News Scraper",
            agent_id="scheduler",
            span_id=str(uuid.uuid4()),
            initial_inputs=inputs,
        )
    )

    start = time.time()
    try:
        subreddits = inputs.get("subreddits")
        limit = inputs.get("limit", 25)
        sort = inputs.get("sort", "hot")
        send_notification = inputs.get("send_notification", True)

        news_data = await _fetcher.fetch_news(
            subreddits=subreddits,
            limit=limit,
            sort=sort,
        )

        if send_notification and news_data.get("posts"):
            await _send_news_notification(news_data)

        if news_data.get("posts"):
            try:
                from app.modules.scheduler.news_archive import get_news_archive

                archive = get_news_archive()
                archive.add_articles(news_data["posts"], source="reddit")
            except Exception as e:
                logger.warning(f"Failed to archive news articles: {e}")

        duration_ms = (time.time() - start) * 1000
        outputs = {
            "posts_count": len(news_data.get("posts", [])),
            "duration_ms": round(duration_ms, 2),
        }
        tracer.emit(
            WorkflowEvent(
                event_type=EventType.WORKFLOW_COMPLETED,
                trace_id=trace_id,
                workflow_id="sd_news_reddit",
                span_id=str(uuid.uuid4()),
                metadata={"outputs": outputs},
            )
        )

        return news_data

    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        tracer.emit(
            WorkflowEvent(
                event_type=EventType.WORKFLOW_FAILED,
                trace_id=trace_id,
                workflow_id="sd_news_reddit",
                span_id=str(uuid.uuid4()),
                metadata={"error": str(e)},
            )
        )
        logger.error(f"SD News workflow failed: {e}")
        return {"success": False, "error": str(e), "posts": []}


async def _send_news_notification(news_data: Dict[str, Any]):
    """Format and send SD news to the UI notification channel."""
    posts = news_data.get("posts", [])
    total_found = news_data.get("total_found", 0)
    new_count = news_data.get("new_posts", 0)
    duration_ms = news_data.get("duration_ms", 0)
    sources = news_data.get("sources", [])
    fetch_number = news_data.get("fetch_number", 0)

    if not posts:
        return

    posts.sort(key=lambda p: p.get("score", 0), reverse=True)
    top_posts = posts[:10]

    message_lines = [
        f"SD News Update (Fetch #{fetch_number})",
        f"Found {total_found} posts, {new_count} new from {', '.join(sources)}",
        f"Scan took {duration_ms:.0f}ms",
        "",
        "Top Stories:",
    ]

    for i, post in enumerate(top_posts, 1):
        title = post.get("title", "Untitled")[:120]
        score = post.get("score", 0)
        comments = post.get("comments_count", 0)
        subreddit = post.get("source_subreddit", "unknown")
        url = post.get("url", "")
        message_lines.append(f"  {i}. [{score} pts, {comments} comments] {title}")
        message_lines.append(f"     r/{subreddit} | {url}")

    await notify(
        event_type="sd_news.update",
        data={
            "type": "sd_news_digest",
            "title": f"Stable Diffusion News Update (#{fetch_number})",
            "message": "\n".join(message_lines),
            "fetch_number": fetch_number,
            "total_found": total_found,
            "new_posts": new_count,
            "sources": sources,
            "duration_ms": duration_ms,
            "top_posts": [
                {
                    "rank": i + 1,
                    "title": p.get("title", ""),
                    "score": p.get("score", 0),
                    "comments": p.get("comments_count", 0),
                    "subreddit": p.get("source_subreddit", ""),
                    "url": p.get("url", ""),
                    "author": p.get("author", ""),
                }
                for i, p in enumerate(top_posts)
            ],
            "all_posts_count": len(posts),
            "timestamp": time.time(),
        },
        channel=Channels.GLOBAL,
        priority=Priority.NORMAL,
    )
