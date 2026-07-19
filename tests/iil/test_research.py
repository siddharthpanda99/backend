"""IIL Research & Verify — Integration Tests.

Tests the POST /research and POST /verify API endpoints with mocked service layer.

Usage:
    cd "Backend Monorepo/Backend"
    uv run pytest tests/iil/test_research.py -v
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# =============================================================================
# POST /research Endpoint Tests
# =============================================================================


class TestResearchEndpoint:
    """Tests for POST /api/v1/iil/research"""

    def _make_research_response(self, **overrides):
        from common_lib.modules.iil.schemas import ResearchResponse
        return ResearchResponse(
            query=overrides.get("query", "test research"),
            summary=overrides.get("summary", "Research summary text"),
            findings=[],
            sources_consulted=["http://example.com"],
            pages_fetched=5,
            depth=2,
            confidence_overall=0.85,
            duration_ms=1200.0,
        )

    def test_research_success(self, client, mock_iil_service):
        """Research endpoint returns ResearchResponse on success."""
        from common_lib.modules.iil.schemas import ResearchResponse, ResearchFinding

        response = ResearchResponse(
            query="test research",
            summary="Research summary text",
            findings=[
                ResearchFinding(
                    claim="finding 1",
                    verified=True,
                    confidence=0.9,
                    supporting_sources=["http://example.com"],
                )
            ],
            sources_consulted=["http://example.com"],
            pages_fetched=5,
            depth=2,
            confidence_overall=0.85,
            duration_ms=1200.0,
        )
        mock_iil_service.research = AsyncMock(return_value=response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/research",
                json={"query": "test research", "depth": 2, "verify": True},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "test research"
        assert data["summary"] == "Research summary text"
        assert data["depth"] == 2
        assert data["confidence_overall"] == 0.85

    def test_research_with_min_sources(self, client, mock_iil_service):
        """Research endpoint passes min_sources to service."""
        response = self._make_research_response()
        mock_iil_service.research = AsyncMock(return_value=response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/research",
                json={"query": "test", "min_sources": 5},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.research.call_args
        assert call_kwargs[1]["min_sources"] == 5

    def test_research_with_code_and_papers(self, client, mock_iil_service):
        """Research endpoint passes code and papers flags."""
        response = self._make_research_response()
        mock_iil_service.research = AsyncMock(return_value=response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/research",
                json={
                    "query": "test",
                    "include_code": True,
                    "include_papers": True,
                    "include_news": False,
                },
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.research.call_args
        assert call_kwargs[1]["include_code"] is True
        assert call_kwargs[1]["include_papers"] is True
        assert call_kwargs[1]["include_news"] is False

    def test_research_service_error(self, client, mock_iil_service):
        """Research endpoint returns 502 when service sets error."""
        from common_lib.modules.iil.schemas import ResearchResponse

        error_response = ResearchResponse(
            query="test",
            error="Research engine unavailable",
        )
        mock_iil_service.research = AsyncMock(return_value=error_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/research",
                json={"query": "test"},
            )

        assert resp.status_code == 502
        body = resp.json()
        assert "Research engine unavailable" in body.get("message", "")

    def test_research_missing_query(self, client):
        """Research endpoint returns 422 when query is missing."""
        resp = client.post("/api/v1/iil/research", json={"depth": 2})
        assert resp.status_code == 422

    def test_research_default_depth(self, client, mock_iil_service):
        """Research endpoint uses default depth=2."""
        response = self._make_research_response()
        mock_iil_service.research = AsyncMock(return_value=response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/research",
                json={"query": "test"},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.research.call_args
        assert call_kwargs[1]["depth"] == 2

    def test_research_with_bypass_cache(self, client, mock_iil_service):
        """Research endpoint passes bypass_cache flag."""
        response = self._make_research_response()
        mock_iil_service.research = AsyncMock(return_value=response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/research",
                json={"query": "test", "bypass_cache": True},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.research.call_args
        assert call_kwargs[1]["bypass_cache"] is True


# =============================================================================
# POST /verify Endpoint Tests
# =============================================================================


class TestVerifyEndpoint:
    """Tests for POST /api/v1/iil/verify"""

    def _make_verify_response(self, **overrides):
        from common_lib.modules.iil.schemas import VerifyFactResponse
        return VerifyFactResponse(
            claim=overrides.get("claim", "The earth orbits the sun"),
            verified=overrides.get("verified", True),
            confidence=overrides.get("confidence", 0.95),
            supporting_sources=overrides.get("supporting_sources", [
                {"url": "http://nasa.gov", "snippet": "Earth orbits the sun"}
            ]),
            contradicting_sources=overrides.get("contradicting_sources", []),
            neutral_sources=overrides.get("neutral_sources", []),
            total_sources_checked=overrides.get("total_sources_checked", 3),
            has_conflicting=overrides.get("has_conflicting", False),
            summary=overrides.get("summary", "Claim is verified"),
        )

    def test_verify_success(self, client, mock_iil_service):
        """Verify endpoint returns VerifyFactResponse on success."""
        response = self._make_verify_response()
        mock_iil_service.verify_fact = AsyncMock(return_value=response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/verify",
                json={"claim": "The earth orbits the sun"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["claim"] == "The earth orbits the sun"
        assert data["verified"] is True
        assert data["confidence"] == 0.95
        assert len(data["supporting_sources"]) == 1

    def test_verify_with_min_agreeing(self, client, mock_iil_service):
        """Verify endpoint passes min_agreeing_sources to service."""
        response = self._make_verify_response()
        mock_iil_service.verify_fact = AsyncMock(return_value=response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/verify",
                json={"claim": "test", "min_agreeing_sources": 3},
            )

        assert resp.status_code == 200
        call_kwargs = mock_iil_service.verify_fact.call_args
        assert call_kwargs[1]["min_agreeing_sources"] == 3

    def test_verify_not_verified(self, client, mock_iil_service):
        """Verify endpoint handles claims that fail verification."""
        response = self._make_verify_response(verified=False, confidence=0.1)
        mock_iil_service.verify_fact = AsyncMock(return_value=response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/verify",
                json={"claim": "The earth is flat"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is False
        assert data["confidence"] == 0.1

    def test_verify_service_error(self, client, mock_iil_service):
        """Verify endpoint returns 502 when service sets error."""
        from common_lib.modules.iil.schemas import VerifyFactResponse

        error_response = VerifyFactResponse(
            claim="test",
            error="Verification engine unavailable",
        )
        mock_iil_service.verify_fact = AsyncMock(return_value=error_response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/verify",
                json={"claim": "test"},
            )

        assert resp.status_code == 502

    def test_verify_missing_claim(self, client):
        """Verify endpoint returns 422 when claim is missing."""
        resp = client.post("/api/v1/iil/verify", json={})
        assert resp.status_code == 422

    def test_verify_with_conflicting_sources(self, client, mock_iil_service):
        """Verify endpoint handles conflicting sources."""
        response = self._make_verify_response(
            verified=False,
            confidence=0.3,
            supporting_sources=[{"url": "http://src1.com", "snippet": "Yes"}],
            contradicting_sources=[{"url": "http://src2.com", "snippet": "No"}],
            has_conflicting=True,
        )
        mock_iil_service.verify_fact = AsyncMock(return_value=response)

        with patch("app.modules.iil.routes._get_service", return_value=mock_iil_service):
            resp = client.post(
                "/api/v1/iil/verify",
                json={"claim": "test claim"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["has_conflicting"] is True
        assert len(data["contradicting_sources"]) == 1
