import httpx
from typing import List, Dict, Any
import asyncio
from cachetools import TTLCache

class MarketService:
    def __init__(self):
        # CoinGecko Public API doesn't require keys, but has rate limits.
        self.base_url = "https://api.coingecko.com/api/v3"
        # Cache results for 1 minute to avoid rate-limiting
        # Using cachetools as it's already in the dependencies
        self.cache = TTLCache(maxsize=10, ttl=60)

    async def get_live_market_data(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetches live market data from CoinGecko for the given coin IDs.
        """
        cache_key = ",".join(sorted(ids))
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "vs_currency": "usd",
                    "ids": ",".join(ids),
                    "order": "market_cap_desc",
                    "sparkline": "true",
                    "price_change_percentage": "24h"
                }
                response = await client.get(f"{self.base_url}/coins/markets", params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                self.cache[cache_key] = data
                return data
        except Exception as e:
            # Fallback handled by the engine (using simulation)
            print(f"MarketService Error: Failed to fetch live data: {e}")
            return []

market_service = MarketService()
