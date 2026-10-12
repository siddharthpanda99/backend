from fastapi.openapi.utils import get_openapi
from app.core.settings import get_settings

settings = get_settings()

def custom_openapi(app):
    if app.openapi_schema:
        return app.openapi_schema
    
    try:
        openapi_schema = get_openapi(
            title=settings.PROJECT_NAME,
            version=settings.VERSION,
            description="""
            # Nexus AI Backend API
            
            This API is designed to be consumed by **AI Agents**.
            
            ## Features
            - **Modular Architecture**: separate modules for Auth, Users, etc.
            - **Detailed Metadata**: endpoints contain `operationId` and `summary` for better agent reasoning.
            
            ## Usage
            Agents should look at the tags to understand the context of capabilities.
            """,
            routes=app.routes,
        )
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "get_openapi failed — serving minimal schema"
        )
        # Return a minimal valid OpenAPI schema
        openapi_schema = {
            "openapi": "3.0.2",
            "info": {
                "title": settings.PROJECT_NAME,
                "version": settings.VERSION,
            },
            "paths": {},
        }
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    # Customizing the schema for Agents
    # Example: Ensure operationIds are clean and predictable.
    # Wrapped defensively: a single malformed route must not 500 /openapi.json.
    try:
        for path, path_item in openapi_schema.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if not isinstance(operation, dict):
                    continue
                if "operationId" not in operation:
                    operation["operationId"] = f"{method}_{path}"
    except Exception:
        import logging as _logging

        _logging.getLogger(__name__).exception(
            "custom_openapi post-processing failed — serving uncustomized schema"
        )
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema
