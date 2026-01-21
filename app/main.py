from fastapi import FastAPI
from app.core.settings import get_settings
from app.core.openapi import custom_openapi

# Import Routers
# Import Routers
from app.modules.common.routes.index import router as common_router
from app.modules.auth.routes.index import router as auth_router
from app.modules.sessions.routes.index import router as sessions_router

settings = get_settings()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=settings.OPENAPI_URL,
        docs_url=settings.DOCS_URL,
        redoc_url=settings.REDOC_URL,
    )

    # Register Custom OpenAPI
    app.openapi = lambda: custom_openapi(app)

    # Include Routers
    app.include_router(common_router, prefix=settings.API_V1_STR)
    app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
    app.include_router(sessions_router, prefix=f"{settings.API_V1_STR}/sessions", tags=["Sessions"])

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
