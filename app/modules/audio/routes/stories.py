"""Stories multi-track narrative composition endpoints."""

import logging
from fastapi import APIRouter, HTTPException
from common_lib.modules.audio_processing.service import get_audio_service
from common_lib.modules.audio_processing.schemas import (
    StoryCreate, StoryUpdate, StoryResponse, StoryDetailResponse,
    StoryItemAdd, StoryItemMove, StoryItemTrim, StoryItemVersionUpdate,
    StoryItemReorder,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_response(s):
    return StoryResponse(
        id=s.id, name=s.name, description=getattr(s, 'description', None),
        item_count=getattr(s, 'item_count', 0), duration_ms=getattr(s, 'duration_ms', 0),
        created_at=getattr(s, 'created_at', None), updated_at=getattr(s, 'updated_at', None),
    )


@router.get("/stories", response_model=list[StoryResponse])
async def list_stories():
    svc = get_audio_service()
    return [_to_response(s) for s in await svc.list_stories()]


@router.post("/stories", response_model=StoryResponse)
async def create_story(data: StoryCreate):
    svc = get_audio_service()
    return _to_response(await svc.create_story(data.model_dump()))


@router.get("/stories/{story_id}", response_model=StoryDetailResponse)
async def get_story(story_id: str):
    svc = get_audio_service()
    result = await svc.get_story_with_items(story_id)
    if not result:
        raise HTTPException(404, "Story not found")
    return StoryDetailResponse(**result)


@router.put("/stories/{story_id}", response_model=StoryResponse)
async def update_story(story_id: str, data: StoryUpdate):
    svc = get_audio_service()
    s = await svc.update_story(story_id, {k: v for k, v in data.model_dump().items() if v is not None})
    if not s:
        raise HTTPException(404, "Story not found")
    return _to_response(s)


@router.delete("/stories/{story_id}")
async def delete_story(story_id: str):
    svc = get_audio_service()
    if not await svc.delete_story(story_id):
        raise HTTPException(404, "Story not found")
    return {"message": "Story deleted"}


@router.post("/stories/{story_id}/items")
async def add_item(story_id: str, data: StoryItemAdd):
    svc = get_audio_service()
    item = await svc.add_item(story_id, data.model_dump())
    if not item:
        raise HTTPException(404, "Story not found")
    return {"id": item["id"], "story_id": story_id, "generation_id": item["generation_id"],
            "start_time_ms": item["start_time_ms"], "track": item["track"], "message": "Item added"}


@router.delete("/stories/{story_id}/items/{item_id}")
async def remove_item(story_id: str, item_id: str):
    svc = get_audio_service()
    if not await svc.remove_item(story_id, item_id):
        raise HTTPException(404, "Item not found")
    return {"message": "Item removed"}


@router.put("/stories/{story_id}/items/reorder")
async def reorder_items(story_id: str, data: StoryItemReorder):
    svc = get_audio_service()
    result = await svc.reorder_items(story_id, data.generation_ids)
    if result is None:
        raise HTTPException(400, "Invalid reorder")
    return {"message": "Reordered", "count": len(result)}


@router.put("/stories/{story_id}/items/{item_id}/move")
async def move_item(story_id: str, item_id: str, data: StoryItemMove):
    svc = get_audio_service()
    if not await svc.move_item(story_id, item_id, data.start_time_ms, data.track):
        raise HTTPException(404, "Item not found")
    return {"message": "Item moved"}


@router.put("/stories/{story_id}/items/{item_id}/trim")
async def trim_item(story_id: str, item_id: str, data: StoryItemTrim):
    svc = get_audio_service()
    if not await svc.update_item_trim(story_id, item_id, data.trim_start_ms, data.trim_end_ms):
        raise HTTPException(404, "Item not found")
    return {"message": "Item trimmed"}


@router.put("/stories/{story_id}/items/{item_id}/version")
async def pin_version(story_id: str, item_id: str, data: StoryItemVersionUpdate):
    svc = get_audio_service()
    item = await svc.pin_version(story_id, item_id, data.version_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return {"message": f"Version {data.version_id or 'default'} pinned"}
