"""Code Review Webhook Routes."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session

from common_lib.modules.integration.adapters.database_adapter import get_db_port
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
        payload = await request.json()
        signature = (
            x_hub_signature_256.replace("sha256=", "") if x_hub_signature_256 else None
        )

        result = service.process_webhook(
            provider="github",
            event=x_github_event,
            payload=payload,
            signature=signature,
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
        payload = await request.json()

        result = service.process_webhook(
            provider="gitlab",
            event=x_gitlab_event,
            payload=payload,
            signature=x_gitlab_token,
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
        payload = await request.json()

        result = service.process_webhook(
            provider="gerrit",
            event=x_gerrit_event,
            payload=payload,
            signature=None,
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
