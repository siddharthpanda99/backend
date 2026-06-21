"""
pytest conftest for builder test fixtures.

Provides a BuilderClient helper that wraps all builder API calls using TestClient,
plus fixtures for creating shared test resources (presets, tokens, bindings).
"""

import pytest
import uuid
import json
from typing import Any, Dict, List, Optional, Generator
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session as SQLSession, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from common_lib.modules.data_storage.database.connection import get_session
from app.modules.app_builder.routes import router as builder_router

# Import all builder models so they register in SQLModel.metadata
from common_lib.modules.app_builder.models import (
    CanvasPresetRecord,
    PresetVersionRecord,
    CommentRecord,
    InteractionRecord,
    AssetRecord,
    PluginRecord,
    DataBindingRecord,
    DesignTokenRecord,
    ComponentInstanceRecord,
)
# Also import AppRecord for the foreign key reference
from common_lib.modules.app_builder.ecosystem.models import AppRecord

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Strip schemas from all ORM model tables for SQLite compatibility
for table in SQLModel.metadata.tables.values():
    table.schema = None

# Drop explicit indexes on columns with unique=True to avoid
# duplicate index creation errors on SQLite
for table in SQLModel.metadata.tables.values():
    unique_col_names = {c.name for c in table.columns if c.unique}
    for ix in list(table.indexes):
        col_names = [c.name for c in ix.columns]
        if len(col_names) == 1 and col_names[0] in unique_col_names:
            table.indexes.discard(ix)

SQLModel.metadata.create_all(engine)


def get_test_session() -> Generator[SQLSession, None, None]:
    with SQLSession(engine) as session:
        yield session


