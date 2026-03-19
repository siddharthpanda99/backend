import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.core.settings import get_settings
from app.core.openapi import custom_openapi

# Import Routers
# Import Routers
from app.modules.common.routes.index import router as common_router
from app.modules.auth.routes.index import router as auth_router
from app.modules.sessions.routes.index import router as sessions_router
from app.modules.authorization.routes.roles import router as roles_router
from app.modules.authorization.routes.permissions import router as permissions_router
from app.modules.users.routes.users import router as users_router
from app.modules.projects.routes.projects import router as projects_router
from app.modules.agents.routes.index import router as agents_router
from app.modules.workflows.routes.index import router as workflows_router
from app.modules.tools.routes.index import router as tools_router
from app.modules.memories.routes.index import router as memories_router
from app.modules.demo.routes.react_agent import router as demo_react_router
from fastapi import Depends
from app.modules.auth.dependencies.index import get_current_active_user

settings = get_settings()

import sys
import time
from sqlalchemy import text
from app.modules.database.service.connection import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Verify Database Connection
    max_retries = 4
    retry_interval = 2
    
    for attempt in range(max_retries):
        try:
            print(f"Startup: Verifying database connection (Attempt {attempt + 1}/{max_retries})...")
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("Database connection established successfully.")
            
            from app.modules.database.service.connection import init_db
            init_db()
            print("Database initialized and models registered.")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Warning: Database connection failed. Retrying in {retry_interval} seconds...")
                print(f"Error: {e}")
                time.sleep(retry_interval)
            else:
                print("="*60)
                print(f"CRITICAL ERROR: Could not connect to the database after {max_retries} attempts.")
                print(f"Please ensure the database server is running at {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}.")
                print(f"Detailed Error: {e}")
                print("="*60)
                sys.exit(1)
        
    yield
    # Shutdown
    engine.dispose()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=settings.OPENAPI_URL,
        docs_url=settings.DOCS_URL,
        redoc_url=settings.REDOC_URL,
        lifespan=lifespan
    )

    # Set all CORS enabled origins
    # Set all CORS enabled origins
    # Using allow_origin_regex to allow any origin with credentials (safe for dev, restrict in prod if needed)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex="https?://.*", 
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Custom OpenAPI
    app.openapi = lambda: custom_openapi(app)

    # Include Routers
    app.include_router(common_router, prefix=settings.API_V1_STR)
    app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"]) # Auth handles its own security
    app.include_router(sessions_router, prefix=f"{settings.API_V1_STR}/sessions", tags=["Sessions"], dependencies=[Depends(get_current_active_user)])
    
    # Module Routers
    app.include_router(roles_router, prefix=f"{settings.API_V1_STR}/roles", tags=["Roles"], dependencies=[Depends(get_current_active_user)])
    app.include_router(permissions_router, prefix=f"{settings.API_V1_STR}/permissions", tags=["Permissions"], dependencies=[Depends(get_current_active_user)])
    app.include_router(users_router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"], dependencies=[Depends(get_current_active_user)])
    app.include_router(projects_router, prefix=f"{settings.API_V1_STR}/projects", tags=["Projects"], dependencies=[Depends(get_current_active_user)])

    # Entities
    app.include_router(agents_router, prefix=f"{settings.API_V1_STR}/agents", tags=["Agents"], dependencies=[Depends(get_current_active_user)])
    app.include_router(workflows_router, prefix=f"{settings.API_V1_STR}/workflows", tags=["Workflows"])
    app.include_router(tools_router, prefix=f"{settings.API_V1_STR}/tools", tags=["Tools"], dependencies=[Depends(get_current_active_user)])
    app.include_router(memories_router, prefix=f"{settings.API_V1_STR}/memories", tags=["Memories"], dependencies=[Depends(get_current_active_user)])
    
    # New Vision API
    from app.modules.vision.routes import router as vision_router
    app.include_router(vision_router, prefix=f"{settings.API_V1_STR}/vision", tags=["Vision"])

    # Demo
    app.include_router(demo_react_router, prefix=f"{settings.API_V1_STR}/demo", tags=["Demo"])

    # Serve generated images as static files
    generated_content_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_content")
    os.makedirs(generated_content_dir, exist_ok=True)
    app.mount("/generated", StaticFiles(directory=generated_content_dir), name="generated")

    # Exception Handlers
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from sqlalchemy.exc import SQLAlchemyError
    from app.core.exceptions import (
        NexusException,
        nexus_exception_handler,
        validation_exception_handler,
        pydantic_exception_handler,
        sqlalchemy_exception_handler,
        generic_exception_handler,
        http_exception_handler
    )
    
    app.add_exception_handler(NexusException, nexus_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    from pydantic import ValidationError
    app.add_exception_handler(ValidationError, pydantic_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
