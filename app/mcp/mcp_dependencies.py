from app.modules.memories.dependencies import get_memory_service
from common_lib.modules.agents.service import agent_service
from common_lib.modules.memory.service import MemoryService
from common_lib.modules.system.service import SystemService
from common_lib.modules.ai_models.container import AIModelsContainer
from common_lib.modules.projects.service import ProjectService
from common_lib.modules.data_storage.database.connection import get_session

def resolve_db_session():
    """Helper to get a database session."""
    return next(get_session())

def resolve_memory_service() -> MemoryService:
    """Helper to get memory service outside of FastAPI request context."""
    return get_memory_service()

def resolve_agent_service():
    """Helper to get agent service."""
    return agent_service

def resolve_system_service() -> SystemService:
    """Helper to get system service."""
    return SystemService()

def resolve_model_container() -> AIModelsContainer:
    """Helper to get AI models container."""
    return AIModelsContainer()

def resolve_project_service() -> ProjectService:
    """Helper to get project service."""
    # We need a session, so we call get_session and get the next item
    session = next(get_session())
    return ProjectService(session)

def resolve_fleet_manager():
    """Helper to get vLLM fleet manager."""
    from common_lib.modules.ai_models.llm.vllm_fleet_manager import vllm_fleet
    return vllm_fleet

def resolve_runtime_session():
    """Helper to get active agent session."""
    from app.modules.agents.runtime.core import get_active_session
    return get_active_session()

def resolve_master_agent():
    """Helper to get master agent instance."""
    from app.modules.agents.runtime.core import get_master_agent
    return get_master_agent()

def resolve_engine_manager():
    """Helper to get engine manager."""
    from app.modules.agents.runtime.core import get_engine_manager
    return get_engine_manager()

def resolve_vision_controller():
    """Helper to get vision task controller."""
    from app.modules.vision.routes import controller
    return controller

def resolve_audio_service():
    """Helper to get audio service."""
    from common_lib.modules.audio.service import audio_service
    return audio_service

def resolve_data_forge_engine():
    """Helper to get data forge engine."""
    from app.modules.data_forge.routes import data_forge_engine
    return data_forge_engine

def resolve_graph_projector():
    """Helper to get knowledge base graph projector."""
    from common_lib.modules.orchestration.knowledgebase.projection.projector import KnowledgeBaseGraphProjector
    return KnowledgeBaseGraphProjector()

def resolve_plugin_manager():
    """Helper to get plugin manager."""
    from app.modules.plugins.routes.router import plugin_manager
    return plugin_manager

def resolve_notification_service():
    """Helper to get notification bridge."""
    from common_lib.modules.notification.controller import notify, event_bus
    return {"notify": notify, "event_bus": event_bus}

def resolve_daw_service():
    """Helper to get DAW service."""
    from common_lib.modules.daw.service import daw_service
    return daw_service

def resolve_dip_service():
    """Helper to get DIP service."""
    from common_lib.modules.dip.service import dip_service
    return dip_service

def resolve_user_service():
    """Helper to get user service."""
    from app.modules.users.service.users import user_service
    return user_service

def resolve_session_service():
    """Helper to get session service."""
    from app.modules.sessions.service.sessions import session_service
    return session_service

def resolve_agent_service():
    """Helper to get agent service."""
    from common_lib.modules.agents.service import agent_service
    return agent_service

def resolve_runtime_session():
    """Helper to get the current runtime session metadata."""
    from app.modules.agents.runtime.core.session_manager import session_manager
    return session_manager.get_active_session()

def resolve_master_agent():
    """Helper to get the master agent instance."""
    from app.modules.agents.runtime.core.orchestrator import orchestrator
    return orchestrator.master_agent

def resolve_engine_manager():
    """Helper to get the inference engine manager."""
    from common_lib.modules.orchestration.inference.manager import engine_manager
    return engine_manager