class BuilderClient:
    """Test helper wrapping all builder API endpoints."""

    def __init__(self, client: TestClient):
        self.client = client

    def _request(self, method: str, path: str, **kwargs) -> Any:
        full_path = f"/api/v1/builder{path}"
        resp = self.client.request(method, full_path, **kwargs)
        if resp.status_code >= 400:
            raise Exception(f"{resp.status_code} {resp.text[:500]}")
        return resp.json()

    def _get(self, path: str, **params) -> Any:
        return self._request("GET", path, params={k: v for k, v in params.items() if v is not None})

    def _post(self, path: str, json_data: Any = None, **params) -> Any:
        return self._request("POST", path, json=json_data, params={k: v for k, v in params.items() if v is not None})

    def _put(self, path: str, json_data: Any = None) -> Any:
        return self._request("PUT", path, json=json_data)

    def _delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    # ── Presets ──
    def create_preset(self, app_id: str, data: dict) -> Any:
        return self._post("/presets", json_data=data, app_id=app_id)

    def list_presets(self, app_id: str, category: str = None, preset_type: str = None, search: str = None) -> Any:
        return self._get("/presets", app_id=app_id, category=category, preset_type=preset_type, search=search)

    def get_preset(self, preset_id: str) -> Any:
        return self._get(f"/presets/{preset_id}")

    def update_preset(self, preset_id: str, data: dict) -> Any:
        return self._put(f"/presets/{preset_id}", json_data=data)

    def delete_preset(self, preset_id: str) -> Any:
        return self._delete(f"/presets/{preset_id}")

    def duplicate_preset(self, preset_id: str, app_id: str) -> Any:
        return self._post(f"/presets/{preset_id}/duplicate", app_id=app_id)

    # ── Canvas State ──
    def get_canvas_state(self, app_id: str) -> Any:
        return self._get(f"/canvas/{app_id}")

    def save_canvas_state(self, app_id: str, presets: List[dict]) -> Any:
        return self._post(f"/canvas/{app_id}", json_data={"presets": presets, "app_id": app_id})

    # ── Tokens ──
    def create_token(self, app_id: str, data: dict) -> Any:
        return self._post("/tokens", json_data=data, app_id=app_id)

    def list_tokens(self, app_id: str, token_type: str = None, mode: str = None, namespace: str = None) -> Any:
        return self._get("/tokens", app_id=app_id, token_type=token_type, mode=mode, namespace=namespace)

    def update_token(self, token_id: str, data: dict) -> Any:
        return self._put(f"/tokens/{token_id}", json_data=data)

    def delete_token(self, token_id: str) -> Any:
        return self._delete(f"/tokens/{token_id}")

    # ── Bindings ──
    def create_binding(self, app_id: str, data: dict) -> Any:
        return self._post("/bindings", json_data=data, app_id=app_id)

    def list_bindings(self, app_id: str, preset_id: str = None) -> Any:
        return self._get("/bindings", app_id=app_id, preset_id=preset_id)

    def update_binding(self, binding_id: str, data: dict) -> Any:
        return self._put(f"/bindings/{binding_id}", json_data=data)

    def delete_binding(self, binding_id: str) -> Any:
        return self._delete(f"/bindings/{binding_id}")

    def test_binding(self, data: dict) -> Any:
        return self._post("/bindings/test", json_data=data)

    def test_existing_binding(self, binding_id: str) -> Any:
        return self._post(f"/bindings/{binding_id}/test")

    # ── Layout ──
    def compute_layout(self, presets: List[dict], auto_layout: dict = None, constraints: dict = None,
                       parent_width: float = 0, parent_height: float = 0,
                       old_parent_width: float = None, old_parent_height: float = None) -> Any:
        data = {
            "presets": presets,
            "auto_layout": auto_layout,
            "constraints": constraints,
            "parent_width": parent_width,
            "parent_height": parent_height,
        }
        if old_parent_width is not None:
            data["old_parent_width"] = old_parent_width
        if old_parent_height is not None:
            data["old_parent_height"] = old_parent_height
        return self._post("/layout/compute", json_data=data)

    # ── Seed ──
    def seed_data(self, app_id: str) -> Any:
        return self._post(f"/seed/{app_id}")

    # ── Versions (NEW) ──
    def create_version(self, app_id: str, data: dict) -> Any:
        return self._post("/versions", json_data=data, app_id=app_id)

    def list_versions(self, app_id: str, preset_id: str = None) -> Any:
        return self._get("/versions", app_id=app_id, preset_id=preset_id)

    def get_version(self, version_id: str) -> Any:
        return self._get(f"/versions/{version_id}")

    def delete_version(self, version_id: str) -> Any:
        return self._delete(f"/versions/{version_id}")

    # ── Comments (NEW) ──
    def create_comment(self, app_id: str, data: dict) -> Any:
        return self._post("/comments", json_data=data, app_id=app_id)

    def list_comments(self, app_id: str, preset_id: str = None, resolved: bool = None) -> Any:
        return self._get("/comments", app_id=app_id, preset_id=preset_id, resolved=resolved)

    def update_comment(self, comment_id: str, data: dict) -> Any:
        return self._put(f"/comments/{comment_id}", json_data=data)

    def delete_comment(self, comment_id: str) -> Any:
        return self._delete(f"/comments/{comment_id}")

    # ── Interactions (NEW) ──
    def create_interaction(self, app_id: str, data: dict) -> Any:
        return self._post("/interactions", json_data=data, app_id=app_id)

    def list_interactions(self, app_id: str, source_preset_id: str = None, trigger_type: str = None) -> Any:
        return self._get("/interactions", app_id=app_id, source_preset_id=source_preset_id, trigger_type=trigger_type)

    def update_interaction(self, interaction_id: str, data: dict) -> Any:
        return self._put(f"/interactions/{interaction_id}", json_data=data)

    def delete_interaction(self, interaction_id: str) -> Any:
        return self._delete(f"/interactions/{interaction_id}")

    # ── Assets (NEW) ──
    def create_asset(self, app_id: str, data: dict) -> Any:
        return self._post("/assets", json_data=data, app_id=app_id)

    def list_assets(self, app_id: str, category: str = None, mime_type: str = None) -> Any:
        return self._get("/assets", app_id=app_id, category=category, mime_type=mime_type)

    def get_asset(self, asset_id: str) -> Any:
        return self._get(f"/assets/{asset_id}")

    def delete_asset(self, asset_id: str) -> Any:
        return self._delete(f"/assets/{asset_id}")

    # ── Plugins (NEW) ──
    def create_plugin(self, app_id: str, data: dict) -> Any:
        return self._post("/plugins", json_data=data, app_id=app_id)

    def list_plugins(self, app_id: str, plugin_type: str = None, enabled: bool = None) -> Any:
        return self._get("/plugins", app_id=app_id, plugin_type=plugin_type, enabled=enabled)

    def update_plugin(self, plugin_id: str, data: dict) -> Any:
        return self._put(f"/plugins/{plugin_id}", json_data=data)

    def delete_plugin(self, plugin_id: str) -> Any:
        return self._delete(f"/plugins/{plugin_id}")


