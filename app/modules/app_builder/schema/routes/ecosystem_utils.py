"""
App Ecosystem — Shared Utilities

Common helpers used across ecosystem route files.
"""

import logging
import re
import uuid
from typing import Any, Dict, Optional, Type as TypingType

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sqlfunc

logger = logging.getLogger(__name__)

# Used only when DEV_MODE and no authenticated identity is present.
# Keeps local tooling working without tokens; never used in non-dev.
_DEV_FALLBACK_USER_ID = "dev-user"


def resolve_actor_user_id(
    request: Request,
    *,
    required: bool = True,
) -> Optional[str]:
    """Resolve the acting user id from AuthzMiddleware / request identity.

    Priority:
      1. ``request.state.authz.subject_id`` when present and not ``anonymous``
      2. ``request.state.identity`` subject fields (if middleware resolved one)
      3. ``request.state.user_id`` (if another layer set it)
      4. DEV_MODE only: fall back to ``dev-user`` so unauthenticated local
         tooling keeps working (same practical behaviour as the old
         hardcoded ``current-user``, but clearly marked as a dev sentinel)
      5. If ``required`` and not DEV_MODE: raise 401

    Read-only optional use (``required=False``) returns ``None`` when
    unauthenticated instead of falling back or raising.
    """
    authz = getattr(request.state, "authz", None)
    if authz is not None:
        subject_id = getattr(authz, "subject_id", None) or ""
        if subject_id and subject_id != "anonymous":
            return str(subject_id)

    identity = getattr(request.state, "identity", None)
    if identity is not None:
        for attr in ("subject_id", "user_id", "id"):
            value = getattr(identity, attr, None)
            if value:
                return str(value)

    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return str(user_id)

    if not required:
        return None

    # Lazy import avoids circular imports at module load.
    from app.core.settings import get_settings

    if get_settings().DEV_MODE:
        logger.debug(
            "resolve_actor_user_id: no authenticated identity; "
            "using DEV_MODE fallback %r",
            _DEV_FALLBACK_USER_ID,
        )
        return _DEV_FALLBACK_USER_ID

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


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
