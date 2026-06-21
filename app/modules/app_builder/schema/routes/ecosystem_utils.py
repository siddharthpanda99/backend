"""
App Ecosystem — Shared Utilities

Common helpers used across ecosystem route files.
"""

import re
import uuid
from typing import Any, Dict, Optional, Type as TypingType

from sqlalchemy.orm import Session
from sqlalchemy import select, func as sqlfunc


def slugify(text: str, max_length: int = 512) -> str:
    """Convert text to URL-friendly slug. Truncates to max_length."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:max_length] if max_length else slug


def generate_unique_slug(
    db: Session,
    model_class: TypingType,
    text: str,
    exclude_id: Optional[str] = None,
    max_length: int = 512,
) -> str:
    """Generate a unique slug, appending a UUID suffix if needed."""
    base = slugify(text, max_length)
    slug = base

    for _ in range(10):  # safety limit
        query = select(model_class).where(model_class.slug == slug)
        if exclude_id:
            query = query.where(model_class.id != exclude_id)
        existing = db.execute(query).scalar_one_or_none()
        if not existing:
            return slug
        suffix = str(uuid.uuid4())[:8]
        slug = f"{base[: max_length - len(suffix) - 1]}-{suffix}"

    # Final fallback — guaranteed unique
    return f"{base[: max_length - 9]}-{str(uuid.uuid4())[:8]}"


def record_activity(
    db: Session,
    model_class: TypingType,
    *,
    app_id: str,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    entity_title: str,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert an activity feed record. Caller must commit."""
    db.add(model_class(
        id=str(uuid.uuid4()),
        app_id=app_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_title=entity_title,
        metadata_json=metadata_json,
    ))
