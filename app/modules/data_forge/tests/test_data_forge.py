# Data Forge Tests
import pytest


class TestMarketService:
    """Tests for MarketService (Data Forge)"""

    def test_service_instance_exists(self):
        from common_lib.modules.data_forge.service import market_service

        assert market_service is not None

    def test_service_has_get_live_market_data_method(self):
        from common_lib.modules.data_forge.service import market_service

        assert hasattr(market_service, "get_live_market_data")
        assert callable(market_service.get_live_market_data)

    def test_service_has_get_historical_data_method(self):
        from common_lib.modules.data_forge.service import market_service

        assert hasattr(market_service, "get_historical_data")
        assert callable(market_service.get_historical_data)

    def test_service_has_base_url(self):
        from common_lib.modules.data_forge.service import MarketService

        service = MarketService()
        assert hasattr(service, "base_url")
        assert "coingecko" in service.base_url

    def test_service_has_cache(self):
        from common_lib.modules.data_forge.service import MarketService

        service = MarketService()
        assert hasattr(service, "cache")

    def test_market_service_is_async(self):
        from common_lib.modules.data_forge.service import MarketService
        import inspect

        assert inspect.iscoroutinefunction(MarketService.get_live_market_data)
        assert inspect.iscoroutinefunction(MarketService.get_historical_data)


class TestMarketServiceUnit:
    """Unit tests for market service"""

    def test_market_service_initialization(self):
        from common_lib.modules.data_forge.service import MarketService

        service = MarketService()
        assert service.base_url == "https://api.coingecko.com/api/v3"
        assert service.cache is not None

    def test_cache_configuration(self):
        from common_lib.modules.data_forge.service import MarketService
        from cachetools import TTLCache

        service = MarketService()
        assert isinstance(service.cache, TTLCache)
        assert service.cache.maxsize == 10


class TestMarketServiceValidation:
    """Validation tests"""

    def test_cache_key_generation(self):
        ids = ["bitcoin", "ethereum"]
        cache_key = ",".join(sorted(ids))
        assert cache_key == "bitcoin,ethereum"

    def test_url_construction(self):
        base_url = "https://api.coingecko.com/api/v3"
        url = f"{base_url}/coins/markets"
        assert url == "https://api.coingecko.com/api/v3/coins/markets"
