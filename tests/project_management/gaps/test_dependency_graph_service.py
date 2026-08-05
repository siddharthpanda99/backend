"""Tests for Dependency Graph (Module 15)."""

import pytest
from sqlmodel import Session, create_engine, SQLModel
from common_lib.modules.project_management.dependency_graph.service import DependencyGraphService
from common_lib.modules.project_management.dependency_graph.models import DependencyMatrixCell, DependencyGraphSnapshot


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    # Create ALL pm_* tables to satisfy FK references
    pm_tables = [
        t for name, t in SQLModel.metadata.tables.items()
        if name.startswith("pm_")
    ]
    SQLModel.metadata.create_all(engine, tables=pm_tables)
    s = Session(engine)
    yield s
    s.close()


class TestDependencyGraph:
    def test_build_graph_empty_scope(self, session):
        svc = DependencyGraphService(session)
        result = svc.build_graph(scope_type="project", scope_id="nonexistent")
        assert "nodes" in result
        assert "edges" in result
        assert isinstance(result["nodes"], list)

    def test_build_matrix_empty_scope(self, session):
        svc = DependencyGraphService(session)
        result = svc.build_matrix(scope_type="project", scope_id="nonexistent")
        assert "matrix" in result
        assert "issue_ids" in result

    def test_get_latest_snapshot_empty(self, session):
        svc = DependencyGraphService(session)
        result = svc.get_latest_snapshot(scope_type="project", scope_id="nonexistent")
        assert result is None

    def test_has_circular_dependency_no_cycle(self, session):
        svc = DependencyGraphService(session)
        is_circular = svc.has_circular_dependency("issue-1", "issue-2")
        assert is_circular is False

    def test_get_dependency_warnings_empty(self, session):
        svc = DependencyGraphService(session)
        warnings = svc.get_dependency_warnings(scope_type="sprint", scope_id="sprint-1")
        assert isinstance(warnings, list)


class TestCircularDetection:
    def test_would_create_cycle_no_data(self, session):
        svc = DependencyGraphService(session)
        assert svc._would_create_cycle("a", "b") is False

    def test_find_circular_deps_empty(self, session):
        svc = DependencyGraphService(session)
        cycles = svc._find_circular_deps([], [])
        assert cycles == []

    def test_find_circular_deps_no_cycle(self, session):
        svc = DependencyGraphService(session)
        nodes = [{"id": "a"}, {"id": "b"}]
        edges = [{"source": "a", "target": "b"}]
        cycles = svc._find_circular_deps(nodes, edges)
        assert cycles == []
