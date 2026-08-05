"""Notification Template API Routes — Template CRUD and rendering."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/templates", tags=["notification-templates"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("")
def list_templates(
    locale: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
):
    """List notification templates."""
    from common_lib.modules.notification.templates.service import TemplateService
    svc = TemplateService(session)
    return {"templates": svc.list_templates(locale=locale)}


@router.post("")
def create_template(
    name: str = Query(...),
    template_body: str = Query(...),
    content_type: str = Query("text/plain"),
    session: Session = Depends(_get_session),
):
    """Create a notification template."""
    from common_lib.modules.notification.templates.service import TemplateService
    svc = TemplateService(session)
    return svc.create_template(name=name, template_body=template_body, content_type=content_type)


@router.post("/render")
def render_template(
    name: str = Query(...),
    context: dict = {},
    locale: str = Query("en"),
    session: Session = Depends(_get_session),
):
    """Render a notification template with context."""
    from common_lib.modules.notification.templates.service import TemplateService
    svc = TemplateService(session)
    result = svc.render(name=name, context=context, locale=locale)
    return result
