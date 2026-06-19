from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
import json
import asyncio
from common_lib.modules.data_forge.engine import DataForgeEngine
from common_lib.modules.data_forge.service import market_service

router = APIRouter()
# The engine is initialized once and shared across requests for state consistency
data_forge_engine = DataForgeEngine()


@router.get("/stream")
async def stream_data(
    category: str = Query(
        "finance", description="Category of data forge (finance, hr, inventory)"
    ),
):
    """
    Server-Sent Events endpoint for real-time data using common_lib DataForgeEngine.
    """

    async def event_generator():
        while True:
            live_data = None
            if category == "finance":
                # Fetch live IDs from the template
                ids = [
                    t["id"]
                    for t in data_forge_engine.templates.get("finance", {}).get(
                        "tickers", []
                    )
                ]
                if ids:
                    live_data = await market_service.get_live_market_data(ids)

            # Yield events in SSE format
            update = data_forge_engine.generate_update(category, live_data=live_data)
            yield f"data: {json.dumps(update)}\n\n"
            # Slightly longer sleep for live API to avoid hammer
            await asyncio.sleep(2.0 if live_data else 0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/snapshot")
async def get_snapshot(category: str = Query("finance")):
    """
    Returns an initial full snapshot of the DataForge data from common_lib templates.
    """
    live_data = None
    if category == "finance":
        ids = [
            t["id"]
            for t in data_forge_engine.templates.get("finance", {}).get("tickers", [])
        ]
        if ids:
            live_data = await market_service.get_live_market_data(ids)

    return data_forge_engine.get_full_snapshot(category, live_data=live_data)
