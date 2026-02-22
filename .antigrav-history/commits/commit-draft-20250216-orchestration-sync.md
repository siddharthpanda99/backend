Commit message
refactor(backend): decouple api from common_lib database

Summary
- Created `app.core.common_lib_integration.py` to host global `common_lib` MemoryStore and Sync Manager dependencies for API usage
- Refactored `AgentService`, `WorkflowService`, `ToolService`, and `MemoryService` methods to query and persist their respective entities through `SQLAlchemyMemoryStore` 
- Appended `sync_entity_to_fs` calls into every `create` and `update` API service methods, establishing immediate, bi-directional entity syncing back to the filesystem representation
- Removed SQLAlchemy `db: Session` context dependencies from Fastapi route endpoints, creating thin clients 
- Stripped orchestration mapping code from `database/service/connection.py`, completely uncoupling the backend schema DB and the logic DB

Risk
Low - No data was transformed or logic significantly rewritten, but purely mapped. Integration manually verified using unit imports.

Files changed
- app.core.common_lib_integration.py
- app.modules.agents.service.index.py
- app.modules.agents.routes.index.py
- app.modules.workflows.service.index.py
- app.modules.workflows.routes.index.py
- app.modules.tools.service.index.py
- app.modules.tools.routes.index.py
- app.modules.memories.service.index.py
- app.modules.memories.routes.index.py
- app.modules.database.service.connection.py