@pytest.fixture(scope="session")
def test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(builder_router, prefix="/api/v1")
    app.dependency_overrides[get_session] = get_test_session
    return app


@pytest.fixture(scope="session")
def test_client(test_app) -> TestClient:
    return TestClient(test_app)


@pytest.fixture(scope="session")
def builder_client(test_client) -> BuilderClient:
    """Shared BuilderClient for all tests."""
    return BuilderClient(test_client)


@pytest.fixture
def created_preset_id(builder_client) -> str:
    """Create a preset and yield its ID, clean up after."""
    import uuid
    app_id = f"test-app-{uuid.uuid4().hex[:8]}"
    
    # Seed the app in ecosystem_apps first to satisfy foreign key constraint
    with SQLSession(engine) as db:
        app_rec = AppRecord(id=app_id, name="Test App", description="Auto-created for testing")
        db.add(app_rec)
        db.commit()

    preset_data = {
        "name": "Test Button",
        "preset_type": "component",
        "icon": "🔘",
        "description": "A test button preset",
        "layout": {"x": 100, "y": 200, "width": 160, "height": 48, "zIndex": 10, "locked": False, "rotation": 0},
        "style": {"background": "#6366f1", "color": "#ffffff", "fontSize": "14px", "fontWeight": 600},
        "tags": ["test", "button"],
        "author": "Test Runner",
    }
    resp = builder_client.create_preset(app_id, preset_data)
    preset_id = resp["data"]["id"]
    yield preset_id
    try:
        builder_client.delete_preset(preset_id)
    except Exception:
        pass


@pytest.fixture
def created_token_id(builder_client) -> str:
    """Create a design token and yield its ID."""
    import uuid
    app_id = f"test-app-{uuid.uuid4().hex[:8]}"
    
    # Seed the app in ecosystem_apps first to satisfy foreign key constraint
    with SQLSession(engine) as db:
        app_rec = AppRecord(id=app_id, name="Test App", description="Auto-created for testing")
        db.add(app_rec)
        db.commit()

    token_data = {"name": "fixture.color", "token_type": "color", "value": "#ff0000"}
    resp = builder_client.create_token(app_id, token_data)
    token_id = resp["data"]["id"]
    yield token_id
    try:
        builder_client.delete_token(token_id)
    except Exception:
        pass


@pytest.fixture
def created_binding_id(builder_client) -> str:
    """Create a data binding and yield its ID."""
    import uuid
    app_id = f"test-app-{uuid.uuid4().hex[:8]}"
    preset_id = f"fixture-preset-{uuid.uuid4().hex[:8]}"
    
    # Seed the app in ecosystem_apps and preset in builder_canvas_presets first to satisfy foreign key constraints
    with SQLSession(engine) as db:
        app_rec = AppRecord(id=app_id, name="Test App", description="Auto-created for testing")
        db.add(app_rec)
        preset_rec = CanvasPresetRecord(id=preset_id, app_id=app_id, name="Fixture Preset", layout={})
        db.add(preset_rec)
        db.commit()

    binding_data = {
        "preset_id": preset_id,
        "source_type": "mock_json",
        "mock_data": '{"test": true}',
    }
    resp = builder_client.create_binding(app_id, binding_data)
    binding_id = resp["data"]["id"]
    yield binding_id
    try:
        builder_client.delete_binding(binding_id)
    except Exception:
        pass


