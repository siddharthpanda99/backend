"""Secrets Manager API Routes package."""
from app.modules.secrets_manager.routes.vault_routes import router as vault_router
from app.modules.secrets_manager.routes.policy_routes import router as policy_router
from app.modules.secrets_manager.routes.core_routes import router as core_router
from app.modules.secrets_manager.routes.audit_routes import router as audit_router
from app.modules.secrets_manager.routes.dynamic_routes import router as dynamic_router
from app.modules.secrets_manager.routes.rotation_routes import router as rotation_router
from app.modules.secrets_manager.routes.pki_routes import router as pki_router
from app.modules.secrets_manager.routes.ssh_routes import router as ssh_router
from app.modules.secrets_manager.routes.proxy_routes import router as proxy_router
from app.modules.secrets_manager.routes.kubernetes_routes import router as kubernetes_router
from app.modules.secrets_manager.routes.cloud_routes import router as cloud_router
from app.modules.secrets_manager.routes.seal_routes import router as seal_router
from app.modules.secrets_manager.routes.engine_routes import router as engine_router
from app.modules.secrets_manager.routes.event_routes import router as event_router
from app.modules.secrets_manager.routes.scanning_routes import router as scanning_router
from app.modules.secrets_manager.routes.replication_routes import router as replication_router
from app.modules.secrets_manager.routes.plugin_routes import router as plugin_router
from app.modules.secrets_manager.routes.monitoring_routes import router as monitoring_router
from app.modules.secrets_manager.routes.import_export_routes import router as import_export_router

__all__ = [
    "vault_router", "policy_router", "core_router", "audit_router",
    "dynamic_router", "rotation_router", "pki_router", "ssh_router",
    "proxy_router", "kubernetes_router", "cloud_router",
    "seal_router", "engine_router", "event_router",
    "scanning_router", "replication_router", "plugin_router",
    "monitoring_router", "import_export_router",
]
