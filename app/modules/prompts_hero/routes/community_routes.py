"""Community routes — likes, comments, collections."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session

router = APIRouter()


class LikeRequest(BaseModel):
    user_id: str


class CommentRequest(BaseModel):
    user_id: str
    content: str
    parent_id: str | None = None


class CollectionCreateRequest(BaseModel):
    user_id: str
    name: str
    description: str | None = None


class CollectionItemRequest(BaseModel):
    generation_id: str
    note: str | None = None


def _svc():
    from common_lib.modules.prompts_hero.services.community_service import (
        CommunityService,
    )

    return CommunityService()


# --- Likes ---


@router.post("/generations/{generation_id}/like")
def like_generation(
    generation_id: str, body: LikeRequest, session: Session = Depends(get_session)
):
    svc = _svc()
    like = svc.like(session, user_id=body.user_id, generation_id=generation_id)
    if not like:
        raise HTTPException(409, "Already liked")
    return {"success": True, "data": {"id": like.id}}


@router.delete("/generations/{generation_id}/like")
def unlike_generation(
    generation_id: str, body: LikeRequest, session: Session = Depends(get_session)
):
    svc = _svc()
    if not svc.unlike(session, user_id=body.user_id, generation_id=generation_id):
        raise HTTPException(404, "Like not found")
    return {"success": True}


@router.get("/generations/{generation_id}/likes")
def count_likes(generation_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    count = svc.count_likes(session, generation_id)
    return {"success": True, "data": {"count": count}}


# --- Comments ---


@router.post("/generations/{generation_id}/comments")
def add_comment(
    generation_id: str, body: CommentRequest, session: Session = Depends(get_session)
):
    svc = _svc()
    comment = svc.add_comment(
        session,
        user_id=body.user_id,
        generation_id=generation_id,
        content=body.content,
        parent_id=body.parent_id,
    )
    return {"success": True, "data": comment.model_dump()}


@router.get("/generations/{generation_id}/comments")
def list_comments(generation_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    comments = svc.list_comments(session, generation_id)
    return {"success": True, "data": [c.model_dump() for c in comments]}


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    if not svc.delete_comment(session, comment_id):
        raise HTTPException(404, "Comment not found")
    return {"success": True}


# --- Collections ---


@router.post("/collections")
def create_collection(
    body: CollectionCreateRequest, session: Session = Depends(get_session)
):
    svc = _svc()
    col = svc.create_collection(
        session, user_id=body.user_id, name=body.name, description=body.description
    )
    return {"success": True, "data": col.model_dump()}


@router.get("/collections/user/{user_id}")
def list_user_collections(user_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    cols = svc.list_user_collections(session, user_id)
    return {"success": True, "data": [c.model_dump() for c in cols]}


@router.get("/collections/public")
def list_public_collections(limit: int = 20, session: Session = Depends(get_session)):
    svc = _svc()
    cols = svc.list_public_collections(session, limit=limit)
    return {"success": True, "data": [c.model_dump() for c in cols]}


@router.get("/collections/{collection_id}")
def get_collection(collection_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    col = svc.get_collection(session, collection_id)
    if not col:
        raise HTTPException(404, "Collection not found")
    return {"success": True, "data": col.model_dump()}


@router.delete("/collections/{collection_id}")
def delete_collection(collection_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    if not svc.delete_collection(session, collection_id):
        raise HTTPException(404, "Collection not found")
    return {"success": True}


@router.post("/collections/{collection_id}/items")
def add_to_collection(
    collection_id: str,
    body: CollectionItemRequest,
    session: Session = Depends(get_session),
):
    svc = _svc()
    item = svc.add_to_collection(
        session,
        collection_id=collection_id,
        generation_id=body.generation_id,
        note=body.note,
    )
    if not item:
        raise HTTPException(409, "Already in collection or collection not found")
    return {"success": True, "data": item.model_dump()}


@router.delete("/collections/{collection_id}/items/{generation_id}")
def remove_from_collection(
    collection_id: str, generation_id: str, session: Session = Depends(get_session)
):
    svc = _svc()
    if not svc.remove_from_collection(
        session, collection_id=collection_id, generation_id=generation_id
    ):
        raise HTTPException(404, "Item not found")
    return {"success": True}


@router.get("/collections/{collection_id}/items")
def list_collection_items(collection_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    items = svc.list_collection_items(session, collection_id)
    return {"success": True, "data": [i.model_dump() for i in items]}
