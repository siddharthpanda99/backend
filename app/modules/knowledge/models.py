"""
Knowledge Engine — SQLModel Database Models.

Persistent storage for knowledge chunks, replacing the in-memory _chunk_store.
Uses SQLModel for multi-backend support (PostgreSQL in prod, SQLite in dev).

KnowledgeChunkRecord has been migrated to common_lib. This module re-exports
it for backwards compatibility — new code should import directly from:
    common_lib.modules.knowledge_engine.models.db_records
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlmodel import JSON, Column, Field, SQLModel

from common_lib.modules.knowledge_engine.models.db_records import (
    KnowledgeChunkRecord,
)


class SelfAssessmentRecord(SQLModel, table=True):
    """Persistent storage for self-assessment reports.

    Replaces in-memory storage in SelfAssessmentFinder so reports
    survive server restarts.
    """

    __tablename__ = "knowledge_self_assessments"

    id: Optional[int] = Field(default=None, primary_key=True)
    report_id: str = Field(
        default_factory=lambda: f"sa_{uuid4().hex[:12]}",
        index=True,
        unique=True,
        description="Unique report identifier",
    )
    overall_health_score: float = Field(
        default=0.0, description="Overall system health score 0-1"
    )
    strategy_generation: int = Field(
        default=0, description="Strategy generation at assessment time"
    )

    # JSON fields for nested report data
    quality_metrics_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )
    method_scores_json: dict[str, float] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )
    strategy_weights_json: dict[str, float] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )
    failure_stats_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )
    beliefs_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )
    findings_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    recommendations_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class ComponentConfigRecord(SQLModel, table=True):
    """Single table for all self-learning configurations.

    Each row stores config data for one category: one of the 9 component
    types (qualityLog, autoEvolve, scorer, failure, reasoner, belief,
    conflict, branching, pruner) or 'full' for a complete instance bundle.

    Rows with the same instance_id form a logical instance group.
    The 'full' category row carries the instance identity (name, description,
    tags, variant) inside config_data.

    Schema validation per category is enforced at the application layer.
    """

    __tablename__ = "self_learning_component_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    instance_id: str = Field(
        default_factory=lambda: f"sl_{uuid4().hex[:12]}",
        index=True,
        description="Grouping key for rows belonging to the same instance",
    )
    category: str = Field(
        default="",
        description="Config category: qualityLog | autoEvolve | scorer | failure | reasoner | belief | conflict | branching | pruner | full",
    )
    config_data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Per-category config data; validated at code level",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc).replace(tzinfo=None)
        },
    )


__all__ = [
    "KnowledgeChunkRecord",
    "SelfAssessmentRecord",
    "ComponentConfigRecord",
]
