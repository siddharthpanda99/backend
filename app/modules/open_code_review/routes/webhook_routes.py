"""Code Review Webhook Routes."""

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session

from common_lib.modules.integration.adapters.database_adapter import get_db_port
from common_lib.modules.open_code_review.models import WebhookProvider
from common_lib.modules.open_code_review.schemas import WebhookPayload
from common_lib.modules.open_code_review.service import get_open_code_review_service


def get_db_session() -> Session:
    """Get database session via integration port."""
    engine = get_db_port().get_engine()
    return Session(engine)


router = APIRouter()


@router.post("/github", summary="GitHub webhook handler")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db_session),
):
    """Handle GitHub webhook events."""
    service = get_open_code_review_service(db)
    try:
        # GitHub signs the exact bytes it sent; decode a copy and keep the raw
        # body so the HMAC can actually be reproduced.
        raw_body = await request.body()
        payload = json.loads(raw_body or b"{}")
        signature = x_hub_signature_256 or None

        result = service.process_webhook(
            provider=WebhookProvider.GITHUB,
            event=x_github_event,
            payload=payload,
            signature=signature,
            raw_body=raw_body,
            # The full header set, not just the one signature. Without it the
            # verifier can never see the legacy sha1 X-Hub-Signature header (a
            # caller holding one string cannot express "which header was this"),
            # nor any replay timestamp a reverse proxy added.
            headers=dict(request.headers),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/gitlab", summary="GitLab webhook handler")
async def gitlab_webhook(
    request: Request,
    x_gitlab_event: str = Header(None, alias="X-Gitlab-Event"),
    x_gitlab_token: str = Header(None, alias="X-Gitlab-Token"),
    db: Session = Depends(get_db_session),
):
    """Handle GitLab webhook events."""
    service = get_open_code_review_service(db)
    try:
        raw_body = await request.body()
        payload = json.loads(raw_body or b"{}")

        result = service.process_webhook(
            provider=WebhookProvider.GITLAB,
            event=x_gitlab_event,
            payload=payload,
            signature=x_gitlab_token,
            raw_body=raw_body,
            # X-Gitlab-Webhook-Timestamp (GitLab >= 16.9) lives in here. It is
            # the only replay defence the GitLab scheme has, and it is
            # unreachable without the full headers.
            headers=dict(request.headers),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/gerrit", summary="Gerrit webhook handler")
async def gerrit_webhook(
    request: Request,
    x_gerrit_event: str = Header(None, alias="X-Gerrit-Event"),
    db: Session = Depends(get_db_session),
):
    """Handle Gerrit webhook events."""
    service = get_open_code_review_service(db)
    try:
        raw_body = await request.body()
        payload = json.loads(raw_body or b"{}")

        result = service.process_webhook(
            provider=WebhookProvider.GERRIT,
            event=x_gerrit_event,
            payload=payload,
            signature=None,
            raw_body=raw_body,
            # Gerrit signs nothing, so the credential is the operator-supplied
            # X-Gerrit-Token header (and any proxy-added X-Gerrit-Timestamp
            # replay stamp). Both are only visible in the full header set.
            headers=dict(request.headers),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generic", summary="Generic webhook handler")
async def generic_webhook(
    webhook: WebhookPayload,
    db: Session = Depends(get_db_session),
):
    """Handle generic webhook events."""
    service = get_open_code_review_service(db)
    try:
        result = service.process_webhook(
            provider=webhook.provider,
            event=webhook.event,
            payload=webhook.payload,
            signature=webhook.signature,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
