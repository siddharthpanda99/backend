"""Module 29 — Backend Architecture & Folder Structure MCP tools."""
from typing import Any, Dict, List, Optional
from app.mcp.fastmcp_compat import FastMCP

from common_lib.modules.db_studio.backend_architecture.service import ArchitectureService

svc = ArchitectureService()


def register_backend_architecture_tools(mcp: FastMCP):
    """Register all backend architecture tools with the MCP server."""

    @mcp.tool()
    async def arch_create_setting(
        key: str, value: str,
        category: str = "general",
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a system setting"""
        from common_lib.modules.db_studio.backend_architecture.schemas import SystemSettingCreate
        req = SystemSettingCreate(key=key, value=value, category=category, description=description)
        result = svc.create_setting(req)
        return result.model_dump()

    @mcp.tool()
    async def arch_get_setting(key: str) -> Optional[Dict[str, Any]]:
        """Get a system setting by key"""
        result = svc.get_setting(key)
        return result.model_dump() if result else None

    @mcp.tool()
    async def arch_list_settings(category: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """List system settings"""
        items, total = svc.list_settings(category=category, limit=limit)
        return {"total": total, "items": [i.model_dump() for i in items]}

    @mcp.tool()
    async def arch_update_setting(key: str, value: str) -> Optional[Dict[str, Any]]:
        """Update a system setting's value"""
        result = svc.update_setting(key, value)
        return result.model_dump() if result else None

    @mcp.tool()
    async def arch_delete_setting(key: str) -> Dict[str, bool]:
        """Delete a system setting"""
        ok = svc.delete_setting(key)
        return {"ok": ok}

    @mcp.tool()
    async def arch_create_feature_flag(
        name: str, is_enabled: bool = False,
        module: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a feature flag"""
        from common_lib.modules.db_studio.backend_architecture.schemas import FeatureFlagCreate
        req = FeatureFlagCreate(name=name, description=description, is_enabled=is_enabled, module=module)
        result = svc.create_feature_flag(req)
        return result.model_dump()

    @mcp.tool()
    async def arch_list_feature_flags(
        module: Optional[str] = None, is_enabled: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """List feature flags"""
        results = svc.list_feature_flags(module=module, is_enabled=is_enabled)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def arch_toggle_feature_flag(flag_id: str, enabled: bool = True) -> Optional[Dict[str, Any]]:
        """Toggle a feature flag on/off"""
        result = svc.toggle_feature_flag(flag_id, enabled)
        return result.model_dump() if result else None

    @mcp.tool()
    async def arch_record_audit_event(
        event_type: str, source: str,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        severity: str = "info",
    ) -> Dict[str, Any]:
        """Record an audit event"""
        result = svc.record_audit_event(event_type, source, actor_id, resource_type, resource_id, severity)
        return result.model_dump()

    @mcp.tool()
    async def arch_list_audit_events(
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List audit events with optional filters"""
        results = svc.list_audit_events(event_type=event_type, source=source, severity=severity, limit=limit)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def arch_create_job(job_type: str, payload_json: Optional[str] = None) -> Dict[str, Any]:
        """Create a background job"""
        from common_lib.modules.db_studio.backend_architecture.schemas import BackgroundJobCreate
        req = BackgroundJobCreate(job_type=job_type, payload_json=payload_json)
        result = svc.create_job(req)
        return result.model_dump()

    @mcp.tool()
    async def arch_list_jobs(
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List background jobs"""
        results = svc.list_jobs(status=status, job_type=job_type, limit=limit)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def arch_update_job_status(
        job_id: str, status: str,
        progress: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a background job's status"""
        result = svc.update_job_status(job_id, status, progress)
        return result.model_dump() if result else None

    @mcp.tool()
    async def arch_register_module(
        name: str, category: str = "core",
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a module in the registry"""
        from common_lib.modules.db_studio.backend_architecture.schemas import ModuleRegistryCreate
        req = ModuleRegistryCreate(name=name, category=category, description=description)
        result = svc.register_module(req)
        return result.model_dump()

    @mcp.tool()
    async def arch_list_modules(
        category: Optional[str] = None, status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List registered modules"""
        results = svc.list_modules(category=category, status=status)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def arch_get_dashboard() -> Dict[str, Any]:
        """Get backend architecture dashboard with aggregated stats"""
        dash = svc.get_dashboard()
        return dash.model_dump()
