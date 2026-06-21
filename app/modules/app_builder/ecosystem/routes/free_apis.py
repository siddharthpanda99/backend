"""
Free API Catalog — Read-only route serving public free API references.

The data mirrors the FREE_APIS constant from the frontend mock data
(mockEcosystemData.ts) so the frontend can fetch it from the real backend.
"""

from fastapi import APIRouter
from common_lib.modules.app_builder.ecosystem.schemas import FreeAPISchema, APIResponse

router = APIRouter(prefix="/apps/free-apis", tags=["ecosystem-free-apis"])

# ─── Free Open APIs Catalog ────────────────────────────────────────
# Mirrors FREE_APIS in platform-demo/.../AppEcosystemPage/data/mockEcosystemData.ts

FREE_API_CATALOG: list[FreeAPISchema] = [
    FreeAPISchema(
        name="JSONPlaceholder",
        url="https://jsonplaceholder.typicode.com",
        description="Fake REST API for testing/prototyping",
        category="general",
    ),
    FreeAPISchema(
        name="OpenWeatherMap",
        url="https://api.openweathermap.org",
        description="Current weather & forecasts (free tier: 60 calls/min)",
        category="weather",
    ),
    FreeAPISchema(
        name="CoinGecko",
        url="https://api.coingecko.com/api/v3",
        description="Cryptocurrency prices, markets, and trends",
        category="finance",
    ),
    FreeAPISchema(
        name="NewsAPI",
        url="https://newsapi.org/v2",
        description="Global news headlines and articles",
        category="news",
    ),
    FreeAPISchema(
        name="REST Countries",
        url="https://restcountries.com/v3.1",
        description="Country information: flags, population, languages",
        category="reference",
    ),
    FreeAPISchema(
        name="TheMealDB",
        url="https://www.themealdb.com/api/json/v1/1",
        description="Recipe database with categories and ingredients",
        category="food",
    ),
    FreeAPISchema(
        name="PokeAPI",
        url="https://pokeapi.co/api/v2",
        description="Pokémon data: species, abilities, types",
        category="entertainment",
    ),
    FreeAPISchema(
        name="SpaceX API",
        url="https://api.spacexdata.com/v4",
        description="Rockets, launches, capsules, and crew data",
        category="science",
    ),
    FreeAPISchema(
        name="Rick & Morty API",
        url="https://rickandmortyapi.com/api",
        description="Characters, locations, and episodes",
        category="entertainment",
    ),
    FreeAPISchema(
        name="Open Library",
        url="https://openlibrary.org/api",
        description="Books, authors, covers, and editions",
        category="reference",
    ),
]


@router.get("", response_model=APIResponse)
async def list_free_apis():
    """List all free open APIs available in the catalog."""
    return APIResponse(
        status="success",
        data=[api.model_dump() for api in FREE_API_CATALOG],
    )


@router.get("/categories", response_model=APIResponse)
async def list_free_api_categories():
    """List unique categories available in the free API catalog."""
    categories = sorted(set(api.category for api in FREE_API_CATALOG))
    return APIResponse(
        status="success",
        data=categories,
    )
