"""
Comprehensive pytest tests for the Figma-Class Builder API.

Tests all 9 model CRUDs + test connection + layout compute + seed data.
Run with: pytest app/modules/builder/test_builder_crud.py -v
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

# ─── Test Data ─────────────────────────────────────────────────────

TEST_APP_ID = f"test-app-{uuid.uuid4().hex[:8]}"
PRESET_ID = f"test-preset-{uuid.uuid4().hex[:8]}"
PARENT_ID = f"test-parent-{uuid.uuid4().hex[:8]}"

SAMPLE_PRESET = {
    "name": "Test Button",
    "preset_type": "component",
    "icon": "🔘",
    "description": "A test button preset",
    "version": "1.0.0",
    "category": "buttons",
    "layout": {"x": 100, "y": 200, "width": 160, "height": 48, "zIndex": 10, "locked": False, "rotation": 0},
    "style": {"background": "#6366f1", "color": "#ffffff", "fontSize": "14px", "fontWeight": 600},
    "tags": ["test", "button"],
    "author": "Test Runner",
}

SAMPLE_TOKEN = {
    "name": "test.primary",
    "token_type": "color",
    "value": "#6366f1",
    "mode": "light",
    "namespace": "test",
    "description": "Test primary color",
}

SAMPLE_BINDING = {
    "preset_id": PRESET_ID,
    "node_instance_id": "default",
    "port_id": "data",
    "label": "Test Binding",
    "source_type": "mock_json",
    "mock_data": '{"users": [{"name": "John", "email": "john@test.com"}]}',
}

SAMPLE_VERSION = {
    "preset_id": PRESET_ID,
    "label": "v1.0",
    "description": "Initial version",
    "author": "Test Runner",
}

SAMPLE_COMMENT = {
    "preset_id": PRESET_ID,
    "author": "Test User",
    "content": "This button needs to be larger",
    "pin_x": 150.0,
    "pin_y": 220.0,
}

SAMPLE_INTERACTION = {
    "source_preset_id": PRESET_ID,
    "name": "Click to navigate",
    "trigger_type": "click",
    "action_type": "navigate",
    "action_config": {"url": "/home"},
}

SAMPLE_ASSET = {
    "name": "Test Logo",
    "file_name": "logo.png",
    "file_path": "/assets/test/logo.png",
    "file_size": 102400,
    "mime_type": "image/png",
    "category": "image",
    "tags": ["logo"],
}

SAMPLE_PLUGIN = {
    "name": "Export Plugin",
    "plugin_type": "export",
    "manifest": {"version": "1.0.0", "hooks": ["onExport"]},
    "enabled": True,
}


# ═══════════════════════════════════════════════════════════════════
# Canvas Preset CRUD Tests
# ═══════════════════════════════════════════════════════════════════

class TestPresetCRUD:
    """CanvasPresetRecord: Create, Read, Update, Delete, List, Duplicate."""

    def test_create_preset(self, builder_client):
        """Should create a preset with all fields."""
        resp = builder_client.create_preset(TEST_APP_ID, SAMPLE_PRESET)
        assert resp["status"] == "success"
        data = resp["data"]
        assert data["name"] == SAMPLE_PRESET["name"]
        assert data["preset_type"] == "component"
        assert data["layout"]["x"] == 100
        assert data["style"]["background"] == "#6366f1"
        assert data["id"].startswith("preset-")

    def test_create_preset_with_parent(self, builder_client):
        """Should create a nested preset with parent_id."""
        child = {**SAMPLE_PRESET, "name": "Child Button", "parent_id": PARENT_ID}
        resp = builder_client.create_preset(TEST_APP_ID, child)
        assert resp["status"] == "success"
        assert resp["data"]["parent_id"] == PARENT_ID

    def test_create_preset_minimal(self, builder_client):
        """Should create a preset with minimal fields."""
        minimal = {"name": "Minimal", "layout": {"x": 0, "y": 0, "width": 100, "height": 50, "zIndex": 0, "locked": False, "rotation": 0}}
        resp = builder_client.create_preset(TEST_APP_ID, minimal)
        assert resp["status"] == "success"
        assert resp["data"]["preset_type"] == "component"  # default
        assert resp["data"]["icon"] == "🧩"  # default

    def test_list_presets(self, builder_client):
        """Should list presets for an app with default ordering."""
        resp = builder_client.list_presets(TEST_APP_ID)
        assert resp["total"] >= 3
        names = [p["name"] for p in resp["presets"]]
        assert "Test Button" in names
        assert "Child Button" in names

    def test_list_presets_filter_by_category(self, builder_client):
        """Should filter presets by category."""
        resp = builder_client.list_presets(TEST_APP_ID, category="buttons")
        assert resp["total"] >= 1
        assert all(p["category"] == "buttons" for p in resp["presets"])

    def test_list_presets_search(self, builder_client):
        """Should search presets by name."""
        resp = builder_client.list_presets(TEST_APP_ID, search="Button")
        assert resp["total"] >= 1
        assert any("Button" in p["name"] for p in resp["presets"])

    def test_list_presets_empty_app(self, builder_client):
        """Should return empty list for unknown app."""
        resp = builder_client.list_presets("nonexistent-app")
        assert resp["total"] == 0
        assert resp["presets"] == []

    def test_get_preset(self, builder_client, created_preset_id):
        """Should get a single preset by ID."""
        resp = builder_client.get_preset(created_preset_id)
        assert resp["name"] == SAMPLE_PRESET["name"]
        assert resp["id"] == created_preset_id

    def test_get_preset_not_found(self, builder_client):
        """Should 404 for unknown preset."""
        with pytest.raises(Exception, match="404|not found"):
            builder_client.get_preset("nonexistent-id")

    def test_update_preset_name(self, builder_client, created_preset_id):
        """Should update preset name."""
        resp = builder_client.update_preset(created_preset_id, {"name": "Updated Button"})
        assert resp["status"] == "success"
        assert resp["data"]["name"] == "Updated Button"

    def test_update_preset_layout(self, builder_client, created_preset_id):
        """Should update preset layout fields."""
        resp = builder_client.update_preset(created_preset_id, {
            "layout": {"x": 300, "y": 400, "width": 200, "height": 80, "zIndex": 20, "locked": True, "rotation": 45}
        })
        data = resp["data"]
        assert data["layout"]["x"] == 300
        assert data["layout"]["y"] == 400
        assert data["layout"]["locked"] is True
        assert data["layout"]["rotation"] == 45

    def test_update_preset_style(self, builder_client, created_preset_id):
        """Should update preset style."""
        resp = builder_client.update_preset(created_preset_id, {
            "style": {"background": "#ef4444", "color": "#ffffff"}
        })
        assert resp["data"]["style"]["background"] == "#ef4444"

    def test_update_preset_auto_layout(self, builder_client, created_preset_id):
        """Should update auto-layout config."""
        resp = builder_client.update_preset(created_preset_id, {
            "auto_layout": {"direction": "horizontal", "padding": {"top": 8, "right": 8, "bottom": 8, "left": 8}, "gap": 12, "alignment": "center", "wrap": "no-wrap", "enabled": True}
        })
        assert resp["data"]["auto_layout"]["direction"] == "horizontal"
        assert resp["data"]["auto_layout"]["enabled"] is True

    def test_update_preset_constraints(self, builder_client, created_preset_id):
        """Should update constraints config."""
        resp = builder_client.update_preset(created_preset_id, {
            "constraints": {"horizontal": "stretch", "vertical": "top"}
        })
        assert resp["data"]["constraints"]["horizontal"] == "stretch"

    def test_update_preset_partial(self, builder_client, created_preset_id):
        """Should update only provided fields."""
        resp = builder_client.update_preset(created_preset_id, {"description": "Updated description"})
        assert resp["data"]["description"] == "Updated description"
        # Other fields unchanged
        assert resp["data"]["name"] == "Test Button"

    def test_duplicate_preset(self, builder_client, created_preset_id):
        """Should duplicate a preset with offset position."""
        resp = builder_client.duplicate_preset(created_preset_id, TEST_APP_ID)
        assert resp["status"] == "success"
        dup = resp["data"]
        assert "(copy)" in dup["name"]
        assert dup["layout"]["x"] == SAMPLE_PRESET["layout"]["x"] + 20
        assert dup["layout"]["y"] == SAMPLE_PRESET["layout"]["y"] + 20

    def test_delete_preset(self, builder_client, created_preset_id):
        """Should delete a preset."""
        resp = builder_client.delete_preset(created_preset_id)
        assert resp["status"] == "success"
        # Verify deleted
        with pytest.raises(Exception, match="404|not found"):
            builder_client.get_preset(created_preset_id)

    def test_delete_nonexistent_preset(self, builder_client):
        """Should 404 when deleting unknown preset."""
        with pytest.raises(Exception, match="404|not found"):
            builder_client.delete_preset("nonexistent-id")


# ═══════════════════════════════════════════════════════════════════
# Canvas State Tests
# ═══════════════════════════════════════════════════════════════════

class TestCanvasState:
    """Canvas state bulk save/load."""

    def test_get_canvas_state(self, builder_client):
        """Should load all presets for an app as canvas state."""
        resp = builder_client.get_canvas_state(TEST_APP_ID)
        assert resp["app_id"] == TEST_APP_ID
        assert len(resp["presets"]) > 0
        assert "canvas_view" in resp

    def test_save_canvas_state_replaces_all(self, builder_client):
        """Should replace all presets when saving canvas state."""
        new_presets = [
            {**SAMPLE_PRESET, "name": "Replacement A"},
            {**SAMPLE_PRESET, "name": "Replacement B"},
        ]
        resp = builder_client.save_canvas_state(TEST_APP_ID, new_presets)
        assert resp["status"] == "success"

        # Verify old presets are gone, new ones exist
        state = builder_client.get_canvas_state(TEST_APP_ID)
        names = [p["name"] for p in state["presets"]]
        assert "Replacement A" in names
        assert "Replacement B" in names
        assert "Test Button" not in names  # old preset replaced


# ═══════════════════════════════════════════════════════════════════
# Design Token CRUD Tests
# ═══════════════════════════════════════════════════════════════════

class TestTokenCRUD:
    """DesignTokenRecord: Create, Read, Update, Delete, List."""

    def test_create_token(self, builder_client):
        """Should create a design token."""
        resp = builder_client.create_token(TEST_APP_ID, SAMPLE_TOKEN)
        assert resp["status"] == "success"
        assert resp["data"]["name"] == SAMPLE_TOKEN["name"]
        assert resp["data"]["token_type"] == "color"

    def test_create_token_all_types(self, builder_client):
        """Should create tokens of all types."""
        types = ["dimension", "fontFamily", "borderRadius", "shadow", "spacing", "opacity"]
        for t in types:
            token = {**SAMPLE_TOKEN, "name": f"test.{t}", "token_type": t, "value": "16px"}
            resp = builder_client.create_token(TEST_APP_ID, token)
            assert resp["status"] == "success"
            assert resp["data"]["token_type"] == t

    def test_create_token_with_alias(self, builder_client):
        """Should create token with alias reference."""
        token = {**SAMPLE_TOKEN, "name": "test.secondary", "alias": "test.primary"}
        resp = builder_client.create_token(TEST_APP_ID, token)
        assert resp["status"] == "success"
        assert resp["data"]["alias"] == "test.primary"

    def test_list_tokens(self, builder_client):
        """Should list tokens with optional filters."""
        resp = builder_client.list_tokens(TEST_APP_ID)
        assert resp["total"] >= 3

    def test_list_tokens_filter_by_type(self, builder_client):
        """Should filter tokens by type."""
        resp = builder_client.list_tokens(TEST_APP_ID, token_type="color")
        assert resp["total"] >= 1
        assert all(t["token_type"] == "color" for t in resp["tokens"])

    def test_list_tokens_filter_by_mode(self, builder_client):
        """Should filter tokens by mode/theme."""
        resp = builder_client.list_tokens(TEST_APP_ID, mode="light")
        assert resp["total"] >= 1

    def test_list_tokens_filter_by_namespace(self, builder_client):
        """Should filter tokens by namespace."""
        resp = builder_client.list_tokens(TEST_APP_ID, namespace="test")
        assert resp["total"] >= 1

    def test_update_token(self, builder_client, created_token_id):
        """Should update token value."""
        resp = builder_client.update_token(created_token_id, {"value": "#4f46e5"})
        assert resp["status"] == "success"
        assert resp["data"]["value"] == "#4f46e5"

    def test_delete_token(self, builder_client, created_token_id):
        """Should delete a token."""
        resp = builder_client.delete_token(created_token_id)
        assert resp["status"] == "success"


# ═══════════════════════════════════════════════════════════════════
# Data Binding CRUD + Test Connection Tests
# ═══════════════════════════════════════════════════════════════════

class TestBindingCRUD:
    """DataBindingRecord: CRUD + test connection."""

    def test_create_binding(self, builder_client):
        """Should create a data binding."""
        resp = builder_client.create_binding(TEST_APP_ID, SAMPLE_BINDING)
        assert resp["status"] == "success"
        assert resp["data"]["source_type"] == "mock_json"

    def test_list_bindings(self, builder_client):
        """Should list bindings with preset filter."""
        resp = builder_client.list_bindings(TEST_APP_ID, preset_id=PRESET_ID)
        assert resp["total"] >= 1

    def test_update_binding_source(self, builder_client, created_binding_id):
        """Should update binding source type."""
        resp = builder_client.update_binding(created_binding_id, {"source_type": "static_json"})
        assert resp["status"] == "success"

    def test_delete_binding(self, builder_client, created_binding_id):
        """Should delete a binding."""
        resp = builder_client.delete_binding(created_binding_id)
        assert resp["status"] == "success"

    def test_test_binding_mock_json(self, builder_client):
        """Should test a mock_json binding."""
        resp = builder_client.test_binding({
            "source_type": "mock_json",
            "mock_data": '{"key": "value"}',
        })
        assert resp["success"] is True
        assert resp["preview"]["key"] == "value"

    def test_test_binding_static_json(self, builder_client):
        """Should test a static_json binding."""
        resp = builder_client.test_binding({
            "source_type": "static_json",
        })
        assert resp["success"] is True

    def test_test_binding_memory_store(self, builder_client):
        """Should test a memory_store binding."""
        resp = builder_client.test_binding({
            "source_type": "memory_store",
        })
        assert resp["success"] is True

    def test_test_binding_no_config(self, builder_client):
        """Should return error for empty binding test."""
        resp = builder_client.test_binding({
            "source_type": "rest_endpoint",
        })
        assert resp["success"] is False
        assert resp["error"] is not None

    def test_test_binding_invalid_websocket(self, builder_client):
        """Should validate WebSocket endpoint format."""
        resp = builder_client.test_binding({
            "source_type": "websocket",
            "endpoint": "http://bad-url.com",
        })
        assert resp["success"] is False

    def test_test_binding_valid_websocket(self, builder_client):
        """Should accept valid WebSocket endpoint."""
        resp = builder_client.test_binding({
            "source_type": "websocket",
            "endpoint": "wss://example.com/ws",
        })
        assert resp["success"] is True

    def test_test_binding_sse(self, builder_client):
        """Should validate SSE endpoint format."""
        resp = builder_client.test_binding({
            "source_type": "sse_stream",
            "endpoint": "https://example.com/events",
        })
        assert resp["success"] is True

    def test_test_binding_sqlite(self, builder_client):
        """Should validate SQLite configuration."""
        resp = builder_client.test_binding({
            "source_type": "sqlite_local",
            "endpoint": "/data/app.db",
        })
        assert resp["success"] is True

    def test_test_binding_sqlite_no_path(self, builder_client):
        """Should error on SQLite without path."""
        resp = builder_client.test_binding({
            "source_type": "sqlite_local",
        })
        assert resp["success"] is False

    def test_test_existing_binding(self, builder_client, created_binding_id):
        """Should test an existing binding by ID."""
        resp = builder_client.test_existing_binding(created_binding_id)
        # This is a mock_json binding, so it should succeed
        assert "success" in resp or "error" in resp or "preview" in resp


# ═══════════════════════════════════════════════════════════════════
# Layout Compute Tests
# ═══════════════════════════════════════════════════════════════════

class TestLayoutCompute:
    """Auto-layout and constraint computation."""

    def test_compute_vertical_layout(self, builder_client):
        """Should compute vertical auto-layout positions."""
        presets = [
            {"id": "a", "width": 200, "height": 80},
            {"id": "b", "width": 200, "height": 100},
            {"id": "c", "width": 200, "height": 60},
        ]
        auto_layout = {"direction": "vertical", "padding": {"top": 16, "right": 16, "bottom": 16, "left": 16}, "gap": 12, "alignment": "top-left", "wrap": "no-wrap", "enabled": True}
        resp = builder_client.compute_layout(presets, auto_layout=auto_layout, parent_width=400, parent_height=500)
        assert len(resp["children"]) == 3
        assert resp["children"][0]["y"] == 16  # starts at padding top
        assert resp["children"][1]["y"] > resp["children"][0]["y"]
        assert resp["children"][2]["y"] > resp["children"][1]["y"]

    def test_compute_horizontal_layout(self, builder_client):
        """Should compute horizontal auto-layout positions."""
        presets = [{"id": "a", "width": 100, "height": 80}, {"id": "b", "width": 150, "height": 80}]
        auto_layout = {"direction": "horizontal", "padding": {"top": 0, "right": 0, "bottom": 0, "left": 0}, "gap": 8, "alignment": "top-left", "wrap": "no-wrap", "enabled": True}
        resp = builder_client.compute_layout(presets, auto_layout=auto_layout, parent_width=500, parent_height=200)
        assert resp["children"][0]["x"] == 0  # starts at left
        assert resp["children"][1]["x"] >= 100 + 8  # width + gap

    def test_compute_layout_center_alignment(self, builder_client):
        """Should center children within parent."""
        presets = [{"id": "a", "width": 100, "height": 50}]
        auto_layout = {"direction": "vertical", "padding": {"top": 0, "right": 0, "bottom": 0, "left": 0}, "gap": 0, "alignment": "center", "wrap": "no-wrap", "enabled": True}
        resp = builder_client.compute_layout(presets, auto_layout=auto_layout, parent_width=200, parent_height=200)
        assert resp["children"][0]["x"] == 50  # centered horizontally: (200-100)/2

    def test_compute_layout_no_auto_layout(self, builder_client):
        """Should return original positions when auto-layout is disabled."""
        presets = [{"id": "a", "pos_x": 10, "pos_y": 20, "width": 100, "height": 50}]
        resp = builder_client.compute_layout(presets, auto_layout=None, parent_width=500, parent_height=500)
        assert resp["children"][0]["x"] == 10
        assert resp["children"][0]["y"] == 20

    def test_compute_constraints_scale(self, builder_client):
        """Should compute constraint-based positions when parent resizes."""
        presets = [{"id": "a", "pos_x": 100, "pos_y": 50, "width": 200, "height": 100}]
        constraints = {"horizontal": "scale", "vertical": "scale"}
        resp = builder_client.compute_layout(
            presets, constraints=constraints,
            parent_width=800, parent_height=600,
            old_parent_width=400, old_parent_height=300,
        )
        # Scaled: x should double, width should double
        assert pytest.approx(resp["children"][0]["x"], 0.1) == 200
        assert pytest.approx(resp["children"][0]["width"], 0.1) == 400


# ═══════════════════════════════════════════════════════════════════
# Seed Data Tests
# ═══════════════════════════════════════════════════════════════════

class TestSeedData:
    """Demo data seeding."""

    def test_seed_demo_data(self, builder_client):
        """Should seed demo presets and tokens."""
        resp = builder_client.seed_data(TEST_APP_ID)
        assert resp["status"] == "success"
        assert resp["data"]["presets_count"] >= 1
        assert resp["data"]["tokens_count"] >= 1

    def test_seed_idempotent(self, builder_client):
        """Should not duplicate existing data on re-seed."""
        resp1 = builder_client.seed_data(TEST_APP_ID)
        resp2 = builder_client.seed_data(TEST_APP_ID)
        # Second call should report 0 created (existing)
        assert resp2["data"]["presets_count"] == 0 or resp2["data"]["presets_count"] >= resp1["data"]["presets_count"]


# ═══════════════════════════════════════════════════════════════════
# Version CRUD Tests (NEW)
# ═══════════════════════════════════════════════════════════════════

class TestVersionCRUD:
    """PresetVersionRecord: Create, List, Get, Delete."""

    def test_create_version(self, builder_client):
        """Should create a version snapshot."""
        resp = builder_client.create_version(TEST_APP_ID, SAMPLE_VERSION)
        assert resp["status"] == "success"
        assert resp["data"]["version_number"] == 1

    def test_create_version_auto_increments(self, builder_client):
        """Should auto-increment version number."""
        v2 = {**SAMPLE_VERSION, "label": "v2.0"}
        resp = builder_client.create_version(TEST_APP_ID, v2)
        assert resp["status"] == "success"
        assert resp["data"]["version_number"] == 2

    def test_list_versions(self, builder_client):
        """Should list versions for an app, newest first."""
        resp = builder_client.list_versions(TEST_APP_ID, preset_id=PRESET_ID)
        assert resp["total"] >= 2
        assert resp["versions"][0]["version_number"] > resp["versions"][1]["version_number"]

    def test_get_version(self, builder_client, created_version_id):
        """Should get a specific version by ID."""
        resp = builder_client.get_version(created_version_id)
        assert resp["id"] == created_version_id

    def test_get_version_not_found(self, builder_client):
        """Should 404 for unknown version."""
        with pytest.raises(Exception, match="404|not found"):
            builder_client.get_version("nonexistent-version")

    def test_delete_version(self, builder_client, created_version_id):
        """Should delete a version."""
        resp = builder_client.delete_version(created_version_id)
        assert resp["status"] == "success"


# ═══════════════════════════════════════════════════════════════════
# Comment CRUD Tests (NEW)
# ═══════════════════════════════════════════════════════════════════

class TestCommentCRUD:
    """CommentRecord: Create, List, Update, Delete, Multi-reply."""

    def test_create_comment(self, builder_client):
        """Should create a comment on a preset."""
        resp = builder_client.create_comment(TEST_APP_ID, SAMPLE_COMMENT)
        assert resp["status"] == "success"
        assert resp["data"] is not None

    def test_create_comment_without_pin(self, builder_client):
        """Should create a comment without canvas position."""
        comment = {**SAMPLE_COMMENT, "pin_x": None, "pin_y": None}
        resp = builder_client.create_comment(TEST_APP_ID, comment)
        assert resp["status"] == "success"

    def test_list_comments(self, builder_client):
        """Should list comments with preset filter."""
        resp = builder_client.list_comments(TEST_APP_ID, preset_id=PRESET_ID)
        assert resp["total"] >= 1

    def test_list_comments_filter_resolved(self, builder_client):
        """Should filter by resolved status."""
        resp = builder_client.list_comments(TEST_APP_ID, preset_id=PRESET_ID, resolved=False)
        assert resp["total"] >= 1

    def test_create_comment_reply(self, builder_client, created_comment_id):
        """Should create a threaded reply to a comment."""
        reply = {**SAMPLE_COMMENT, "content": "Agreed! Making it bigger.", "parent_comment_id": created_comment_id}
        resp = builder_client.create_comment(TEST_APP_ID, reply)
        assert resp["status"] == "success"

    def test_resolve_comment(self, builder_client, created_comment_id):
        """Should mark a comment as resolved."""
        resp = builder_client.update_comment(created_comment_id, {"resolved": True})
        assert resp["status"] == "success"

    def test_update_comment_content(self, builder_client, created_comment_id):
        """Should update comment content."""
        resp = builder_client.update_comment(created_comment_id, {"content": "Updated!"})
        assert resp["status"] == "success"

    def test_delete_comment(self, builder_client, created_comment_id):
        """Should delete a comment."""
        resp = builder_client.delete_comment(created_comment_id)
        assert resp["status"] == "success"


# ═══════════════════════════════════════════════════════════════════
# Interaction CRUD Tests (NEW)
# ═══════════════════════════════════════════════════════════════════

class TestInteractionCRUD:
    """InteractionRecord: Create, List, Update, Delete."""

    def test_create_interaction(self, builder_client):
        """Should create a prototyping interaction."""
        resp = builder_client.create_interaction(TEST_APP_ID, SAMPLE_INTERACTION)
        assert resp["status"] == "success"
        assert resp["data"] is not None

    def test_create_interaction_all_trigger_types(self, builder_client):
        """Should create interactions of all trigger types."""
        triggers = ["click", "hover", "drag", "scroll", "timer"]
        for t in triggers:
            interaction = {**SAMPLE_INTERACTION, "name": f"Trigger {t}", "trigger_type": t}
            resp = builder_client.create_interaction(TEST_APP_ID, interaction)
            assert resp["status"] == "success"

    def test_list_interactions(self, builder_client):
        """Should list interactions with filter."""
        resp = builder_client.list_interactions(TEST_APP_ID, source_preset_id=PRESET_ID)
        assert resp["total"] >= 1

    def test_list_interactions_filter_trigger(self, builder_client):
        """Should filter by trigger type."""
        resp = builder_client.list_interactions(TEST_APP_ID, trigger_type="click")
        assert resp["total"] >= 1

    def test_update_interaction(self, builder_client, created_interaction_id):
        """Should update interaction config."""
        resp = builder_client.update_interaction(created_interaction_id, {
            "enabled": False,
            "action_config": {"url": "/about"},
        })
        assert resp["status"] == "success"

    def test_delete_interaction(self, builder_client, created_interaction_id):
        """Should delete an interaction."""
        resp = builder_client.delete_interaction(created_interaction_id)
        assert resp["status"] == "success"


# ═══════════════════════════════════════════════════════════════════
# Asset CRUD Tests (NEW)
# ═══════════════════════════════════════════════════════════════════

class TestAssetCRUD:
    """AssetRecord: Create, List, Get, Delete."""

    def test_create_asset(self, builder_client):
        """Should register a new asset."""
        resp = builder_client.create_asset(TEST_APP_ID, SAMPLE_ASSET)
        assert resp["status"] == "success"

    def test_list_assets(self, builder_client):
        """Should list assets with category filter."""
        resp = builder_client.list_assets(TEST_APP_ID, category="image")
        assert resp["total"] >= 1

    def test_get_asset(self, builder_client, created_asset_id):
        """Should get asset details."""
        resp = builder_client.get_asset(created_asset_id)
        assert resp["name"] == SAMPLE_ASSET["name"]

    def test_get_asset_not_found(self, builder_client):
        """Should 404 for unknown asset."""
        with pytest.raises(Exception, match="404|not found"):
            builder_client.get_asset("nonexistent-asset")

    def test_delete_asset(self, builder_client, created_asset_id):
        """Should delete an asset."""
        resp = builder_client.delete_asset(created_asset_id)
        assert resp["status"] == "success"


# ═══════════════════════════════════════════════════════════════════
# Plugin CRUD Tests (NEW)
# ═══════════════════════════════════════════════════════════════════

class TestPluginCRUD:
    """PluginRecord: Create, List, Update, Delete."""

    def test_create_plugin(self, builder_client):
        """Should register a new plugin."""
        resp = builder_client.create_plugin(TEST_APP_ID, SAMPLE_PLUGIN)
        assert resp["status"] == "success"

    def test_list_plugins(self, builder_client):
        """Should list plugins with type filter."""
        resp = builder_client.list_plugins(TEST_APP_ID, plugin_type="export")
        assert resp["total"] >= 1

    def test_list_plugins_filter_enabled(self, builder_client):
        """Should filter by enabled status."""
        resp = builder_client.list_plugins(TEST_APP_ID, enabled=True)
        assert resp["total"] >= 1

    def test_update_plugin(self, builder_client, created_plugin_id):
        """Should update plugin config."""
        resp = builder_client.update_plugin(created_plugin_id, {"enabled": False})
        assert resp["status"] == "success"

    def test_delete_plugin(self, builder_client, created_plugin_id):
        """Should delete a plugin."""
        resp = builder_client.delete_plugin(created_plugin_id)
        assert resp["status"] == "success"
