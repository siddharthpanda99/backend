"""Regression tests for the /scrape route's fabricated success.

`app/modules/prompt_studio/routes/scraper.py` returned HTTP 200 with
``success: True`` and an empty list for **any** failed search — unknown spider,
upstream error, or an exception. A caller that trusted ``success`` concluded
"there are no prompts" when the truth was "the scrape failed".

These tests call the handler directly and stub the service, so no network and
no `scrapling` install is needed.
"""

import pytest

from app.modules.prompt_studio.routes import scraper as scraper_routes


class _FakeScraperService:
    """Stands in for ScraperService so no network is touched."""

    def __init__(self, result=None, raises=None):
        self._result = (
            result if result is not None else {"success": True, "prompts": []}
        )
        self._raises = raises

    def scrape(self, spider, action, params):
        if self._raises is not None:
            raise self._raises
        return self._result

    def import_json(self, prompts, mode="skip", dry_run=False):
        return {"success": True, "imported": len(prompts), "results": []}


@pytest.fixture(name="fake")
def fake_fixture(monkeypatch):
    def _install(result=None, raises=None):
        svc = _FakeScraperService(result=result, raises=raises)
        monkeypatch.setattr(scraper_routes, "ScraperService", svc)
        return svc

    return _install


def _req(**kw):
    return scraper_routes.ScrapeRequest(**kw)


# --- failures must not be reported as success ------------------------------


@pytest.mark.asyncio
async def test_failed_search_reports_failure_not_empty_success(fake):
    """The headline defect: a failed search looked like an empty result set."""
    fake(result={"success": False, "error": "upstream 500"})

    out = await scraper_routes.scrape(_req(spider="prompthero", action="search"))

    assert out["success"] is False, "failed scrape reported success"
    assert out["error"] == "upstream 500"
    assert out["prompts"] == []


@pytest.mark.asyncio
async def test_unknown_spider_search_reports_failure(fake):
    fake(result={"success": False, "error": "Unknown spider: nope"})

    out = await scraper_routes.scrape(_req(spider="nope", action="search"))

    assert out["success"] is False
    assert "Unknown spider" in out["error"]


@pytest.mark.asyncio
async def test_exception_in_search_reports_failure(fake):
    """An exception used to be swallowed into success=True + empty list."""
    fake(raises=RuntimeError("scrapling is not available"))

    out = await scraper_routes.scrape(_req(spider="prompthero", action="search"))

    assert out["success"] is False
    assert "scrapling" in out["error"]


@pytest.mark.asyncio
async def test_reddit_search_failure_reports_failure(fake):
    fake(result={"success": False, "error": "rate limited"})

    out = await scraper_routes.scrape(_req(spider="reddit", action="search"))

    assert out["success"] is False


# --- a genuine empty result is still a success -----------------------------


@pytest.mark.asyncio
async def test_successful_search_with_no_matches_is_still_success(fake):
    """Zero matches is not a failure — it must stay success=True."""
    fake(result={"success": True, "prompts": []})

    out = await scraper_routes.scrape(_req(spider="prompthero", action="search"))

    assert out["success"] is True
    assert out["prompts"] == []


@pytest.mark.asyncio
async def test_successful_search_payload_is_passed_through(fake):
    payload = {"success": True, "prompts": [{"url": "u"}], "count": 1}
    fake(result=payload)

    out = await scraper_routes.scrape(_req(spider="prompthero", action="search"))

    assert out == payload


# --- non-search actions still raise ---------------------------------------


@pytest.mark.asyncio
async def test_failed_details_action_still_raises_400(fake):
    from fastapi import HTTPException

    fake(result={"success": False, "error": "url required"})

    with pytest.raises(HTTPException) as exc:
        await scraper_routes.scrape(_req(spider="prompthero", action="details"))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_exception_in_details_action_still_raises_500(fake):
    from fastapi import HTTPException

    fake(raises=RuntimeError("boom"))

    with pytest.raises(HTTPException) as exc:
        await scraper_routes.scrape(_req(spider="prompthero", action="details"))
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_error_keys_present_on_search_failure(fake):
    """The failure shape must carry the same keys the success shape has."""
    fake(result={"success": False, "error": "nope"})

    out = await scraper_routes.scrape(_req(spider="reddit", action="search"))

    for key in ("success", "count", "error"):
        assert key in out
    # reddit callers read posts/subreddits, not prompts
    for key in ("prompts", "posts", "subreddits"):
        assert key in out
