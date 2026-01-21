from fastapi.openapi.utils import get_openapi
from app.core.settings import get_settings

settings = get_settings()

def custom_openapi(app):
    if app.openapi_schema:
        return app.openapi_schema
    
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
    
    # Customizing the schema for Agents
    # Example: Ensure operationIds are clean and predictable
    for path, path_item in openapi_schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if "operationId" not in operation:
                operation["operationId"] = f"{method}_{path}"
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema
