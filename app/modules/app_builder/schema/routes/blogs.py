"""
App Ecosystem — Blogs & Articles Routes

/api/v1/blogs — CRUD, publish, comments, likes.
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
    AppBlogPostRecord,
    AppBlogCommentRecord,
    AppBlogLikeRecord,
    AppActivityRecord,
    BlogPostCreate,
    BlogPostUpdate,
    BlogPostResponse,
    BlogPostListResponse,
    BlogCommentCreate,
    BlogCommentResponse,
    APIResponse,
)
from app.modules.app_builder.schema.routes.ecosystem_utils import generate_unique_slug, record_activity

logger = logging.getLogger(__name__)
router = APIRouter(tags=["App Blogs"])


def _record_activity(
    db: Session, app_id: str, actor_id: str, action: str,
    entity_type: str, entity_id: str, entity_title: str,
):
    db.add(AppActivityRecord(
        id=str(uuid.uuid4()),
        app_id=app_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_title=entity_title,
    ))


# ─── Blog Posts CRUD ────────────────────────────────────────────

@router.get("/apps/{app_id}/blogs", response_model=BlogPostListResponse)
async def list_blogs(
    app_id: str,
    category: Optional[str] = None,
    status: Optional[str] = Query(None, pattern=r"^(draft|published)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    query = select(AppBlogPostRecord).where(AppBlogPostRecord.app_id == app_id)
    if status:
        query = query.where(AppBlogPostRecord.status == status)
    else:
        query = query.where(AppBlogPostRecord.status == "published")
    if category:
        query = query.where(AppBlogPostRecord.category == category)

    query = query.order_by(desc(AppBlogPostRecord.created_at))
    count_q = select(sqlfunc.count()).select_from(query.subquery())
    total = db.execute(count_q).scalar() or 0
    items = db.execute(query.offset(offset).limit(limit)).scalars().all()

    return BlogPostListResponse(
        items=[BlogPostResponse.model_validate(i) for i in items],
        total=total,
    )


@router.post("/apps/{app_id}/blogs", response_model=BlogPostResponse, status_code=201)
async def create_blog(app_id: str, data: BlogPostCreate, db: Session = Depends(get_session)):
    slug = generate_unique_slug(db, AppBlogPostRecord, data.title)

    author_id = "current-user"  # TODO: auth
    record = AppBlogPostRecord(
        id=str(uuid.uuid4()),
        app_id=app_id,
        author_id=author_id,
        slug=slug,
        **data.model_dump(),
    )
    db.add(record)
    record_activity(db, AppActivityRecord, app_id=app_id, actor_id=author_id, action="published_blog", entity_type="blog", entity_id=record.id, entity_title=data.title)
    db.commit()
    db.refresh(record)
    return BlogPostResponse.model_validate(record)


@router.get("/blogs/{slug}", response_model=BlogPostResponse)
async def get_blog(slug: str, db: Session = Depends(get_session)):
    post = db.execute(
        select(AppBlogPostRecord).where(AppBlogPostRecord.slug == slug)
    ).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    post.view_count += 1
    db.commit()
    db.refresh(post)
    return BlogPostResponse.model_validate(post)


@router.put("/blogs/{blog_id}", response_model=BlogPostResponse)
async def update_blog(blog_id: str, data: BlogPostUpdate, db: Session = Depends(get_session)):
    post = db.get(AppBlogPostRecord, blog_id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(post, k, v)
    if data.title:
        post.slug = generate_unique_slug(db, AppBlogPostRecord, data.title, exclude_id=blog_id)
    post.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post)
    return BlogPostResponse.model_validate(post)


@router.delete("/blogs/{blog_id}", response_model=APIResponse)
async def delete_blog(blog_id: str, db: Session = Depends(get_session)):
    post = db.get(AppBlogPostRecord, blog_id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    db.delete(post)
    db.commit()
    return APIResponse(message="Blog post deleted")


@router.post("/blogs/{blog_id}/publish", response_model=BlogPostResponse)
async def publish_blog(blog_id: str, db: Session = Depends(get_session)):
    post = db.get(AppBlogPostRecord, blog_id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    post.status = "published"
    post.published_at = datetime.now(timezone.utc)
    post.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post)
    return BlogPostResponse.model_validate(post)


# ─── Blog Comments ──────────────────────────────────────────────

@router.get("/blogs/{blog_id}/comments", response_model=list[BlogCommentResponse])
async def list_comments(blog_id: str, db: Session = Depends(get_session)):
    items = db.execute(
        select(AppBlogCommentRecord)
        .where(AppBlogCommentRecord.blog_id == blog_id, AppBlogCommentRecord.parent_id == None)
        .order_by(AppBlogCommentRecord.created_at)
    ).scalars().all()
    return [BlogCommentResponse.model_validate(c) for c in items]


@router.post("/blogs/{blog_id}/comments", response_model=BlogCommentResponse, status_code=201)
async def create_comment(
    blog_id: str, data: BlogCommentCreate, db: Session = Depends(get_session)
):
    post = db.get(AppBlogPostRecord, blog_id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    record = AppBlogCommentRecord(
        id=str(uuid.uuid4()),
        blog_id=blog_id,
        author_id="current-user",  # TODO: auth
        parent_id=data.parent_id,
        body=data.body,
    )
    db.add(record)
    post.comment_count += 1
    db.commit()
    db.refresh(record)
    return BlogCommentResponse.model_validate(record)


@router.delete("/blog-comments/{comment_id}", response_model=APIResponse)
async def delete_comment(comment_id: str, db: Session = Depends(get_session)):
    comment = db.get(AppBlogCommentRecord, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    post = db.get(AppBlogPostRecord, comment.blog_id)
    if post and post.comment_count > 0:
        post.comment_count -= 1
    db.delete(comment)
    db.commit()
    return APIResponse(message="Comment deleted")


@router.post("/blogs/{blog_id}/like")
async def toggle_like(blog_id: str, db: Session = Depends(get_session)):
    post = db.get(AppBlogPostRecord, blog_id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    user_id = "current-user"  # TODO: auth
    existing = db.execute(
        select(AppBlogLikeRecord).where(
            AppBlogLikeRecord.blog_id == blog_id,
            AppBlogLikeRecord.user_id == user_id,
        )
    ).scalar_one_or_none()

    if existing:
        db.delete(existing)
        post.like_count = max(0, post.like_count - 1)
        liked = False
    else:
        db.add(AppBlogLikeRecord(id=str(uuid.uuid4()), blog_id=blog_id, user_id=user_id))
        post.like_count += 1
        liked = True

    db.commit()
    return {"liked": liked, "like_count": post.like_count}
