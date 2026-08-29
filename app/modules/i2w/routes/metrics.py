"""``app.modules.i2w.routes.metrics`` — Prometheus metrics endpoint.

Per docs/11_observability_security.md §1, the I2W framework emits
``i2w_*`` metrics. This endpoint exposes them in Prometheus text
exposition format (the platform's standard).

The endpoint delegates to the ``observability`` port accessor so the
metrics are defined once (in the common_lib layer) and exposed via
HTTP by the router (in the app/ layer). The router does not
hardcode any metric names — it reads the registry from observability.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/metrics",
    summary="Prometheus metrics for the I2W framework.",
    description=(
        "Text exposition format. Includes every ``i2w_*`` counter, "
        "histogram, and gauge defined in docs/11 §1. The endpoint is "
        "intended for the Prometheus scrape job; the body follows "
        "the platform-wide metrics format."
    ),
    response_model=None,
)
async def metrics(request: Request) -> Response:
    """Return the Prometheus text-format dump.

    The router delegates to the platform's observability layer;
    the I2W metrics are defined there. If observability is not
    configured the endpoint returns an empty 200 body (the metrics
    system is opt-in).
    """
    body = ""
    content_type = "text/plain; version=0.0.4"
    try:
        from common_lib.modules.observability import get_observability

        obs = get_observability()
        if obs is not None and hasattr(obs, "prometheus_text"):
            body = obs.prometheus_text()
            content_type = getattr(obs, "prometheus_content_type", content_type)
        elif obs is not None and hasattr(obs, "metrics_text"):
            body = obs.metrics_text()
    except Exception:  # noqa: BLE001
        logger.debug("observability.prometheus_text failed", exc_info=True)
    return Response(content=body, media_type=content_type)


__all__ = ["router"]
