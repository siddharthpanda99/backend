"""
App Ecosystem — Forums & Discussions Routes

/api/v1/forums — Thread CRUD, replies, voting, pin/lock, accepted answers.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sqlfunc, desc

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import (
    ForumThreadRecord,
    ForumReplyRecord,
    ForumVoteRecord,
    AppActivityRecord,
    ThreadCreate,
    ThreadUpdate,
    ThreadResponse,
    ThreadListResponse,
    ThreadReplyCreate,
    ThreadReplyUpdate,
    ThreadReplyResponse,
    ThreadVoteRequest,
    APIResponse,
)
from app.modules.app_builder.schema.routes.ecosystem_utils import generate_unique_slug, record_activity

logger = logging.getLogger(__name__)
router = APIRouter(tags=["App Forums"])


# ─── Thread CRUD ────────────────────────────────────────────────

@router.get("/apps/{app_id}/threads", response_model=ThreadListResponse)
async def list_threads(
    app_id: str,
    category: Optional[str] = None,
    sort: Optional[str] = Query(None, pattern=r"^(newest|oldest|popular|unanswered)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    query = select(ForumThreadRecord).where(ForumThreadRecord.app_id == app_id)
    if category:
        query = query.where(ForumThreadRecord.category == category)

    if sort == "popular":
        query = query.order_by(desc(ForumThreadRecord.view_count))
    elif sort == "unanswered":
        query = query.where(ForumThreadRecord.is_solved == False)
        query = query.order_by(desc(ForumThreadRecord.created_at))
    elif sort == "oldest":
        query = query.order_by(ForumThreadRecord.created_at)
    else:
        # Default: pinned first, then newest
        query = query.order_by(desc(ForumThreadRecord.is_pinned), desc(ForumThreadRecord.created_at))

    count_q = select(sqlfunc.count()).select_from(query.subquery())
    total = db.execute(count_q).scalar() or 0
    items = db.execute(query.offset(offset).limit(limit)).scalars().all()

    return ThreadListResponse(
        items=[ThreadResponse.model_validate(i) for i in items],
        total=total,
    )


@router.post("/apps/{app_id}/threads", response_model=ThreadResponse, status_code=201)
async def create_thread(app_id: str, data: ThreadCreate, db: Session = Depends(get_session)):
    slug = generate_unique_slug(db, ForumThreadRecord, data.title)

    author_id = "current-user"
    record = ForumThreadRecord(
        id=str(uuid.uuid4()),
        app_id=app_id,
        author_id=author_id,
        slug=slug,
        **data.model_dump(),
    )
    db.add(record)
    record_activity(db, AppActivityRecord, app_id=app_id, actor_id=author_id, action="created_thread", entity_type="thread", entity_id=record.id, entity_title=data.title)
    db.commit()
    db.refresh(record)
    return ThreadResponse.model_validate(record)


@router.get("/threads/{slug}", response_model=ThreadResponse)
async def get_thread(slug: str, db: Session = Depends(get_session)):
    thread = db.execute(
        select(ForumThreadRecord).where(ForumThreadRecord.slug == slug)
    ).scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.view_count += 1
    db.commit()
    db.refresh(thread)
    return ThreadResponse.model_validate(thread)


@router.put("/threads/{thread_id}", response_model=ThreadResponse)
async def update_thread(thread_id: str, data: ThreadUpdate, db: Session = Depends(get_session)):
    thread = db.get(ForumThreadRecord, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(thread, k, v)
    thread.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(thread)
    return ThreadResponse.model_validate(thread)


@router.delete("/threads/{thread_id}", response_model=APIResponse)
async def delete_thread(thread_id: str, db: Session = Depends(get_session)):
    thread = db.get(ForumThreadRecord, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    # Delete replies first
    replies = db.execute(
        select(ForumReplyRecord).where(ForumReplyRecord.thread_id == thread_id)
    ).scalars().all()
    for r in replies:
        db.delete(r)
    db.delete(thread)
    db.commit()
    return APIResponse(message="Thread deleted")


# ─── Pin / Lock ─────────────────────────────────────────────────

@router.post("/threads/{thread_id}/pin", response_model=ThreadResponse)
async def toggle_pin(thread_id: str, db: Session = Depends(get_session)):
    thread = db.get(ForumThreadRecord, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.is_pinned = not thread.is_pinned
    db.commit()
    db.refresh(thread)
    return ThreadResponse.model_validate(thread)


@router.post("/threads/{thread_id}/lock", response_model=ThreadResponse)
async def toggle_lock(thread_id: str, db: Session = Depends(get_session)):
    thread = db.get(ForumThreadRecord, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.is_locked = not thread.is_locked
    db.commit()
    db.refresh(thread)
    return ThreadResponse.model_validate(thread)


# ─── Replies ────────────────────────────────────────────────────

@router.get("/threads/{thread_id}/replies", response_model=list[ThreadReplyResponse])
async def list_replies(thread_id: str, db: Session = Depends(get_session)):
    items = db.execute(
        select(ForumReplyRecord)
        .where(ForumReplyRecord.thread_id == thread_id, ForumReplyRecord.parent_id == None)
        .order_by(ForumReplyRecord.created_at)
    ).scalars().all()
    return [ThreadReplyResponse.model_validate(r) for r in items]


@router.post("/threads/{thread_id}/replies", response_model=ThreadReplyResponse, status_code=201)
async def create_reply(
    thread_id: str, data: ThreadReplyCreate, db: Session = Depends(get_session)
):
    thread = db.get(ForumThreadRecord, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.is_locked:
        raise HTTPException(status_code=403, detail="Thread is locked")

    record = ForumReplyRecord(
        id=str(uuid.uuid4()),
        thread_id=thread_id,
        author_id="current-user",
        parent_id=data.parent_id,
        body_markdown=data.body_markdown,
    )
    db.add(record)
    thread.reply_count += 1
    thread.last_reply_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return ThreadReplyResponse.model_validate(record)


@router.put("/thread-replies/{reply_id}", response_model=ThreadReplyResponse)
async def update_reply(reply_id: str, data: ThreadReplyUpdate, db: Session = Depends(get_session)):
    reply = db.get(ForumReplyRecord, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    reply.body_markdown = data.body_markdown
    reply.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(reply)
    return ThreadReplyResponse.model_validate(reply)


@router.delete("/thread-replies/{reply_id}", response_model=APIResponse)
async def delete_reply(reply_id: str, db: Session = Depends(get_session)):
    reply = db.get(ForumReplyRecord, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    thread = db.get(ForumThreadRecord, reply.thread_id)
    if thread and thread.reply_count > 0:
        thread.reply_count -= 1
    db.delete(reply)
    db.commit()
    return APIResponse(message="Reply deleted")


@router.post("/thread-replies/{reply_id}/accept", response_model=ThreadReplyResponse)
async def accept_answer(reply_id: str, db: Session = Depends(get_session)):
    reply = db.get(ForumReplyRecord, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")

    # Unmark any previously accepted answer
    prev = db.execute(
        select(ForumReplyRecord).where(
            ForumReplyRecord.thread_id == reply.thread_id,
            ForumReplyRecord.is_accepted_answer == True,
        )
    ).scalar_one_or_none()
    if prev:
        prev.is_accepted_answer = False

    reply.is_accepted_answer = True
    thread = db.get(ForumThreadRecord, reply.thread_id)
    if thread:
        thread.is_solved = True
        thread.accepted_answer_id = reply_id
    db.commit()
    db.refresh(reply)
    return ThreadReplyResponse.model_validate(reply)


@router.post("/thread-replies/{reply_id}/vote", response_model=ThreadReplyResponse)
async def vote_reply(
    reply_id: str, data: ThreadVoteRequest, db: Session = Depends(get_session)
):
    reply = db.get(ForumReplyRecord, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")

    user_id = "current-user"
    existing = db.execute(
        select(ForumVoteRecord).where(
            ForumVoteRecord.reply_id == reply_id,
            ForumVoteRecord.user_id == user_id,
        )
    ).scalar_one_or_none()

    if existing:
        if existing.vote == data.vote:
            db.delete(existing)
            reply.like_count += 1 if data.vote == "up" else -1
        else:
            existing.vote = data.vote
            reply.like_count += 2 if data.vote == "up" else -2
    else:
        db.add(ForumVoteRecord(
            id=str(uuid.uuid4()),
            reply_id=reply_id,
            user_id=user_id,
            vote=data.vote,
        ))
        reply.like_count += 1 if data.vote == "up" else -1

    db.commit()
    db.refresh(reply)
    return ThreadReplyResponse.model_validate(reply)
