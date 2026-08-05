"""Notification Routes — All submodule routes aggregated into a single router."""

from fastapi import APIRouter

# Main router for SSE/stream/channels
from app.modules.notification.routes.router import router as main_router

# Inbox/preferences/mentions
from app.modules.notification.routes.notification_routes import router as inbox_router

# New submodule API routes
from app.modules.notification.routes.core_routes import router as core_router
from app.modules.notification.routes.publisher_routes import router as publisher_router
from app.modules.notification.routes.subscriber_routes import router as subscriber_router
from app.modules.notification.routes.bus_routes import router as bus_router
from app.modules.notification.routes.delivery_routes import router as delivery_router
from app.modules.notification.routes.template_routes import router as template_router
from app.modules.notification.routes.store_routes import router as store_router
from app.modules.notification.routes.throttle_routes import router as throttle_router

# Combined router that includes all sub-routers
router = APIRouter()
router.include_router(main_router)
router.include_router(inbox_router)
router.include_router(core_router)
router.include_router(publisher_router)
router.include_router(subscriber_router)
router.include_router(bus_router)
router.include_router(delivery_router)
router.include_router(template_router)
router.include_router(store_router)
router.include_router(throttle_router)

# Events routes (merged into notification router)
from app.modules.events.routes.router import router as events_router

# Phase 3 submodule API routes
from app.modules.notification.routes.dedup_routes import router as dedup_router
from app.modules.notification.routes.routing_routes import router as routing_router
from app.modules.notification.routes.receipt_routes import router as receipt_router
router.include_router(dedup_router)
router.include_router(routing_router)
router.include_router(receipt_router)

# Phase 4 submodule API routes
from app.modules.notification.routes.campaign_routes import router as campaign_router
from app.modules.notification.routes.rule_routes import router as rule_router
from app.modules.notification.routes.schedule_routes import router as schedule_router
from app.modules.notification.routes.interactive_routes import router as interactive_router
router.include_router(campaign_router)
router.include_router(rule_router)
router.include_router(schedule_router)
router.include_router(interactive_router)

# Wire events with /events prefix
router.include_router(events_router, prefix="/events")

# Workers
from app.modules.notification.routes.worker_routes import router as worker_router
router.include_router(worker_router)

# Search
from app.modules.notification.routes.search_routes import router as search_router
router.include_router(search_router)

# Provider Config & Circuit Breaker (SSOT §22)
from app.modules.notification.routes.channel_routes import router as channel_router
router.include_router(channel_router)