@pytest.fixture
def created_version_id(builder_client) -> str:
    """Create a version and yield its ID."""
    import uuid
    app_id = f"test-app-{uuid.uuid4().hex[:8]}"
    preset_id = f"fixture-preset-{uuid.uuid4().hex[:8]}"
    
    # Seed the app and preset first to satisfy foreign keys
    with SQLSession(engine) as db:
        app_rec = AppRecord(id=app_id, name="Test App", description="Auto-created for testing")
        db.add(app_rec)
        preset_rec = CanvasPresetRecord(id=preset_id, app_id=app_id, name="Fixture Preset", layout={})
        db.add(preset_rec)
        db.commit()

    version_data = {"preset_id": preset_id, "label": "v1", "author": "test"}
    resp = builder_client.create_version(app_id, version_data)
    version_id = resp["data"]["id"]
    yield version_id
    try:
        builder_client.delete_version(version_id)
    except Exception:
        pass


@pytest.fixture
def created_comment_id(builder_client) -> str:
    """Create a comment and yield its ID."""
    import uuid
    app_id = f"test-app-{uuid.uuid4().hex[:8]}"
    preset_id = f"fixture-preset-{uuid.uuid4().hex[:8]}"
    
    # Seed the app and preset first to satisfy foreign keys
    with SQLSession(engine) as db:
        app_rec = AppRecord(id=app_id, name="Test App", description="Auto-created for testing")
        db.add(app_rec)
        preset_rec = CanvasPresetRecord(id=preset_id, app_id=app_id, name="Fixture Preset", layout={})
        db.add(preset_rec)
        db.commit()

    comment_data = {"preset_id": preset_id, "author": "tester", "content": "Fixture comment"}
    resp = builder_client.create_comment(app_id, comment_data)
    comment_id = resp["data"]["id"]
    yield comment_id
    try:
        builder_client.delete_comment(comment_id)
    except Exception:
        pass


@pytest.fixture
def created_interaction_id(builder_client) -> str:
    """Create an interaction and yield its ID."""
    import uuid
    app_id = f"test-app-{uuid.uuid4().hex[:8]}"
    preset_id = f"fixture-preset-{uuid.uuid4().hex[:8]}"
    
    # Seed the app and preset first to satisfy foreign keys
    with SQLSession(engine) as db:
        app_rec = AppRecord(id=app_id, name="Test App", description="Auto-created for testing")
        db.add(app_rec)
        preset_rec = CanvasPresetRecord(id=preset_id, app_id=app_id, name="Fixture Preset", layout={})
        db.add(preset_rec)
        db.commit()

    interaction_data = {"source_preset_id": preset_id, "name": "Fixture interaction", "trigger_type": "click", "action_type": "navigate"}
    resp = builder_client.create_interaction(app_id, interaction_data)
    interaction_id = resp["data"]["id"]
    yield interaction_id
    try:
        builder_client.delete_interaction(interaction_id)
    except Exception:
        pass


@pytest.fixture
def created_asset_id(builder_client) -> str:
    """Create an asset and yield its ID."""
    import uuid
    app_id = f"test-app-{uuid.uuid4().hex[:8]}"
    
    # Seed the app first to satisfy foreign key
    with SQLSession(engine) as db:
        app_rec = AppRecord(id=app_id, name="Test App", description="Auto-created for testing")
        db.add(app_rec)
        db.commit()

    asset_data = {
        "name": "Test Logo",
        "file_name": "logo.png",
        "file_path": "/assets/test/logo.png",
        "file_size": 102400,
        "mime_type": "image/png",
        "category": "image",
        "tags": ["logo"]
    }
    resp = builder_client.create_asset(app_id, asset_data)
    asset_id = resp["data"]["id"]
    yield asset_id
    try:
        builder_client.delete_asset(asset_id)
    except Exception:
        pass


@pytest.fixture
def created_plugin_id(builder_client) -> str:
    """Create a plugin and yield its ID."""
    import uuid
    app_id = f"test-app-{uuid.uuid4().hex[:8]}"
    
    # Seed the app first to satisfy foreign key
    with SQLSession(engine) as db:
        app_rec = AppRecord(id=app_id, name="Test App", description="Auto-created for testing")
        db.add(app_rec)
        db.commit()

    plugin_data = {"name": "fixture-plugin", "plugin_type": "render", "manifest": {"version": "1.0.0"}, "enabled": True}
    resp = builder_client.create_plugin(app_id, plugin_data)
    plugin_id = resp["data"]["id"]
    yield plugin_id
    try:
        builder_client.delete_plugin(plugin_id)
    except Exception:
        pass
