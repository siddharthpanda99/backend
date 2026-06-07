from app.modules.connectors.routes.connector_routes import router as connector_router
from app.modules.connectors.routes.connection_routes import router as connection_router

__all__ = [
    "connector_router",
    "connection_router",
]
