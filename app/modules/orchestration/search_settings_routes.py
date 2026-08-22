"""Search Settings API — per-session search configuration that affects agent runtime.

Endpoints:
    GET  /api/v1/agents/search-settings/{session_id}   — Get search settings
    PUT  /api/v1/agents/search-settings/{session_id}   — Update search settings
    POST /api/v1/agents/search-settings/{session_id}/reset — Reset to defaults
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SearchSettingsUpdate(BaseModel):
    """Partial update for search settings."""
    global_settings: Optional[Dict[str, Any]] = None
    feature_flags: Optional[Dict[str, str]] = None
    source_flags: Optional[Dict[str, bool]] = None
    source_numerics: Optional[Dict[str, int]] = None
    profile: Optional[str] = None


class SearchSettingsResponse(BaseModel):
    """Full search settings for a session."""
    session_id: str
    global_settings: Dict[str, Any] = Field(default_factory=lambda: {
        "pipeline": "hybrid",
        "max_layers": 3,
        "token_budget": 8000,
        "top_k": 10,
        "rerank_enabled": True,
        "external_search_enabled": False,
    })
    feature_flags: Dict[str, str] = Field(default_factory=dict)
    source_flags: Dict[str, bool] = Field(default_factory=dict)
    source_numerics: Dict[str, int] = Field(default_factory=dict)
    profile: str = "production"


# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS: Dict[str, Any] = {
    "global_settings": {
        "pipeline": "hybrid",
        "max_layers": 3,
        "token_budget": 8000,
        "top_k": 10,
        "rerank_enabled": True,
        "external_search_enabled": False,
    },
    "feature_flags": {},
    "source_flags": {},
    "source_numerics": {},
    "profile": "production",
}

# In-memory session settings store (production would use Redis/DB)
_session_settings: Dict[str, Dict[str, Any]] = {}


def _get_session_config(session_id: str) -> Dict[str, Any]:
    """Get or create search settings for a session."""
    if session_id not in _session_settings:
        _session_settings[session_id] = {
            "global_settings": dict(DEFAULT_SETTINGS["global_settings"]),
            "feature_flags": {},
            "source_flags": {},
            "source_numerics": {},
            "profile": "production",
        }
    return _session_settings[session_id]


def get_search_settings_for_session(session_id: str) -> Dict[str, Any]:
    """Public accessor — used by the agent runtime to read search settings.

    This is the bridge between the REST API and the agent's search tool.
    The agent calls this to get the current search configuration before
    executing a search.
    """
    return _get_session_config(session_id)


def apply_search_settings_to_agent_ctx(ctx: Any, session_id: str) -> None:
    """Apply search settings to the agent's PluginContext.

    Called once at session start to wire search settings into the agent runtime.
    The search tool reads from ctx.session_config["search_settings"].
    """
    settings = get_search_settings_for_session(session_id)

    if not hasattr(ctx, "session_config") or ctx.session_config is None:
        ctx.session_config = {}

    ctx.session_config["search_settings"] = settings

    # Also flatten key settings for easy access by search tools
    gs = settings.get("global_settings", {})
    ctx.session_config["search_top_k"] = gs.get("top_k", 10)
    ctx.session_config["search_rerank"] = gs.get("rerank_enabled", True)
    ctx.session_config["search_max_layers"] = gs.get("max_layers", 3)
    ctx.session_config["search_external"] = gs.get("external_search_enabled", False)
    ctx.session_config["search_pipeline"] = gs.get("pipeline", "hybrid")

    logger.debug(
        f"Applied search settings to agent ctx for session {session_id}: "
        f"top_k={gs.get('top_k')}, rerank={gs.get('rerank_enabled')}, "
        f"pipeline={gs.get('pipeline')}"
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{session_id}")
async def get_search_settings(session_id: str) -> SearchSettingsResponse:
    """Get search settings for a session."""
    settings = _get_session_config(session_id)
    return SearchSettingsResponse(session_id=session_id, **settings)


@router.put("/{session_id}")
async def update_search_settings(
    session_id: str,
    update: SearchSettingsUpdate,
) -> SearchSettingsResponse:
    """Update search settings for a session (partial update)."""
    settings = _get_session_config(session_id)

    if update.global_settings is not None:
        settings["global_settings"].update(update.global_settings)

    if update.feature_flags is not None:
        settings["feature_flags"].update(update.feature_flags)

    if update.source_flags is not None:
        settings["source_flags"].update(update.source_flags)

    if update.source_numerics is not None:
        settings["source_numerics"].update(update.source_numerics)

    if update.profile is not None:
        settings["profile"] = update.profile

    # Re-apply to any active agent context for this session
    try:
        from common_lib.modules.orchestration.plugin import get_context
        ctx = get_context()
        apply_search_settings_to_agent_ctx(ctx, session_id)
    except Exception:
        pass  # Agent may not be active — settings stored for next session

    return SearchSettingsResponse(session_id=session_id, **settings)


@router.post("/{session_id}/reset")
async def reset_search_settings(session_id: str) -> SearchSettingsResponse:
    """Reset search settings to defaults."""
    _session_settings[session_id] = {
        "global_settings": dict(DEFAULT_SETTINGS["global_settings"]),
        "feature_flags": {},
        "source_flags": {},
        "source_numerics": {},
        "profile": "production",
    }
    settings = _session_settings[session_id]
    return SearchSettingsResponse(session_id=session_id, **settings)
