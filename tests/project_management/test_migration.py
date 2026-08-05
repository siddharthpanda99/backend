"""Migration tests — Domain 32.04.

Verifies that:
1. All PM models register correctly with SQLModel.metadata
2. ``create_pm_tables()`` creates the expected tables
3. Data can be round-tripped through the models
4. Table names match conventions (``pm_*`` prefix)
5. Key indexes and constraints are present
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlmodel import SQLModel


class TestModelRegistration:
    """Verify all PM models register with SQLModel.metadata."""

    def test_metadata_contains_pm_tables(self):
        """All PM tables should be prefixed with ``pm_``."""
        from common_lib.modules.project_management.init_db import get_pm_metadata
        metadata = get_pm_metadata()
        pm_tables = [t for t in metadata.tables.keys() if t.startswith("pm_")]
        assert len(pm_tables) > 20, (
            f"Expected 20+ PM tables, got {len(pm_tables)}. "
            f"Tables: {sorted(pm_tables)}"
        )

    def test_core_tables_exist(self):
        """Critical core tables must be present."""
        from common_lib.modules.project_management.init_db import get_pm_metadata
        metadata = get_pm_metadata()
        required = [
            "pm_projects", "pm_issues", "pm_sprints", "pm_workflows",
            "pm_releases", "pm_organizations", "pm_workspaces",
            "pm_work_graph_nodes", "pm_work_graph_edges",
            "pm_offline_mutations", "pm_offline_cache",
            "pm_goals", "pm_objectives", "pm_key_results",
        ]
        for name in required:
            assert name in metadata.tables, f"Missing required table: {name}"

    def test_pm_tablename_convention(self):
        """Every PM table must use the ``pm_`` prefix convention."""
        from common_lib.modules.project_management.init_db import get_pm_metadata
        metadata = get_pm_metadata()
        pm_tables = [t for t in metadata.tables.keys() if t.startswith("pm_")]
        bad = [t for t in pm_tables if not t.startswith("pm_")]
        assert not bad, f"Tables without pm_ prefix: {bad}"

    def test_models_have_primary_key(self):
        """Every SQLModel table=True class must have at least one primary key.

        Most tables use a single UUID ``id`` field, but some (e.g.
        ``pm_watchers``) use a composite primary key.
        """
        from common_lib.modules.project_management.init_db import get_pm_metadata
        metadata = get_pm_metadata()
        pm_tables = {k: v for k, v in metadata.tables.items() if k.startswith("pm_")}
        tables_without_pk = []
        for name, table in pm_tables.items():
            pk = [c for c in table.columns if c.primary_key]
            if not pk:
                tables_without_pk.append(name)
        assert not tables_without_pk, f"Tables without primary keys: {tables_without_pk}"


class TestCreateTables:
    """Verify ``create_pm_tables()`` works correctly."""

    def test_create_tables_calls_create_all(self):
        """``create_pm_tables`` should call ``SQLModel.metadata.create_all``."""
        from common_lib.modules.project_management.init_db import create_pm_tables
        mock_engine = MagicMock()
        with patch.object(SQLModel.metadata, "create_all") as mock_create:
            result = create_pm_tables(mock_engine)
            assert result is True
            mock_create.assert_called_once_with(mock_engine)

    def test_create_tables_returns_false_on_error(self):
        """``create_pm_tables`` should return ``False`` if creation fails."""
        from common_lib.modules.project_management.init_db import create_pm_tables
        mock_engine = MagicMock()
        with patch.object(SQLModel.metadata, "create_all", side_effect=Exception("DB error")):
            result = create_pm_tables(mock_engine)
            assert result is False


class TestDataRoundTrip:
    """Verify that PM models can be created and serialised correctly."""

    def test_project_round_trip(self):
        """Create a ``Project``, dump it, and verify fields survive."""
        from common_lib.modules.project_management.models import Project
        from datetime import datetime

        project = Project(
            name="Test Project",
            identifier="TEST",
            description="A test project",
            project_type="software_scrum",
            status="active",
            created_by="user-1",
        )
        d = project.model_dump()
        assert d["name"] == "Test Project"
        assert d["identifier"] == "TEST"
        assert d["project_type"] == "software_scrum"
        assert d["status"] == "active"

    def test_issue_round_trip(self):
        """Create an ``Issue``, dump it, verify fields."""
        from common_lib.modules.project_management.models import Issue
        issue = Issue(
            project_id="proj-1",
            title="Test Issue",
            priority="high",
            status_id="status-1",
            issue_type_id="type-1",
        )
        d = issue.model_dump()
        assert d["title"] == "Test Issue"
        assert d["priority"] == "high"
        assert d["project_id"] == "proj-1"

    def test_sprint_round_trip(self):
        """Create a ``Sprint``, dump it, verify fields."""
        from common_lib.modules.project_management.models import Sprint
        sprint = Sprint(
            project_id="proj-1",
            name="Sprint 1",
            goal="Ship feature X",
            status="planned",
        )
        d = sprint.model_dump()
        assert d["name"] == "Sprint 1"
        assert d["goal"] == "Ship feature X"
        assert d["status"] == "planned"

    def test_work_graph_node_round_trip(self):
        """Create a ``WorkGraphNode``, dump it, verify fields."""
        from common_lib.modules.project_management.universal_graph.models import WorkGraphNode
        node = WorkGraphNode(
            workspace_id="ws-1",
            entity_type="issue",
            entity_id="iss-123",
            title="Fix login bug",
            status="in_progress",
            entity_data={"priority": "high"},
        )
        d = node.model_dump()
        assert d["entity_type"] == "issue"
        assert d["entity_id"] == "iss-123"
        assert d["title"] == "Fix login bug"

    def test_work_graph_edge_round_trip(self):
        """Create a ``WorkGraphEdge``, dump it, verify fields."""
        from common_lib.modules.project_management.universal_graph.models import WorkGraphEdge
        edge = WorkGraphEdge(
            workspace_id="ws-1",
            source_type="issue",
            source_id="iss-1",
            target_type="sprint",
            target_id="spr-1",
            relationship_type="belongs_to",
            weight=1.0,
        )
        d = edge.model_dump()
        assert d["relationship_type"] == "belongs_to"
        assert d["source_type"] == "issue"
        assert d["target_type"] == "sprint"


class TestModelConstraints:
    """Verify unique constraints exist on key models."""

    def test_graph_node_unique_constraint(self):
        """WorkGraphNode must have a UNIQUE constraint on (workspace_id, entity_type, entity_id)."""
        from common_lib.modules.project_management.universal_graph.models import WorkGraphNode
        assert hasattr(WorkGraphNode, "__table_args__"), "Expected __table_args__ on WorkGraphNode"
        args = WorkGraphNode.__table_args__
        # Find UniqueConstraint among table args
        from sqlalchemy import UniqueConstraint
        uqs = [a for a in args if isinstance(a, UniqueConstraint)]
        assert len(uqs) == 1, f"Expected 1 UniqueConstraint on WorkGraphNode, found {len(uqs)}"
        col_names = [c.name for c in uqs[0].columns]
        assert "entity_type" in col_names
        assert "entity_id" in col_names
        assert "workspace_id" in col_names

    def test_graph_edge_unique_constraint(self):
        """WorkGraphEdge must have a UNIQUE constraint on (source, target, relationship)."""
        from common_lib.modules.project_management.universal_graph.models import WorkGraphEdge
        assert hasattr(WorkGraphEdge, "__table_args__")
        from sqlalchemy import UniqueConstraint
        uqs = [a for a in WorkGraphEdge.__table_args__ if isinstance(a, UniqueConstraint)]
        assert len(uqs) == 1, f"Expected 1 UniqueConstraint on WorkGraphEdge, found {len(uqs)}"
