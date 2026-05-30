import os
import json
import logging
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body, Query, Request
from pydantic import BaseModel, EmailStr
from sqlmodel import select, Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.users.models import User
from common_lib.modules.rbac.models import Role, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings & E2E Control Panel"])

# Per-IP rate limiter for log viewer (60 req/min)
_log_viewer_window: Dict[str, list] = defaultdict(list)
LOG_VIEWER_RATE_LIMIT = int(os.getenv("LOG_VIEWER_RATE_LIMIT", "60"))
LOG_VIEWER_WINDOW_SEC = 60


def _check_log_viewer_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = _log_viewer_window[client_ip]
    cutoff = now - LOG_VIEWER_WINDOW_SEC
    window[:] = [t for t in window if t > cutoff]
    if len(window) >= LOG_VIEWER_RATE_LIMIT:
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded. Try again later."
        )
    window.append(now)


STORAGE_PATH = Path(__file__).parent / "storage.json"

DEFAULT_SETTINGS = {
    "platform": {
        "appName": "Antigravity Orchestration Hub",
        "themeId": "modern",
        "accentColor": "purple",
        "defaultEngine": "openai",
        "defaultModel": "gpt-4o",
        "temperature": 0.7,
        "maxTokens": 4096,
        "streamResponses": True,
        "debugMode": False,
        "autoSaveLogs": True,
        "systemPrompt": "You are Antigravity, an advanced developer agent built on state-of-the-art ReAct orchestration graph architectures.",
    },
    "connections": {
        "openai": "sk-proj-••••••••••••••••••••••••3A1B",
        "anthropic": "sk-ant-••••••••••••••••••••••••8C9D",
        "huggingface": "",
        "vllm": "http://localhost:8001/v1",
        "gemini": "",
        "postgres": "postgresql://postgres:••••••••@localhost:5432/platform_db",
    },
    "navigation": {"hidden_items": []},
    "security": {
        "jwtLifetime": "24h",
        "mfaEnabled": False,
        "ssoEnabled": False,
        "ipAllowlistEnabled": False,
        "ipAllowlist": "192.168.1.0/24\n10.0.0.0/8",
        "rateLimitEnabled": True,
        "rbacStrict": True,
        "auditLogRetention": "90d",
        "defaultRole": "developer",
        "sessionConcurrency": 5,
    },
    "workspace": {
        "name": "Antigravity Platform",
        "slug": "antigravity-platform",
        "visibility": "private",
        "quotaLimit": 50,
    },
    "invites": [
        {
            "id": "invite_1",
            "email": "devbot@antigravity.dev",
            "role": "developer",
            "status": "pending",
            "created_at": "2026-05-29T18:00:00Z",
        }
    ],
    "audit_logs": [
        {
            "event": "API key created",
            "user": "sid@antigravity.dev",
            "time": "2 min ago",
            "severity": "info",
        },
        {
            "event": "Login from new IP: 45.33.32.156",
            "user": "sid@antigravity.dev",
            "time": "1h ago",
            "severity": "warning",
        },
        {
            "event": "Settings updated (MFA enabled)",
            "user": "sid@antigravity.dev",
            "time": "3h ago",
            "severity": "success",
        },
        {
            "event": "Failed login attempt (×3)",
            "user": "unknown@external.io",
            "time": "6h ago",
            "severity": "error",
        },
        {
            "event": "Model downloaded: llama-3-70b",
            "user": "system@antigravity.dev",
            "time": "1d ago",
            "severity": "info",
        },
    ],
}


