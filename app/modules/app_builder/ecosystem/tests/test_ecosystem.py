"""
Ecosystem API — Comprehensive CRUD Tests

Tests all 7 route modules via FastAPI TestClient:
- Apps CRUD
- Social Posts CRUD + like/pin
- Blog Articles CRUD + featured/category
- Reviews CRUD + stats + helpful
- Walkthroughs CRUD + nested steps + complete
- Data Sources CRUD + connect/disconnect
- Settings GET/PUT + auto-create defaults

Follows the governance module test pattern with sequential numbered tests.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

PREFIX = "/api/v1/ecosystem"


# ─── Helpers ────────────────────────────────────────────────────────

TEST_APP_ID = "test-app-001"


# ═══════════════════════════════════════════════════════════════════
# 1. Apps CRUD
# ═══════════════════════════════════════════════════════════════════

class TestApps:
    """CRUD tests for /apps endpoints."""

    def test_01_list_apps_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["apps"] == []

    def test_02_create_app(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/",
            json={
                "id": TEST_APP_ID,
                "name": "Test App",
                "description": "An app for testing",
                "icon": "🧪",
                "category": "testing",
                "platform": ["Web", "iOS"],
                "author": "Tester",
                "status": "active",
                "stats": {"users": 10, "pages": 3, "components": 15, "sections": 5},
            },
        )
        assert resp.status_code == 201
        d = resp.json()
        assert d["status"] == "success"
        assert d["data"]["id"] == TEST_APP_ID
        assert d["data"]["name"] == "Test App"
        assert d["data"]["category"] == "testing"
        assert d["data"]["status"] == "active"
        assert d["data"]["stats"]["users"] == 10
        assert d["data"]["stats"]["pages"] == 3

    def test_03_create_duplicate_app(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/",
            json={"id": TEST_APP_ID, "name": "Duplicate"},
        )
        assert resp.status_code == 409

    def test_04_get_app(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}")
        assert resp.status_code == 200
        d = resp.json()
        assert d["id"] == TEST_APP_ID
        assert d["name"] == "Test App"
        assert d["platform"] == ["Web", "iOS"]

    def test_05_get_nonexistent_app(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/nonexistent-app")
        assert resp.status_code == 404

    def test_06_list_apps_after_create(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["active"] >= 1
        app_ids = [a["id"] for a in data["apps"]]
        assert TEST_APP_ID in app_ids

    def test_07_list_apps_with_filters(self, client: TestClient) -> None:
        # Filter by category
        resp = client.get(f"{PREFIX}/apps/?category=testing")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

        # Filter by status
        resp = client.get(f"{PREFIX}/apps/?status=active")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

        # Search by name
        resp = client.get(f"{PREFIX}/apps/?search=Test")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

        # No match search
        resp = client.get(f"{PREFIX}/apps/?search=zzz_nonexistent")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_08_update_app(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/apps/{TEST_APP_ID}",
            json={"name": "Updated App", "status": "draft"},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["data"]["name"] == "Updated App"
        assert d["data"]["status"] == "draft"

    def test_09_update_nonexistent_app(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/apps/nonexistent",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404

    def test_10_delete_nonexistent_app(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/apps/nonexistent")
        assert resp.status_code == 404

    def test_11_delete_app(self, client: TestClient) -> None:
        resp = client.delete(f"{PREFIX}/apps/{TEST_APP_ID}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_12_get_deleted_app(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 2. Social Posts CRUD + Like + Pin
# ═══════════════════════════════════════════════════════════════════

class TestSocialPosts:
    """CRUD tests for /apps/{app_id}/social endpoints."""

    POST_ID: str | None = None

    def test_20_create_app_for_social(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/",
            json={"id": TEST_APP_ID, "name": "Social Test App"},
        )
        assert resp.status_code == 201

    def test_21_list_posts_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/social/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []

    def test_22_list_posts_for_nonexistent_app(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/no-such-app/social/")
        assert resp.status_code == 404

    def test_23_create_post(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/social/",
            json={
                "author": "Alice",
                "avatar": "https://example.com/avatar.png",
                "content": "Hello from the ecosystem!",
                "tags": ["hello", "ecosystem"],
                "pinned": True,
            },
        )
        assert resp.status_code == 201
        d = resp.json()
        assert d["status"] == "success"
        assert d["data"]["author"] == "Alice"
        assert d["data"]["content"] == "Hello from the ecosystem!"
        assert d["data"]["pinned"] is True
        assert d["data"]["tags"] == ["hello", "ecosystem"]
        TestSocialPosts.POST_ID = d["data"]["id"]

    def test_24_create_post_no_app(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/no-such-app/social/",
            json={"author": "Bob", "content": "Ghost post"},
        )
        assert resp.status_code == 404

    def test_25_list_posts_after_create(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/social/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_26_like_post(self, client: TestClient) -> None:
        assert TestSocialPosts.POST_ID is not None
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/social/{TestSocialPosts.POST_ID}/like"
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["likes"] == 1

        # Like again — should increment
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/social/{TestSocialPosts.POST_ID}/like"
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["likes"] == 2

    def test_27_like_nonexistent_post(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/social/no-such-post/like"
        )
        assert resp.status_code == 404

    def test_28_update_post(self, client: TestClient) -> None:
        assert TestSocialPosts.POST_ID is not None
        resp = client.patch(
            f"{PREFIX}/apps/{TEST_APP_ID}/social/{TestSocialPosts.POST_ID}",
            json={"content": "Updated content", "pinned": False},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["data"]["content"] == "Updated content"
        assert d["data"]["pinned"] is False

    def test_29_delete_post(self, client: TestClient) -> None:
        assert TestSocialPosts.POST_ID is not None
        resp = client.delete(
            f"{PREFIX}/apps/{TEST_APP_ID}/social/{TestSocialPosts.POST_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_30_delete_nonexistent_post(self, client: TestClient) -> None:
        resp = client.delete(
            f"{PREFIX}/apps/{TEST_APP_ID}/social/no-such-post"
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 3. Blog Articles CRUD
# ═══════════════════════════════════════════════════════════════════

class TestBlogArticles:
    """CRUD tests for /apps/{app_id}/blogs endpoints."""

    ARTICLE_ID: str | None = None

    def test_40_list_articles_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/blogs/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_41_create_article(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/blogs/",
            json={
                "title": "Getting Started",
                "summary": "A guide to getting started",
                "content": "Full article content here...",
                "author": "Alice",
                "avatar": "https://example.com/alice.png",
                "readTime": 8,
                "tags": ["guide", "beginner"],
                "featured": True,
                "category": "guide",
            },
        )
        assert resp.status_code == 201
        d = resp.json()
        assert d["status"] == "success"
        assert d["data"]["title"] == "Getting Started"
        assert d["data"]["category"] == "guide"
        assert d["data"]["featured"] is True
        assert d["data"]["readTime"] == 8
        TestBlogArticles.ARTICLE_ID = d["data"]["id"]

    def test_42_create_article_no_app(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/no-such-app/blogs/",
            json={"title": "Ghost", "summary": "", "author": "Bob"},
        )
        assert resp.status_code == 404

    def test_43_list_articles_after_create(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/blogs/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_44_list_articles_filter_by_category(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/blogs/?category=guide")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/blogs/?category=tutorial")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_45_list_articles_featured_only(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/blogs/?featured_only=true")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_46_update_article(self, client: TestClient) -> None:
        assert TestBlogArticles.ARTICLE_ID is not None
        resp = client.patch(
            f"{PREFIX}/apps/{TEST_APP_ID}/blogs/{TestBlogArticles.ARTICLE_ID}",
            json={"title": "Updated Title", "featured": False},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["data"]["title"] == "Updated Title"
        assert d["data"]["featured"] is False

    def test_47_delete_article(self, client: TestClient) -> None:
        assert TestBlogArticles.ARTICLE_ID is not None
        resp = client.delete(
            f"{PREFIX}/apps/{TEST_APP_ID}/blogs/{TestBlogArticles.ARTICLE_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


# ═══════════════════════════════════════════════════════════════════
# 4. Reviews CRUD + Stats + Helpful
# ═══════════════════════════════════════════════════════════════════

class TestReviews:
    """CRUD tests for /apps/{app_id}/reviews endpoints."""

    REVIEW_ID: str | None = None

    def test_50_list_reviews_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/reviews/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_51_create_review(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/reviews/",
            json={
                "author": "Bob",
                "rating": 4,
                "title": "Great app!",
                "content": "Really enjoying the features.",
                "version": "1.0.0",
            },
        )
        assert resp.status_code == 201
        d = resp.json()
        assert d["status"] == "success"
        assert d["data"]["rating"] == 4
        assert d["data"]["author"] == "Bob"
        assert d["data"]["helpful"] == 0
        TestReviews.REVIEW_ID = d["data"]["id"]

    def test_52_create_review_invalid_rating(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/reviews/",
            json={"author": "Bob", "rating": 6, "title": "Bad", "content": "..."},
        )
        assert resp.status_code == 422

        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/reviews/",
            json={"author": "Bob", "rating": 0, "title": "Bad", "content": "..."},
        )
        assert resp.status_code == 422

    def test_53_create_review_no_app(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/no-such-app/reviews/",
            json={"author": "Bob", "rating": 3, "title": "X", "content": "Y"},
        )
        assert resp.status_code == 404

    def test_54_list_reviews_after_create(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/reviews/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        assert data["items"][0]["rating"] == 4

    def test_55_get_review_stats(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/reviews/stats")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1
        assert data["average"] > 0
        assert "4" in data["distribution"]

    def test_56_review_stats_empty_app(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/reviews/stats")
        assert resp.status_code == 200
        # Now has at least 1 review from test_51

    def test_57_mark_helpful(self, client: TestClient) -> None:
        assert TestReviews.REVIEW_ID is not None
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/reviews/{TestReviews.REVIEW_ID}/helpful"
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["helpful"] == 1

    def test_58_mark_helpful_nonexistent(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/reviews/no-such-review/helpful"
        )
        assert resp.status_code == 404

    def test_59_delete_review(self, client: TestClient) -> None:
        assert TestReviews.REVIEW_ID is not None
        resp = client.delete(
            f"{PREFIX}/apps/{TEST_APP_ID}/reviews/{TestReviews.REVIEW_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_60_delete_nonexistent_review(self, client: TestClient) -> None:
        resp = client.delete(
            f"{PREFIX}/apps/{TEST_APP_ID}/reviews/no-such-review"
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 5. Walkthroughs CRUD + Steps + Complete
# ═══════════════════════════════════════════════════════════════════

class TestWalkthroughs:
    """CRUD tests for /apps/{app_id}/walkthroughs endpoints."""

    WALKTHROUGH_ID: str | None = None

    def test_70_list_walkthroughs_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_71_create_walkthrough(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/",
            json={
                "title": "How to Use the App",
                "summary": "A step-by-step guide",
                "difficulty": "beginner",
                "duration": "10 min",
                "author": "Charlie",
                "tags": ["guide", "onboarding"],
                "steps": [
                    {
                        "title": "Step 1",
                        "description": "Open the app",
                        "image": None,
                        "code": None,
                        "tip": "Make sure you have an internet connection",
                    },
                    {
                        "title": "Step 2",
                        "description": "Click the button",
                        "image": "https://example.com/step2.png",
                        "code": "console.log('hello')",
                        "tip": None,
                    },
                ],
            },
        )
        assert resp.status_code == 201
        d = resp.json()
        assert d["status"] == "success"
        assert d["data"]["title"] == "How to Use the App"
        assert len(d["data"]["steps"]) == 2
        assert d["data"]["steps"][0]["title"] == "Step 1"
        assert d["data"]["steps"][0]["tip"] == "Make sure you have an internet connection"
        assert d["data"]["steps"][1]["code"] == "console.log('hello')"
        TestWalkthroughs.WALKTHROUGH_ID = d["data"]["id"]

    def test_72_get_walkthrough(self, client: TestClient) -> None:
        assert TestWalkthroughs.WALKTHROUGH_ID is not None
        resp = client.get(
            f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/{TestWalkthroughs.WALKTHROUGH_ID}"
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["id"] == TestWalkthroughs.WALKTHROUGH_ID
        assert len(d["steps"]) == 2

    def test_73_get_nonexistent_walkthrough(self, client: TestClient) -> None:
        resp = client.get(
            f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/no-such-wt"
        )
        assert resp.status_code == 404

    def test_74_list_walkthroughs_after_create(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        assert data["items"][0]["title"] == "How to Use the App"

    def test_75_complete_walkthrough(self, client: TestClient) -> None:
        assert TestWalkthroughs.WALKTHROUGH_ID is not None
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/{TestWalkthroughs.WALKTHROUGH_ID}/complete"
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["completions"] == 1

        # Complete again
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/{TestWalkthroughs.WALKTHROUGH_ID}/complete"
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["completions"] == 2

    def test_76_update_walkthrough_replace_steps(self, client: TestClient) -> None:
        assert TestWalkthroughs.WALKTHROUGH_ID is not None
        resp = client.put(
            f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/{TestWalkthroughs.WALKTHROUGH_ID}",
            json={
                "title": "Updated Walkthrough",
                "difficulty": "intermediate",
                "steps": [
                    {
                        "title": "New Step 1",
                        "description": "The only step now",
                    },
                ],
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["data"]["title"] == "Updated Walkthrough"
        assert d["data"]["difficulty"] == "intermediate"
        assert len(d["data"]["steps"]) == 1
        assert d["data"]["steps"][0]["title"] == "New Step 1"

    def test_77_delete_walkthrough(self, client: TestClient) -> None:
        assert TestWalkthroughs.WALKTHROUGH_ID is not None
        resp = client.delete(
            f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/{TestWalkthroughs.WALKTHROUGH_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_78_delete_nonexistent_walkthrough(self, client: TestClient) -> None:
        resp = client.delete(
            f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/no-such-wt"
        )
        assert resp.status_code == 404

    def test_79_get_deleted_walkthrough(self, client: TestClient) -> None:
        assert TestWalkthroughs.WALKTHROUGH_ID is not None
        resp = client.get(
            f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/{TestWalkthroughs.WALKTHROUGH_ID}"
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 6. Data Sources CRUD + Connect/Disconnect
# ═══════════════════════════════════════════════════════════════════

class TestDataSources:
    """CRUD tests for /apps/{app_id}/data endpoints."""

    SOURCE_ID: str | None = None

    def test_90_list_data_sources_empty(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/data/")
        assert resp.status_code == 200
        d = resp.json()
        assert d["status"] == "success"
        assert d["data"]["sources"] == []

    def test_91_create_data_source(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/data/",
            json={
                "name": "Users API",
                "type": "rest",
                "endpoint": "https://api.example.com/users",
                "description": "User data endpoint",
                "recordCount": 0,
            },
        )
        assert resp.status_code == 201
        d = resp.json()
        assert d["status"] == "success"
        assert d["data"]["name"] == "Users API"
        assert d["data"]["type"] == "rest"
        assert d["data"]["status"] == "disconnected"
        assert d["data"]["lastSync"] == "Never"
        TestDataSources.SOURCE_ID = d["data"]["id"]

    def test_92_list_data_sources_after_create(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/data/")
        assert resp.status_code == 200
        sources = resp.json()["data"]["sources"]
        assert len(sources) >= 1
        names = [s["name"] for s in sources]
        assert "Users API" in names

    def test_93_connect_data_source(self, client: TestClient) -> None:
        assert TestDataSources.SOURCE_ID is not None
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/data/{TestDataSources.SOURCE_ID}/connect"
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["data"]["status"] == "connected"
        assert d["data"]["lastSync"] != "Never"

    def test_94_connect_nonexistent_source(self, client: TestClient) -> None:
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/data/no-such-source/connect"
        )
        assert resp.status_code == 404

    def test_95_disconnect_data_source(self, client: TestClient) -> None:
        assert TestDataSources.SOURCE_ID is not None
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/data/{TestDataSources.SOURCE_ID}/disconnect"
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "disconnected"

    def test_96_update_data_source(self, client: TestClient) -> None:
        assert TestDataSources.SOURCE_ID is not None
        resp = client.patch(
            f"{PREFIX}/apps/{TEST_APP_ID}/data/{TestDataSources.SOURCE_ID}",
            json={
                "name": "Updated Users API",
                "recordCount": 150,
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["data"]["name"] == "Updated Users API"
        assert d["data"]["recordCount"] == 150

    def test_97_delete_data_source(self, client: TestClient) -> None:
        assert TestDataSources.SOURCE_ID is not None
        resp = client.delete(
            f"{PREFIX}/apps/{TEST_APP_ID}/data/{TestDataSources.SOURCE_ID}"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_98_delete_nonexistent_data_source(self, client: TestClient) -> None:
        resp = client.delete(
            f"{PREFIX}/apps/{TEST_APP_ID}/data/no-such-source"
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 7. App Settings GET/PUT + Auto-Create Defaults
# ═══════════════════════════════════════════════════════════════════

class TestAppSettings:
    """Tests for /apps/{app_id}/settings endpoints."""

    def test_100_get_settings_auto_creates_defaults(self, client: TestClient) -> None:
        """GET on a new app auto-creates default settings."""
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/settings/")
        assert resp.status_code == 200
        d = resp.json()
        assert d["status"] == "success"
        data = d["data"]
        assert data["navigation"] == "bottom-tabs"
        assert data["auth"] == "jwt"
        assert data["dataRetention"] == 90
        assert data["autoSave"] is True
        assert data["analytics"] is True
        # Theme defaults
        assert data["theme"]["primaryColor"] == "#0ea5e9"
        assert data["theme"]["accentColor"] == "#2563eb"
        assert data["theme"]["darkMode"] is True
        assert data["theme"]["borderRadius"] == 8
        # Platform defaults
        assert data["platform"]["web"] is True
        assert data["platform"]["ios"] is False
        assert data["platform"]["android"] is False

    def test_101_get_settings_nonexistent_app(self, client: TestClient) -> None:
        resp = client.get(f"{PREFIX}/apps/no-such-app/settings/")
        assert resp.status_code == 404

    def test_102_update_settings(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/apps/{TEST_APP_ID}/settings/",
            json={
                "theme": {
                    "primaryColor": "#ff0000",
                    "darkMode": False,
                    "borderRadius": 12,
                },
                "platform": {
                    "ios": True,
                    "android": True,
                },
                "navigation": "sidebar",
                "dataRetention": 180,
                "autoSave": False,
            },
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["status"] == "success"
        data = d["data"]
        # Check theme updates
        assert data["theme"]["primaryColor"] == "#ff0000"
        assert data["theme"]["darkMode"] is False
        assert data["theme"]["borderRadius"] == 12
        # Check platform updates
        assert data["platform"]["ios"] is True
        assert data["platform"]["android"] is True
        assert data["platform"]["web"] is True  # unchanged
        # Check scalar updates
        assert data["navigation"] == "sidebar"
        assert data["dataRetention"] == 180
        assert data["autoSave"] is False
        # Check unchanged defaults
        assert data["auth"] == "jwt"
        assert data["analytics"] is True

    def test_103_verify_settings_persist(self, client: TestClient) -> None:
        """GET after update returns the updated values."""
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/settings/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["theme"]["primaryColor"] == "#ff0000"
        assert data["navigation"] == "sidebar"

    def test_104_update_settings_nonexistent_app(self, client: TestClient) -> None:
        resp = client.put(
            f"{PREFIX}/apps/no-such-app/settings/",
            json={"auth": "oauth"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 8. Cascade Delete: Deleting an app removes all ecosystem data
# ═══════════════════════════════════════════════════════════════════

class TestCascadeDelete:
    """Verify that deleting an app cascades to all related ecosystem data."""

    def test_110_create_data_for_cascade_test(self, client: TestClient) -> None:
        """Create an app with all types of ecosystem data."""
        # App exists from previous tests (TEST_APP_ID)
        # Add a social post
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/social/",
            json={"author": "Cascade", "content": "Should be deleted"},
        )
        assert resp.status_code == 201
        # Add a blog article
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/blogs/",
            json={"title": "Cascade Blog", "summary": "...", "author": "Cascade"},
        )
        assert resp.status_code == 201
        # Add a review
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/reviews/",
            json={"author": "Cascade", "rating": 5, "title": "X", "content": "Y"},
        )
        assert resp.status_code == 201
        # Add a walkthrough
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/",
            json={
                "title": "Cascade WT",
                "summary": "...",
                "author": "Cascade",
                "steps": [{"title": "Step 1", "description": "..."}],
            },
        )
        assert resp.status_code == 201
        # Add a data source
        resp = client.post(
            f"{PREFIX}/apps/{TEST_APP_ID}/data/",
            json={"name": "Cascade DS", "type": "rest"},
        )
        assert resp.status_code == 201

    def test_111_verify_data_exists(self, client: TestClient) -> None:
        """Verify all ecosystem data is present before deletion."""
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/social/")
        assert resp.json()["total"] >= 1
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/blogs/")
        assert resp.json()["total"] >= 1
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/reviews/")
        assert resp.json()["total"] >= 1
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/")
        assert resp.json()["total"] >= 1
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/data/")
        assert len(resp.json()["data"]["sources"]) >= 1

    def test_112_delete_app(self, client: TestClient) -> None:
        """Delete the app — should cascade to all ecosystem data."""
        resp = client.delete(f"{PREFIX}/apps/{TEST_APP_ID}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_113_verify_cascade(self, client: TestClient) -> None:
        """Verify all ecosystem data was removed with the app."""
        # App is gone
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}")
        assert resp.status_code == 404

        # All related data is gone
        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/social/")
        assert resp.status_code == 404

        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/blogs/")
        assert resp.status_code == 404

        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/reviews/")
        assert resp.status_code == 404

        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/walkthroughs/")
        assert resp.status_code == 404

        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/data/")
        assert resp.status_code == 404

        resp = client.get(f"{PREFIX}/apps/{TEST_APP_ID}/settings/")
        assert resp.status_code == 404
