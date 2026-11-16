"""Voice consent + watermark routes (safety features — always available).

Thin transport layer. Business logic lives in:
  - common_lib.modules.audio_processing.services.consent_service
  - common_lib.modules.audio_processing.services.watermarking

NOT mounted by this file — the parent wires the routers into the audio
router::

    from app.modules.audio.routes.consent import router as consent_router
    from app.modules.audio.routes.consent import watermark_router

    app.include_router(consent_router, prefix="/api/v1/audio")
    app.include_router(watermark_router, prefix="/api/v1/audio")

which yields:
  - /api/v1/audio/consent/...        (consent ledger endpoints)
  - /api/v1/audio/watermark/...      (watermark embed/extract endpoints)

NOTE: these endpoints are ALWAYS available and are intentionally NOT gated
behind any feature flag. Voice consent and provenance watermarking are
safety/compliance features — blocking them behind a flag would let a
misconfigured deployment ship without them.
"""

from app.modules.audio.routes.consent.consent_routes import router, watermark_router

__all__ = ["router", "watermark_router"]
