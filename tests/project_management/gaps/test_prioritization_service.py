"""Tests for Prioritization (RICE/ICE/MoSCoW)."""

import pytest
from sqlmodel import Session, create_engine, SQLModel
from common_lib.modules.project_management.prioritization.service import PrioritizationService
from common_lib.modules.project_management.prioritization.models import PrioritizationScore, ScoringFormula


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


class TestRICE:
    def test_score_rice(self, session):
        svc = PrioritizationService(session)
        result = svc.score_rice(
            entity_type="issue", entity_id="issue-1",
            reach=100, impact=3, confidence=0.8, effort=5,
        )
        assert result["framework"] == "rice"
        # (100 * 3 * 0.8) / 5 = 48
        assert result["total_score"] == 48.0

    def test_rice_zero_effort(self, session):
        svc = PrioritizationService(session)
        result = svc.score_rice(
            entity_type="issue", entity_id="issue-2",
            reach=100, impact=3, confidence=0.8, effort=0,
        )
        assert result["total_score"] > 0  # Should not crash


class TestICE:
    def test_score_ice(self, session):
        svc = PrioritizationService(session)
        result = svc.score_ice(
            entity_type="feature", entity_id="feature-1",
            impact=8, confidence=7, ease=6,
        )
        assert result["framework"] == "ice"
        assert result["total_score"] == 336  # 8 * 7 * 6


class TestMoSCoW:
    def test_classify_must(self, session):
        svc = PrioritizationService(session)
        result = svc.classify_moscow(
            entity_type="issue", entity_id="issue-1",
            classification="must",
        )
        assert result["classification"] == "must"
        assert result["total_score"] == 100

    def test_classify_wont(self, session):
        svc = PrioritizationService(session)
        result = svc.classify_moscow(
            entity_type="issue", entity_id="issue-2",
            classification="wont",
        )
        assert result["classification"] == "wont"
        assert result["total_score"] == 0


class TestCustom:
    def test_create_formula(self, session):
        svc = PrioritizationService(session)
        formula = svc.create_formula(
            name="Custom Score",
            expression="reach * impact * confidence / effort",
            parameter_names=["reach", "impact", "confidence", "effort"],
        )
        assert formula["name"] == "Custom Score"

    def test_score_custom_formula_not_found(self, session):
        svc = PrioritizationService(session)
        result = svc.score_custom("issue", "i-1", formula_id="nonexistent", params={})
        assert result is None


class TestQueries:
    def test_get_scores(self, session):
        svc = PrioritizationService(session)
        svc.score_rice("issue", "i-1", reach=10, impact=3, confidence=0.8, effort=5)
        scores = svc.get_scores("issue", "i-1")
        assert len(scores) >= 1

    def test_list_by_framework(self, session):
        svc = PrioritizationService(session)
        svc.score_rice("issue", "i-1", reach=10, impact=3, confidence=0.8, effort=5)
        top = svc.list_by_framework(framework="rice", limit=10)
        assert len(top) >= 1
