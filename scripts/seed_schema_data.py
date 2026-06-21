"""
Seed Schema Data — Populates schema tables, relationships, and migrations
for the 6 example apps in the App Builder.

Run with: uv run python scripts/seed_schema_data.py
"""
import sys
import os
import uuid
from datetime import datetime, timezone

# Add the Backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select, delete
from common_lib.modules.data_storage.database.connection import get_session, engine
from app.modules.schema.models import (
    SchemaTableRecord,
    SchemaRelationshipRecord,
    SchemaMigrationRecord,
    SchemaSnapshotRecord,
    SchemaModelRecord,
    SchemaSeedDataRecord,
    SchemaDiagramLayoutRecord,
    SchemaVersionRecord,
)



def generate_id() -> str:
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════════
# Table Definitions for All 6 Apps
# ═══════════════════════════════════════════════════════════════════════

TABLES = [
    # ── AI Chat App ──────────────────────────────────────────────────
    {
        "name": "conversations",
        "description": "Chat conversation sessions (AI Chat App)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "title", "type": "varchar", "length": 256, "nullable": True},
            {"name": "user_id", "type": "uuid", "nullable": False, "index": True},
            {"name": "model", "type": "varchar", "length": 64, "nullable": True, "default": "'gpt-4'"},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
            {"name": "updated_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "messages",
        "description": "Individual chat messages within conversations (AI Chat App)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "conversation_id", "type": "uuid", "nullable": False, "index": True},
            {"name": "role", "type": "varchar", "length": 16, "nullable": False},
            {"name": "content", "type": "text", "nullable": False},
            {"name": "token_count", "type": "integer", "nullable": True},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "memories",
        "description": "Agent memory store for persistent context (AI Chat App)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "user_id", "type": "uuid", "nullable": False, "index": True},
            {"name": "key", "type": "varchar", "length": 128, "nullable": False},
            {"name": "value", "type": "jsonb", "nullable": False},
            {"name": "importance", "type": "float", "nullable": True, "default": "0.5"},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
            {"name": "expires_at", "type": "timestamptz", "nullable": True},
        ],
    },

    # ── Vision Studio ────────────────────────────────────────────────
    {
        "name": "generations",
        "description": "Image generation job records (Vision Studio)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "prompt", "type": "text", "nullable": False},
            {"name": "negative_prompt", "type": "text", "nullable": True},
            {"name": "model", "type": "varchar", "length": 128, "nullable": False},
            {"name": "sampler", "type": "varchar", "length": 64, "nullable": True, "default": "'Euler a'"},
            {"name": "seed", "type": "integer", "nullable": True},
            {"name": "width", "type": "integer", "nullable": False, "default": "512"},
            {"name": "height", "type": "integer", "nullable": False, "default": "512"},
            {"name": "steps", "type": "integer", "nullable": True, "default": "30"},
            {"name": "cfg_scale", "type": "float", "nullable": True, "default": "7.0"},
            {"name": "image_url", "type": "text", "nullable": True},
            {"name": "status", "type": "varchar", "length": 16, "nullable": False, "default": "'pending'"},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "galleries",
        "description": "Image galleries for organizing generations (Vision Studio)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "name", "type": "varchar", "length": 256, "nullable": False},
            {"name": "description", "type": "text", "nullable": True},
            {"name": "user_id", "type": "uuid", "nullable": False, "index": True},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "gallery_items",
        "description": "Junction table linking galleries to generations (Vision Studio)",
        "columns": [
            {"name": "gallery_id", "type": "uuid", "nullable": False, "primary_key": True},
            {"name": "generation_id", "type": "uuid", "nullable": False, "primary_key": True},
            {"name": "sort_order", "type": "integer", "nullable": True, "default": "0"},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },

    # ── CRUD App ─────────────────────────────────────────────────────
    {
        "name": "items",
        "description": "Inventory items (CRUD App)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "name", "type": "varchar", "length": 256, "nullable": False},
            {"name": "description", "type": "text", "nullable": True},
            {"name": "quantity", "type": "integer", "nullable": False, "default": "0"},
            {"name": "status", "type": "varchar", "length": 32, "nullable": False, "default": "'active'"},
            {"name": "price", "type": "decimal", "nullable": True},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
            {"name": "updated_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "categories",
        "description": "Item categories for organization (CRUD App)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "name", "type": "varchar", "length": 128, "nullable": False, "unique": True},
            {"name": "description", "type": "text", "nullable": True},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "item_categories",
        "description": "Junction table for items and categories (CRUD App)",
        "columns": [
            {"name": "item_id", "type": "uuid", "nullable": False, "primary_key": True},
            {"name": "category_id", "type": "uuid", "nullable": False, "primary_key": True},
        ],
    },

    # ── Dashboard ────────────────────────────────────────────────────
    {
        "name": "analytics_events",
        "description": "Raw analytics event stream (Dashboard)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "event_type", "type": "varchar", "length": 64, "nullable": False, "index": True},
            {"name": "user_id", "type": "uuid", "nullable": True, "index": True},
            {"name": "properties", "type": "jsonb", "nullable": True},
            {"name": "session_id", "type": "uuid", "nullable": True},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "metrics",
        "description": "Time-series metric recordings (Dashboard)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "metric_name", "type": "varchar", "length": 128, "nullable": False, "index": True},
            {"name": "value", "type": "float", "nullable": False},
            {"name": "tags", "type": "jsonb", "nullable": True},
            {"name": "recorded_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "dashboards",
        "description": "Dashboard configurations (Dashboard)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "name", "type": "varchar", "length": 256, "nullable": False},
            {"name": "config", "type": "jsonb", "nullable": False},
            {"name": "user_id", "type": "uuid", "nullable": False, "index": True},
            {"name": "is_default", "type": "boolean", "nullable": True, "default": "false"},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
            {"name": "updated_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "dashboard_widgets",
        "description": "Individual widget instances on dashboards (Dashboard)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "dashboard_id", "type": "uuid", "nullable": False, "index": True},
            {"name": "widget_type", "type": "varchar", "length": 64, "nullable": False},
            {"name": "title", "type": "varchar", "length": 256, "nullable": False},
            {"name": "config", "type": "jsonb", "nullable": False},
            {"name": "position_x", "type": "integer", "nullable": False, "default": "0"},
            {"name": "position_y", "type": "integer", "nullable": False, "default": "0"},
            {"name": "width", "type": "integer", "nullable": False, "default": "6"},
            {"name": "height", "type": "integer", "nullable": False, "default": "4"},
        ],
    },

    # ── Workflow Monitor ─────────────────────────────────────────────
    {
        "name": "workflows",
        "description": "Orchestration pipeline definitions (Workflow Monitor)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "name", "type": "varchar", "length": 256, "nullable": False},
            {"name": "description", "type": "text", "nullable": True},
            {"name": "status", "type": "varchar", "length": 32, "nullable": False, "default": "'active'"},
            {"name": "config", "type": "jsonb", "nullable": True},
            {"name": "created_by", "type": "uuid", "nullable": True},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
            {"name": "updated_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "workflow_runs",
        "description": "Individual execution instances of workflows (Workflow Monitor)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "workflow_id", "type": "uuid", "nullable": False, "index": True},
            {"name": "status", "type": "varchar", "length": 32, "nullable": False, "default": "'pending'"},
            {"name": "triggered_by", "type": "uuid", "nullable": True},
            {"name": "started_at", "type": "timestamptz", "nullable": True},
            {"name": "completed_at", "type": "timestamptz", "nullable": True},
            {"name": "duration_ms", "type": "float", "nullable": True},
            {"name": "error_message", "type": "text", "nullable": True},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "workflow_steps",
        "description": "Individual steps within a workflow run (Workflow Monitor)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "workflow_run_id", "type": "uuid", "nullable": False, "index": True},
            {"name": "name", "type": "varchar", "length": 256, "nullable": False},
            {"name": "status", "type": "varchar", "length": 32, "nullable": False, "default": "'pending'"},
            {"name": "output", "type": "jsonb", "nullable": True},
            {"name": "error_message", "type": "text", "nullable": True},
            {"name": "started_at", "type": "timestamptz", "nullable": True},
            {"name": "completed_at", "type": "timestamptz", "nullable": True},
            {"name": "sort_order", "type": "integer", "nullable": False, "default": "0"},
        ],
    },

    # ── Location Tracker ─────────────────────────────────────────────
    {
        "name": "locations",
        "description": "GPS location records (Location Tracker)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "user_id", "type": "uuid", "nullable": False, "index": True},
            {"name": "latitude", "type": "float", "nullable": False},
            {"name": "longitude", "type": "float", "nullable": False},
            {"name": "accuracy", "type": "float", "nullable": True},
            {"name": "altitude", "type": "float", "nullable": True},
            {"name": "speed", "type": "float", "nullable": True},
            {"name": "heading", "type": "float", "nullable": True},
            {"name": "timestamp", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "geofences",
        "description": "Geographic boundary definitions (Location Tracker)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "name", "type": "varchar", "length": 256, "nullable": False},
            {"name": "description", "type": "text", "nullable": True},
            {"name": "latitude", "type": "float", "nullable": False},
            {"name": "longitude", "type": "float", "nullable": False},
            {"name": "radius", "type": "float", "nullable": False, "default": "100"},
            {"name": "active", "type": "boolean", "nullable": False, "default": "true"},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "location_alerts",
        "description": "Alerts triggered by geofence entry/exit (Location Tracker)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "user_id", "type": "uuid", "nullable": False, "index": True},
            {"name": "geofence_id", "type": "uuid", "nullable": False, "index": True},
            {"name": "alert_type", "type": "varchar", "length": 32, "nullable": False},
            {"name": "latitude", "type": "float", "nullable": True},
            {"name": "longitude", "type": "float", "nullable": True},
            {"name": "acknowledged", "type": "boolean", "nullable": False, "default": "false"},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },

    # ── Shared / Cross-App ───────────────────────────────────────────
    {
        "name": "users",
        "description": "Platform user accounts (shared across all apps)",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "email", "type": "varchar", "length": 256, "nullable": False, "unique": True},
            {"name": "name", "type": "varchar", "length": 256, "nullable": True},
            {"name": "avatar_url", "type": "text", "nullable": True},
            {"name": "role", "type": "varchar", "length": 32, "nullable": False, "default": "'user'"},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
    {
        "name": "api_keys",
        "description": "API key management for authenticated access",
        "columns": [
            {"name": "id", "type": "uuid", "primary_key": True, "nullable": False},
            {"name": "user_id", "type": "uuid", "nullable": False, "index": True},
            {"name": "name", "type": "varchar", "length": 128, "nullable": False},
            {"name": "key_hash", "type": "varchar", "length": 128, "nullable": False, "unique": True},
            {"name": "scopes", "type": "jsonb", "nullable": True},
            {"name": "expires_at", "type": "timestamptz", "nullable": True},
            {"name": "created_at", "type": "timestamptz", "nullable": False, "default": "now()"},
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════
# Relationship Definitions
# ═══════════════════════════════════════════════════════════════════════

RELATIONSHIPS = [
    # AI Chat App
    {"name": "conversations_user", "source": "conversations", "source_col": "user_id", "target": "users", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},
    {"name": "messages_conversation", "source": "messages", "source_col": "conversation_id", "target": "conversations", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},
    {"name": "memories_user", "source": "memories", "source_col": "user_id", "target": "users", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},

    # Vision Studio
    {"name": "galleries_user", "source": "galleries", "source_col": "user_id", "target": "users", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},
    {"name": "gallery_items_gallery", "source": "gallery_items", "source_col": "gallery_id", "target": "galleries", "target_col": "id", "type": "many_to_many", "through_table": "gallery_items", "on_delete": "CASCADE"},
    {"name": "gallery_items_generation", "source": "gallery_items", "source_col": "generation_id", "target": "generations", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},

    # CRUD App
    {"name": "item_categories_item", "source": "item_categories", "source_col": "item_id", "target": "items", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},
    {"name": "item_categories_category", "source": "item_categories", "source_col": "category_id", "target": "categories", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},

    # Dashboard
    {"name": "dashboards_user", "source": "dashboards", "source_col": "user_id", "target": "users", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},
    {"name": "dashboard_widgets_dashboard", "source": "dashboard_widgets", "source_col": "dashboard_id", "target": "dashboards", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},

    # Workflow Monitor
    {"name": "workflow_runs_workflow", "source": "workflow_runs", "source_col": "workflow_id", "target": "workflows", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},
    {"name": "workflow_steps_run", "source": "workflow_steps", "source_col": "workflow_run_id", "target": "workflow_runs", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},

    # Location Tracker
    {"name": "locations_user", "source": "locations", "source_col": "user_id", "target": "users", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},
    {"name": "location_alerts_user", "source": "location_alerts", "source_col": "user_id", "target": "users", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},
    {"name": "location_alerts_geofence", "source": "location_alerts", "source_col": "geofence_id", "target": "geofences", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},

    # Shared
    {"name": "api_keys_user", "source": "api_keys", "source_col": "user_id", "target": "users", "target_col": "id", "type": "one_to_many", "on_delete": "CASCADE"},
]


# ═══════════════════════════════════════════════════════════════════════
# Migration Definitions
# ═══════════════════════════════════════════════════════════════════════

MIGRATIONS = [
    {
        "name": "001_create_users_and_api_keys",
        "version": "001",
        "sql_up": """-- Create users table (shared across all apps)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(256) NOT NULL UNIQUE,
    name VARCHAR(256),
    avatar_url TEXT,
    role VARCHAR(32) NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create api_keys table
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    key_hash VARCHAR(128) NOT NULL UNIQUE,
    scopes JSONB,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);""",
        "sql_down": """DROP TABLE IF EXISTS api_keys;
DROP TABLE IF EXISTS users;""",
        "diff_summary": "Create users and api_keys tables",
    },
    {
        "name": "002_create_ai_chat_tables",
        "version": "002",
        "sql_up": """-- AI Chat App tables
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(256),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    model VARCHAR(64) DEFAULT 'gpt-4',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key VARCHAR(128) NOT NULL,
    value JSONB NOT NULL,
    importance FLOAT DEFAULT 0.5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_memories_user_id ON memories(user_id);""",
        "sql_down": """DROP TABLE IF EXISTS memories;
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS conversations;""",
        "diff_summary": "Create conversations, messages, memories tables for AI Chat App",
    },
    {
        "name": "003_create_vision_studio_tables",
        "version": "003",
        "sql_up": """-- Vision Studio tables
CREATE TABLE generations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt TEXT NOT NULL,
    negative_prompt TEXT,
    model VARCHAR(128) NOT NULL,
    sampler VARCHAR(64) DEFAULT 'Euler a',
    seed INTEGER,
    width INTEGER NOT NULL DEFAULT 512,
    height INTEGER NOT NULL DEFAULT 512,
    steps INTEGER DEFAULT 30,
    cfg_scale FLOAT DEFAULT 7.0,
    image_url TEXT,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE galleries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(256) NOT NULL,
    description TEXT,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE gallery_items (
    gallery_id UUID NOT NULL REFERENCES galleries(id) ON DELETE CASCADE,
    generation_id UUID NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (gallery_id, generation_id)
);

CREATE INDEX idx_galleries_user_id ON galleries(user_id);""",
        "sql_down": """DROP TABLE IF EXISTS gallery_items;
DROP TABLE IF EXISTS galleries;
DROP TABLE IF EXISTS generations;""",
        "diff_summary": "Create generations, galleries, gallery_items tables for Vision Studio",
    },
    {
        "name": "004_create_crud_app_tables",
        "version": "004",
        "sql_up": """-- CRUD App tables
CREATE TABLE items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(256) NOT NULL,
    description TEXT,
    quantity INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    price DECIMAL(10,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE item_categories (
    item_id UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, category_id)
);""",
        "sql_down": """DROP TABLE IF EXISTS item_categories;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS items;""",
        "diff_summary": "Create items, categories, item_categories tables for CRUD App",
    },
    {
        "name": "005_create_dashboard_tables",
        "version": "005",
        "sql_up": """-- Dashboard tables
CREATE TABLE analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(64) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    properties JSONB,
    session_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(128) NOT NULL,
    value FLOAT NOT NULL,
    tags JSONB,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE dashboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(256) NOT NULL,
    config JSONB NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE dashboard_widgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dashboard_id UUID NOT NULL REFERENCES dashboards(id) ON DELETE CASCADE,
    widget_type VARCHAR(64) NOT NULL,
    title VARCHAR(256) NOT NULL,
    config JSONB NOT NULL,
    position_x INTEGER NOT NULL DEFAULT 0,
    position_y INTEGER NOT NULL DEFAULT 0,
    width INTEGER NOT NULL DEFAULT 6,
    height INTEGER NOT NULL DEFAULT 4
);

CREATE INDEX idx_analytics_events_event_type ON analytics_events(event_type);
CREATE INDEX idx_analytics_events_user_id ON analytics_events(user_id);
CREATE INDEX idx_metrics_metric_name ON metrics(metric_name);
CREATE INDEX idx_dashboards_user_id ON dashboards(user_id);
CREATE INDEX idx_dashboard_widgets_dashboard_id ON dashboard_widgets(dashboard_id);""",
        "sql_down": """DROP TABLE IF EXISTS dashboard_widgets;
DROP TABLE IF EXISTS dashboards;
DROP TABLE IF EXISTS metrics;
DROP TABLE IF EXISTS analytics_events;""",
        "diff_summary": "Create analytics_events, metrics, dashboards, dashboard_widgets tables for Dashboard",
    },
    {
        "name": "006_create_workflow_monitor_tables",
        "version": "006",
        "sql_up": """-- Workflow Monitor tables
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(256) NOT NULL,
    description TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    config JSONB,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    triggered_by UUID REFERENCES users(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms FLOAT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE workflow_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    name VARCHAR(256) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    output JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_workflow_runs_workflow_id ON workflow_runs(workflow_id);
CREATE INDEX idx_workflow_steps_run_id ON workflow_steps(workflow_run_id);""",
        "sql_down": """DROP TABLE IF EXISTS workflow_steps;
DROP TABLE IF EXISTS workflow_runs;
DROP TABLE IF EXISTS workflows;""",
        "diff_summary": "Create workflows, workflow_runs, workflow_steps tables for Workflow Monitor",
    },
    {
        "name": "007_create_location_tracker_tables",
        "version": "007",
        "sql_up": """-- Location Tracker tables
CREATE TABLE locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    accuracy FLOAT,
    altitude FLOAT,
    speed FLOAT,
    heading FLOAT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE geofences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(256) NOT NULL,
    description TEXT,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    radius FLOAT NOT NULL DEFAULT 100,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE location_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    geofence_id UUID NOT NULL REFERENCES geofences(id) ON DELETE CASCADE,
    alert_type VARCHAR(32) NOT NULL,
    latitude FLOAT,
    longitude FLOAT,
    acknowledged BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_locations_user_id ON locations(user_id);
CREATE INDEX idx_location_alerts_user_id ON location_alerts(user_id);
CREATE INDEX idx_location_alerts_geofence_id ON location_alerts(geofence_id);""",
        "sql_down": """DROP TABLE IF EXISTS location_alerts;
DROP TABLE IF EXISTS geofences;
DROP TABLE IF EXISTS locations;""",
        "diff_summary": "Create locations, geofences, location_alerts tables for Location Tracker",
    },
]


# ═══════════════════════════════════════════════════════════════════════
# Seed Function
# ═══════════════════════════════════════════════════════════════════════

def seed_schema_data():
    """Populate schema tables, relationships, and migrations partitioned by app."""
    print("[SEED] Seeding schema data partitioned by app...")

    db = next(get_session())
    # ── Clear existing data ──
    print("  [1/5] Clearing all existing schema data...")
    db.execute(delete(SchemaVersionRecord))
    db.execute(delete(SchemaDiagramLayoutRecord))
    db.execute(delete(SchemaSeedDataRecord))
    db.execute(delete(SchemaModelRecord))
    db.execute(delete(SchemaSnapshotRecord))
    db.execute(delete(SchemaMigrationRecord))
    db.execute(delete(SchemaRelationshipRecord))
    db.execute(delete(SchemaTableRecord))
    db.commit()

    apps_def = {
        "ai-chat": {
            "tables": ["conversations", "messages", "memories", "users", "api_keys"],
            "migrations": ["001_create_users_and_api_keys", "002_create_ai_chat_tables"],
            "name": "AI Chat App"
        },
        "vision-studio": {
            "tables": ["generations", "galleries", "gallery_items", "users", "api_keys"],
            "migrations": ["001_create_users_and_api_keys", "003_create_vision_studio_tables"],
            "name": "Vision Studio"
        },
        "crud-app": {
            "tables": ["items", "categories", "item_categories", "users", "api_keys"],
            "migrations": ["001_create_users_and_api_keys", "004_create_crud_app_tables"],
            "name": "CRUD App"
        },
        "dashboard": {
            "tables": ["analytics_events", "metrics", "dashboards", "dashboard_widgets", "users", "api_keys"],
            "migrations": ["001_create_users_and_api_keys", "005_create_dashboard_tables"],
            "name": "Dashboard"
        },
        "workflow-monitor": {
            "tables": ["workflows", "workflow_runs", "workflow_steps", "users", "api_keys"],
            "migrations": ["001_create_users_and_api_keys", "006_create_workflow_monitor_tables"],
            "name": "Workflow Monitor"
        },
        "location-tracker": {
            "tables": ["locations", "geofences", "location_alerts", "users", "api_keys"],
            "migrations": ["001_create_users_and_api_keys", "007_create_location_tracker_tables"],
            "name": "Location Tracker"
        }
    }

    # Maps global table name to definition
    table_defs_map = {t["name"]: t for t in TABLES}
    migration_defs_map = {m["name"]: m for m in MIGRATIONS}

    total_tables_created = 0
    total_relationships_created = 0
    total_migrations_created = 0
    total_snapshots_created = 0

    for app_id, config in apps_def.items():
        print(f"  --> Seeding schema for app: {app_id}...")
        
        # 1. Create tables
        table_id_map = {}  # table_name -> id
        app_tables = []
        for name in config["tables"]:
            if name not in table_defs_map:
                print(f"    [WARNING] Table definition not found for '{name}'")
                continue
            table_def = table_defs_map[name]
            table_id = generate_id()
            table_id_map[name] = table_id
            app_tables.append(table_def)

            record = SchemaTableRecord(
                id=table_id,
                name=table_def["name"],
                description=table_def.get("description"),
                schema_id=app_id,
                columns=table_def["columns"],
            )
            db.add(record)
            total_tables_created += 1

        db.commit()

        # 2. Create relationships
        app_relationships = []
        for rel_def in RELATIONSHIPS:
            if rel_def["source"] in table_id_map and rel_def["target"] in table_id_map:
                rel_id = generate_id()
                app_relationships.append(rel_def)
                record = SchemaRelationshipRecord(
                    id=rel_id,
                    name=rel_def["name"],
                    schema_id=app_id,
                    relation_type=rel_def["type"],
                    source_table_id=table_id_map[rel_def["source"]],
                    source_column=rel_def["source_col"],
                    target_table_id=table_id_map[rel_def["target"]],
                    target_column=rel_def["target_col"],
                    on_delete=rel_def.get("on_delete", "CASCADE"),
                    on_update=rel_def.get("on_update", "CASCADE"),
                    through_table=rel_def.get("through_table"),
                )
                db.add(record)
                total_relationships_created += 1

        db.commit()

        # 3. Create migrations
        for name in config["migrations"]:
            if name not in migration_defs_map:
                print(f"    [WARNING] Migration definition not found for '{name}'")
                continue
            mig_def = migration_defs_map[name]
            mig_id = generate_id()
            record = SchemaMigrationRecord(
                id=mig_id,
                name=mig_def["name"],
                schema_id=app_id,
                version=mig_def["version"],
                status="pending",
                sql_up=mig_def["sql_up"],
                sql_down=mig_def.get("sql_down"),
                diff_summary=mig_def.get("diff_summary"),
            )
            db.add(record)
            total_migrations_created += 1

        db.commit()

        # 4. Create initial snapshot
        snapshot_id = generate_id()
        snapshot = SchemaSnapshotRecord(
            id=snapshot_id,
            name=f"Initial Schema ({config['name']})",
            schema_id=app_id,
            tables_json=[
                {"name": t["name"], "columns": t["columns"]}
                for t in app_tables
            ],
            relationships_json=[
                {
                    "name": r["name"],
                    "source": r["source"],
                    "source_column": r["source_col"],
                    "target": r["target"],
                    "target_column": r["target_col"],
                    "type": r["type"],
                }
                for r in app_relationships
            ],
            meta_json={
                "table_count": len(app_tables),
                "relationship_count": len(app_relationships),
                "column_count": sum(len(t["columns"]) for t in app_tables),
                "description": f"Initial schema with tables for {config['name']}",
            },
            tags=["baseline", "milestone"],
        )
        db.add(snapshot)
        db.commit()
        total_snapshots_created += 1

    print("")
    print("[SEED] Schema seed complete!")
    print(f"  Total Tables Created: {total_tables_created}")
    print(f"  Total Relationships Created: {total_relationships_created}")
    print(f"  Total Migrations Created: {total_migrations_created}")
    print(f"  Total Snapshots Created: {total_snapshots_created}")



if __name__ == "__main__":
    seed_schema_data()