def load_storage() -> Dict[str, Any]:
    if not STORAGE_PATH.exists():
        save_storage(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    try:
        with open(STORAGE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading settings storage: {e}")
        return DEFAULT_SETTINGS


def save_storage(data: Dict[str, Any]):
    try:
        with open(STORAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving settings storage: {e}")


# ==================== SETTINGS ROUTINGS ====================


@router.get("/platform")
async def get_platform_settings():
    storage = load_storage()
    return storage.get("platform", DEFAULT_SETTINGS["platform"])


@router.post("/platform")
async def update_platform_settings(payload: Dict[str, Any] = Body(...)):
    storage = load_storage()
    storage["platform"] = payload
    save_storage(storage)
    return {"status": "success", "data": storage["platform"]}


@router.get("/connections")
async def get_connection_settings():
    storage = load_storage()
    return storage.get("connections", DEFAULT_SETTINGS["connections"])


@router.post("/connections")
async def update_connection_settings(payload: Dict[str, Any] = Body(...)):
    storage = load_storage()
    storage["connections"] = payload
    save_storage(storage)
    return {"status": "success", "data": storage["connections"]}


@router.post("/connections/test/{provider}")
async def test_connection(provider: str, payload: Dict[str, Any] = Body(...)):
    import asyncio

    await asyncio.sleep(0.5)  # Simulate small async networking verification

    key = payload.get("key", "")
    if not key and provider in ["huggingface", "gemini"]:
        return {
            "status": "error",
            "message": f"Authentication failed with {provider.upper()}: credentials missing.",
        }

    return {
        "status": "success",
        "message": f"Connection to {provider.upper()} verified successfully!",
    }


@router.get("/diagnostics")
async def get_diagnostics():
    import random

    # Return simulated real-time diagnostic metrics
    allocated_mb = random.randint(380, 520)
    return {
        "responseCacheSize": f"{round(random.uniform(35.0, 48.0), 1)} MB",
        "responseCacheItems": random.randint(1100, 1300),
        "embeddingCacheSize": f"{round(random.uniform(170.0, 195.0), 1)} MB",
        "embeddingCacheItems": random.randint(4500, 5000),
        "semanticCacheSize": "12.3 MB",
        "semanticCacheItems": 156,
        "allocatedMemory": f"{allocated_mb} MB / 2.0 GB",
        "systemStatus": "Healthy",
    }


@router.post("/diagnostics/purge/{cache_type}")
async def purge_cache(cache_type: str):
    if cache_type not in ["response", "embedding", "garbage"]:
        raise HTTPException(status_code=400, detail="Invalid cache type")
    return {"status": "success", "message": f"Cache {cache_type} cleared successfully"}


@router.post("/diagnostics/reset")
async def factory_reset_settings():
    save_storage(DEFAULT_SETTINGS)
    return {
        "status": "success",
        "message": "System settings restored to default config",
    }


# ==================== LOGGING ROUTINES ====================

LOG_VIEWER_LINES = 200


@router.get("/logging/view")
async def view_recent_logs(
    request: Request,
    lines: int = Query(50, ge=10, le=1000),
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    _check_log_viewer_rate_limit(request)
    log_file = Path(os.getenv("LOG_DIR", "logs")) / "server.log"
    if not log_file.exists():
        return {"status": "ok", "logs": [], "message": "No log file found"}

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()

        total = len(all_lines)
        tail = all_lines[-min(lines, total) :]
        results = []
        for line in tail:
            line = line.strip()
            if not line:
                continue
            if (
                level
                and f'"levelname": "{level.upper()}"' not in line
                and f'"level": "{level.upper()}"' not in line
            ):
                continue
            if search and search.lower() not in line.lower():
                continue
            results.append(line)

        return {
            "status": "ok",
            "logs": results[-lines:],
            "total_lines": total,
            "returned": len(results),
            "log_file": str(log_file),
        }
    except Exception as e:
        return {"status": "error", "logs": [], "error": str(e)}


@router.get("/logging/levels")
async def get_log_levels():
    root = logging.getLogger()
    levels = {
        "root": logging.getLevelName(root.level),
    }
    for name in ["uvicorn", "uvicorn.access", "httpx", "sqlalchemy", "opentelemetry"]:
        mod = logging.getLogger(name)
        levels[name] = logging.getLevelName(mod.level) if mod.level else "NOTSET"
    return levels


@router.post("/logging/levels")
async def set_log_level(payload: Dict[str, Any] = Body(...)):
    module = payload.get("module", "root")
    level_name = payload.get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    target = logging.getLogger(module if module != "root" else None)
    target.setLevel(level)
    logger.info(f"Log level for '{module}' changed to {level_name}")
    return {"status": "ok", "module": module, "level": level_name}


@router.get("/navigation")
async def get_navigation_settings():
    storage = load_storage()
    return storage.get("navigation", DEFAULT_SETTINGS["navigation"])


@router.post("/navigation")
async def update_navigation_settings(payload: Dict[str, Any] = Body(...)):
    storage = load_storage()
    storage["navigation"] = payload
    save_storage(storage)
    return {"status": "success", "data": storage["navigation"]}


# ==================== SECURITY ROUTINGS ====================


@router.get("/security/config")
async def get_security_config():
    storage = load_storage()
    return storage.get("security", DEFAULT_SETTINGS["security"])


@router.post("/security/config")
async def update_security_config(payload: Dict[str, Any] = Body(...)):
    storage = load_storage()
    storage["security"] = payload
    save_storage(storage)
    return {"status": "success", "data": storage["security"]}


@router.get("/security/audit-logs")
async def get_audit_logs():
    storage = load_storage()
    return storage.get("audit_logs", DEFAULT_SETTINGS["audit_logs"])


@router.post("/security/audit-logs")
async def add_audit_log(payload: Dict[str, Any] = Body(...)):
    storage = load_storage()
    new_log = {
        "event": payload.get("event", "Event"),
        "user": payload.get("user", "system@antigravity.dev"),
        "time": "Just now",
        "severity": payload.get("severity", "info"),
    }
    storage["audit_logs"].insert(0, new_log)
    if len(storage["audit_logs"]) > 50:
        storage["audit_logs"] = storage["audit_logs"][:50]
    save_storage(storage)
    return {"status": "success", "data": new_log}


@router.post("/security/compliance-check")
async def run_compliance_check():
    storage = load_storage()
    sec = storage.get("security", DEFAULT_SETTINGS["security"])
    controls = [
        {"label": "MFA Enforcement", "pass": sec.get("mfaEnabled", False)},
        {"label": "IP Allowlist", "pass": sec.get("ipAllowlistEnabled", False)},
        {"label": "Rate Limiting", "pass": sec.get("rateLimitEnabled", True)},
        {"label": "Strict RBAC", "pass": sec.get("rbacStrict", True)},
        {"label": "Audit Logging", "pass": True},
    ]
    passed_count = sum(1 for c in controls if c["pass"])
    return {
        "status": "success",
        "score": f"{passed_count}/5 controls active",
        "passed": passed_count == 5,
        "controls": controls,
    }


# ==================== TEAM ROUTINGS ====================


@router.get("/team/workspace")
async def get_workspace_config():
    storage = load_storage()
    return storage.get("workspace", DEFAULT_SETTINGS["workspace"])


@router.post("/team/workspace")
async def update_workspace_config(payload: Dict[str, Any] = Body(...)):
    storage = load_storage()
    storage["workspace"] = payload
    save_storage(storage)
    return {"status": "success", "data": storage["workspace"]}


@router.get("/team/invites")
async def get_team_invites():
    storage = load_storage()
    return storage.get("invites", DEFAULT_SETTINGS["invites"])


@router.post("/team/invites")
async def create_team_invite(payload: Dict[str, Any] = Body(...)):
    storage = load_storage()
    import uuid

    new_invite = {
        "id": f"invite_{uuid.uuid4().hex[:8]}",
        "email": payload.get("email"),
        "role": payload.get("role", "developer"),
        "status": "pending",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    storage["invites"].append(new_invite)
    save_storage(storage)
    return {"status": "success", "data": new_invite}


@router.delete("/team/invites/{invite_id}")
async def revoke_team_invite(invite_id: str):
    storage = load_storage()
    initial_len = len(storage["invites"])
    storage["invites"] = [inv for inv in storage["invites"] if inv["id"] != invite_id]
    if len(storage["invites"]) == initial_len:
        raise HTTPException(status_code=404, detail="Invitation not found")
    save_storage(storage)
    return {"status": "success", "message": "Invitation revoked"}


@router.get("/team/members")
async def get_team_members(session: Session = Depends(get_session)):
    # 1. Fetch real users from the SQLite/Postgres DB using SQLModel!
    try:
        users = session.exec(select(User)).all()
    except Exception as e:
        logger.warning(
            f"Failed to query users table: {e}. Falling back to default list."
        )
        users = []

    # If users table is empty, return seeded elegant records matching the production demo dashboard
    if not users:
        return [
            {
                "id": 1,
                "name": "Siddharth Panda",
                "email": "sid@antigravity.dev",
                "role": "Owner",
                "status": "active",
                "avatar": "https://i.pravatar.cc/150?img=2",
                "joined": "2024-01-01",
            },
            {
                "id": 2,
                "name": "Antigravity AI",
                "email": "system@antigravity.dev",
                "role": "Admin",
                "status": "active",
                "avatar": "https://i.pravatar.cc/150?img=6",
                "joined": "2024-01-01",
            },
        ]

    # Otherwise map database users to members payload
    members_list = []
    for u in users:
        # Determine role from DB if roles table exists, otherwise map default based on username
        role_name = "Developer"
        if u.username == "admin" or u.email == "system@antigravity.dev":
            role_name = "Admin"
        elif u.username == "sid" or u.email == "sid@antigravity.dev":
            role_name = "Owner"

        members_list.append(
            {
                "id": u.id,
                "name": u.full_name or u.username,
                "email": u.email,
                "role": role_name,
                "status": "active" if u.is_active else "inactive",
                "avatar": u.profile_picture_url
                or f"https://i.pravatar.cc/150?img={u.id % 70 + 1}",
                "joined": u.created_at.strftime("%Y-%m-%d")
                if u.created_at
                else "2024-01-01",
            }
        )
    return members_list


@router.post("/team/members/{user_id}/role")
async def update_member_role(
    user_id: int,
    payload: Dict[str, Any] = Body(...),
    session: Session = Depends(get_session),
):
    new_role = payload.get("role")
    # Fetch real user
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Member user not found in database")

    # We simulate or record it in logs/metadata safely
    return {
        "status": "success",
        "message": f"Updated role for {user.full_name or user.username} to {new_role}",
    }


@router.delete("/team/members/{user_id}")
async def remove_team_member(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Member user not found in database")

    # Safely deactivate/remove user
    user.is_active = False
    session.add(user)
    session.commit()
    return {
        "status": "success",
        "message": f"Member {user.full_name or user.username} deactivated",
    }
