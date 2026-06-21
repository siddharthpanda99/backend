"""Tests for the SD News archive and news routes."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from common_lib.modules.scheduler.news_archive import (
    NewsArchive,
    get_news_archive,
    _archive,
)
from app.modules.scheduler.routes.news_routes import router as news_router


@pytest.fixture(autouse=True)
def reset_archive():
    """Reset the news archive singleton."""
    global _archive
    _archive = None
    yield
    _archive = None


@pytest.fixture
def temp_archive():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield NewsArchive(Path(tmpdir) / "test_archive.json")


@pytest.fixture
def sample_articles():
    return [
        {
            "id": "abc123",
            "title": "Test SD Post 1",
            "url": "https://reddit.com/r/StableDiffusion/comments/abc123/test",
            "author": "user1",
            "score": 150,
            "comments_count": 25,
            "source_subreddit": "StableDiffusion",
            "fetched_at": 1700000000,
        },
        {
            "id": "def456",
            "title": "Another SD Post",
            "url": "https://reddit.com/r/sdforall/comments/def456/another",
            "author": "user2",
            "score": 50,
            "comments_count": 10,
            "source_subreddit": "sdforall",
            "fetched_at": 1700000100,
        },
        {
            "id": "ghi789",
            "title": "Low score post",
            "url": "https://reddit.com/r/aiArt/comments/ghi789/low",
            "author": "user3",
            "score": 5,
            "comments_count": 2,
            "source_subreddit": "aiArt",
            "fetched_at": 1700000200,
        },
    ]


# =============================================================================
# News Archive Tests
# =============================================================================


class TestNewsArchive:
    def test_load_empty(self, temp_archive):
        assert temp_archive.load_all() == []

    def test_add_articles(self, temp_archive, sample_articles):
        temp_archive.add_articles(sample_articles)
        loaded = temp_archive.load_all()
        assert len(loaded) == 3

    def test_deduplication(self, temp_archive, sample_articles):
        temp_archive.add_articles(sample_articles)
        temp_archive.add_articles(sample_articles)
        loaded = temp_archive.load_all()
        assert len(loaded) == 3

    def test_search_by_query(self, temp_archive, sample_articles):
        temp_archive.add_articles(sample_articles)
        result = temp_archive.search(query="Test SD")
        assert result["total"] == 1
        assert result["articles"][0]["title"] == "Test SD Post 1"

    def test_search_by_subreddit(self, temp_archive, sample_articles):
        temp_archive.add_articles(sample_articles)
        result = temp_archive.search(subreddit="sdforall")
        assert result["total"] == 1
        assert result["articles"][0]["source_subreddit"] == "sdforall"

    def test_search_by_min_score(self, temp_archive, sample_articles):
        temp_archive.add_articles(sample_articles)
        result = temp_archive.search(min_score=100)
        assert result["total"] == 1
        assert result["articles"][0]["score"] == 150

    def test_search_sort_by_score(self, temp_archive, sample_articles):
        temp_archive.add_articles(sample_articles)
        result = temp_archive.search(sort_by="score")
        assert result["articles"][0]["score"] == 150
        assert result["articles"][-1]["score"] == 5

    def test_search_sort_by_comments(self, temp_archive, sample_articles):
        temp_archive.add_articles(sample_articles)
        result = temp_archive.search(sort_by="comments_count")
        assert result["articles"][0]["comments_count"] == 25

    def test_search_pagination(self, temp_archive, sample_articles):
        temp_archive.add_articles(sample_articles)
        result = temp_archive.search(limit=2, offset=0)
        assert len(result["articles"]) == 2
        assert result["total"] == 3

    def test_get_stats(self, temp_archive, sample_articles):
        temp_archive.add_articles(sample_articles)
        stats = temp_archive.get_stats()
        assert stats["total_articles"] == 3
        assert stats["avg_score"] == pytest.approx(68.3, abs=0.5)
        assert stats["max_score"] == 150
        assert stats["total_comments"] == 37

    def test_max_articles_trim(self, temp_archive):
        archive = NewsArchive(Path(temp_archive._path.parent) / "trim_test.json")
        archive._max_articles = 5
        articles = [
            {
                "id": str(i),
                "url": f"http://test.com/{i}",
                "title": f"Post {i}",
                "score": i,
            }
            for i in range(10)
        ]
        archive.add_articles(articles)
        loaded = archive.load_all()
        assert len(loaded) == 5


# =============================================================================
# News API Tests
# =============================================================================


class TestNewsAPI:
    @pytest.fixture
    def app(self, temp_archive, sample_articles):
        app = FastAPI()
        app.include_router(news_router)

        import common_lib.modules.scheduler.news_archive as na

        na._archive = temp_archive
        temp_archive.add_articles(sample_articles)

        yield app
        na._archive = None

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_list_articles(self, client):
        resp = client.get("/sd-news/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["total"] == 3

    def test_search_articles(self, client):
        resp = client.get("/sd-news/articles?query=Test+SD")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_filter_by_subreddit(self, client):
        resp = client.get("/sd-news/articles?subreddit=aiArt")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_filter_by_min_score(self, client):
        resp = client.get("/sd-news/articles?min_score=100")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_sort_by_score(self, client):
        resp = client.get("/sd-news/articles?sort_by=score")
        assert resp.status_code == 200
        data = resp.json()
        assert data["articles"][0]["score"] == 150

    def test_pagination(self, client):
        resp = client.get("/sd-news/articles?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["articles"]) == 2
        assert data["total"] == 3

    def test_stats(self, client):
        resp = client.get("/sd-news/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stats"]["total_articles"] == 3

    def test_archive_articles(self, client):
        resp = client.post(
            "/sd-news/archive",
            json={
                "articles": [
                    {
                        "id": "new1",
                        "url": "http://test.com/new1",
                        "title": "New Post",
                        "score": 10,
                    }
                ],
                "source": "reddit",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["archived"] == 1

    def test_clear_archive(self, client):
        resp = client.delete("/sd-news/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Archive cleared"

        resp = client.get("/sd-news/articles")
        assert resp.json()["total"] == 0
