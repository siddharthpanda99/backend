"""Tests for Policy Engine — explicit deny, ABAC, ReBAC, wildcards.

Uses raw SQLAlchemy to avoid metadata conflicts with SQLModel.
"""


from tests.rbac.conftest import rbac_policy_rules, policy_rules, rbac_abac_conditions, abac_conditions, rbac_rebac_relations, rebac_relations

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, MetaData, Table, Column, String, Boolean, DateTime, Integer, JSON
from sqlalchemy.orm import Session

# ===========================================================================
# Explicit Deny Tests
# ===========================================================================

class TestExplicitDeny:
    def test_explicit_deny_overrides_allow(self, db):
        db.execute(policy_rules.insert().values(
            id="allow-1", name="Allow project read", enabled=True,
            effect="allow", resource_type="project", actions=["read"],
            priority=200,
        ))
        db.execute(policy_rules.insert().values(
            id="deny-1", name="Deny project read for user 42", enabled=True,
            effect="deny", resource_type="project", actions=["read"],
            subject_ids=["42"], priority=100,
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ExplicitDenyResolver
        resolver = ExplicitDenyResolver(db)

        denied, rule = resolver.has_explicit_deny(42, "project", "read")
        assert denied is True
        assert rule == "Deny project read for user 42"

        denied, rule = resolver.has_explicit_deny(99, "project", "read")
        assert denied is False

    def test_disabled_deny_rule_ignored(self, db):
        db.execute(policy_rules.insert().values(
            id="deny-disabled", name="Disabled deny", enabled=False,
            effect="deny", resource_type="project", actions=["read"],
            subject_ids=["1"], priority=10,
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ExplicitDenyResolver
        resolver = ExplicitDenyResolver(db)
        denied, _ = resolver.has_explicit_deny(1, "project", "read")
        assert denied is False

    def test_wildcard_deny_matches_all_users(self, db):
        db.execute(policy_rules.insert().values(
            id="deny-all", name="Deny all delete", enabled=True,
            effect="deny", resource_type="project", actions=["delete"],
            priority=10,
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ExplicitDenyResolver
        resolver = ExplicitDenyResolver(db)
        denied, rule = resolver.has_explicit_deny(1, "project", "delete")
        assert denied is True
        assert rule == "Deny all delete"

    def test_deny_precedence_over_rbac(self, db):
        db.execute(policy_rules.insert().values(
            id="deny-2", name="Deny write", enabled=True,
            effect="deny", resource_type="issue", actions=["write"],
            subject_ids=["5"], priority=50,
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ExplicitDenyResolver
        resolver = ExplicitDenyResolver(db)
        result = resolver.resolve_with_deny_precedence(
            allow=True, user_id=5, resource_type="issue", action="write"
        )
        assert result.allowed is False
        assert result.decision.value == "deny"
        assert result.denied_by == "Deny write"

# ===========================================================================
# ABAC Tests
# ===========================================================================

class TestABAC:
    def test_equals_condition(self, db):
        db.execute(abac_conditions.insert().values(
            id="cond-1", name="Must be admin role", enabled=True,
            attribute_source="subject", attribute_name="role",
            operator="equals", value="admin", value_type="string",
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ABACEvaluator
        evaluator = ABACEvaluator(db)

        assert evaluator.evaluate_condition("cond-1", {"subject": {"role": "admin"}, "resource": {}, "context": {}}) is True
        assert evaluator.evaluate_condition("cond-1", {"subject": {"role": "viewer"}, "resource": {}, "context": {}}) is False

    def test_in_condition(self, db):
        db.execute(abac_conditions.insert().values(
            id="cond-2", name="Team in allowed", enabled=True,
            attribute_source="subject", attribute_name="team",
            operator="in", value="backend,frontend,devops", value_type="list",
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ABACEvaluator
        evaluator = ABACEvaluator(db)

        assert evaluator.evaluate_condition("cond-2", {"subject": {"team": "backend"}, "resource": {}, "context": {}}) is True
        assert evaluator.evaluate_condition("cond-2", {"subject": {"team": "marketing"}, "resource": {}, "context": {}}) is False

    def test_numeric_condition(self, db):
        db.execute(abac_conditions.insert().values(
            id="cond-3", name="Priority >= high", enabled=True,
            attribute_source="resource", attribute_name="priority_num",
            operator="gte", value="7", value_type="number",
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ABACEvaluator
        evaluator = ABACEvaluator(db)

        assert evaluator.evaluate_condition("cond-3", {"subject": {}, "resource": {"priority_num": 8}, "context": {}}) is True
        assert evaluator.evaluate_condition("cond-3", {"subject": {}, "resource": {"priority_num": 5}, "context": {}}) is False

    def test_and_logic(self, db):
        db.execute(abac_conditions.insert().values(
            id="cond-a", name="Role admin", enabled=True,
            attribute_source="subject", attribute_name="role",
            operator="equals", value="admin", value_type="string",
        ))
        db.execute(abac_conditions.insert().values(
            id="cond-b", name="Team backend", enabled=True,
            attribute_source="subject", attribute_name="team",
            operator="equals", value="backend", value_type="string",
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ABACEvaluator
        evaluator = ABACEvaluator(db)

        attrs = {"subject": {"role": "admin", "team": "backend"}, "resource": {}, "context": {}}
        assert evaluator.evaluate_rule_conditions(["cond-a", "cond-b"], "and", attrs) is True

        attrs2 = {"subject": {"role": "admin", "team": "marketing"}, "resource": {}, "context": {}}
        assert evaluator.evaluate_rule_conditions(["cond-a", "cond-b"], "and", attrs2) is False

    def test_or_logic(self, db):
        db.execute(abac_conditions.insert().values(
            id="cond-c", name="Role admin", enabled=True,
            attribute_source="subject", attribute_name="role",
            operator="equals", value="admin", value_type="string",
        ))
        db.execute(abac_conditions.insert().values(
            id="cond-d", name="Role auditor", enabled=True,
            attribute_source="subject", attribute_name="role",
            operator="equals", value="auditor", value_type="string",
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ABACEvaluator
        evaluator = ABACEvaluator(db)

        attrs = {"subject": {"role": "admin"}, "resource": {}, "context": {}}
        assert evaluator.evaluate_rule_conditions(["cond-c", "cond-d"], "or", attrs) is True

        attrs2 = {"subject": {"role": "viewer"}, "resource": {}, "context": {}}
        assert evaluator.evaluate_rule_conditions(["cond-c", "cond-d"], "or", attrs2) is False

# ===========================================================================
# ReBAC Tests
# ===========================================================================

class TestReBAC:
    def test_has_relation(self, db):
        db.execute(rebac_relations.insert().values(
            id="rel-1", subject_type="user", subject_id="1",
            relation="owns", object_type="project", object_id="proj-1",
            granted_at=datetime.utcnow(),
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(db)

        assert evaluator.has_relation("user", "1", "owns", "project", "proj-1") is True
        assert evaluator.has_relation("user", "1", "member_of", "project", "proj-1") is False
        assert evaluator.has_relation("user", "1", "owns", "project", "proj-2") is False

    def test_expired_relation_ignored(self, db):
        db.execute(rebac_relations.insert().values(
            id="rel-expired", subject_type="user", subject_id="2",
            relation="owns", object_type="project", object_id="proj-3",
            granted_at=datetime.utcnow(),
            expires_at=datetime.utcnow() - timedelta(hours=1),
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(db)
        assert evaluator.has_relation("user", "2", "owns", "project", "proj-3") is False

    def test_revoked_relation_ignored(self, db):
        db.execute(rebac_relations.insert().values(
            id="rel-revoked", subject_type="user", subject_id="3",
            relation="editor", object_type="issue", object_id="iss-1",
            granted_at=datetime.utcnow(),
            revoked_at=datetime.utcnow(),
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(db)
        assert evaluator.has_relation("user", "3", "editor", "issue", "iss-1") is False

    def test_grant_and_revoke(self, db):
        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(db)

        rel = evaluator.grant_relation("user", "10", "member_of", "team", "team-1")
        assert rel.id is not None
        assert evaluator.has_relation("user", "10", "member_of", "team", "team-1") is True

        success = evaluator.revoke_relation("user", "10", "member_of", "team", "team-1")
        assert success is True
        assert evaluator.has_relation("user", "10", "member_of", "team", "team-1") is False

    def test_grant_is_idempotent(self, db):
        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(db)

        rel1 = evaluator.grant_relation("user", "20", "owns", "project", "p1")
        rel2 = evaluator.grant_relation("user", "20", "owns", "project", "p1")
        assert rel1.id == rel2.id

    def test_get_related_objects(self, db):
        db.execute(rebac_relations.insert().values(
            id="rel-list-1", subject_type="user", subject_id="5",
            relation="owns", object_type="project", object_id="p1",
            granted_at=datetime.utcnow(),
        ))
        db.execute(rebac_relations.insert().values(
            id="rel-list-2", subject_type="user", subject_id="5",
            relation="owns", object_type="project", object_id="p2",
            granted_at=datetime.utcnow(),
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(db)
        rels = evaluator.get_related_objects("user", "5", "owns", "project")
        assert len(rels) == 2

    def test_get_related_subjects(self, db):
        """Test reverse lookup — who relates to an object."""
        db.execute(rebac_relations.insert().values(
            id="rel-subj-1", subject_type="user", subject_id="100",
            relation="owns", object_type="project", object_id="proj-x",
            granted_at=datetime.utcnow(),
        ))
        db.execute(rebac_relations.insert().values(
            id="rel-subj-2", subject_type="user", subject_id="101",
            relation="editor", object_type="project", object_id="proj-x",
            granted_at=datetime.utcnow(),
        ))
        db.execute(rebac_relations.insert().values(
            id="rel-subj-3", subject_type="team", subject_id="team-99",
            relation="member_of", object_type="project", object_id="proj-x",
            granted_at=datetime.utcnow(),
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(db)

        all_subj = evaluator.get_related_subjects("project", "proj-x")
        assert len(all_subj) == 3

        users = evaluator.get_related_subjects("project", "proj-x", subject_type="user")
        assert len(users) == 2

        owners = evaluator.get_related_subjects("project", "proj-x", relation="owns")
        assert len(owners) == 1
        assert owners[0].subject_id == "100"

    def test_transitive_same_relation_chain(self, db):
        """Test BFS transitive traversal with same relation type:
        user → manages team → manages project.
        """
        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(db)

        # user 1 manages team A (transitive)
        evaluator.grant_relation("user", "1", "manages", "team", "team-A", transitive=True)
        # team A manages project P1 (transitive)
        evaluator.grant_relation("team", "team-A", "manages", "project", "p1", transitive=True)

        # user 1 should have transitive "manages" to project p1 via team-A
        assert evaluator.resolve_transitive("user", "1", "manages", "project", "p1") is True

        # user 1 should NOT have transitive "owns" (different relation type)
        assert evaluator.resolve_transitive("user", "1", "owns", "project", "p1") is False

        # user 1 should NOT reach project p2 (no chain)
        assert evaluator.resolve_transitive("user", "1", "manages", "project", "p2") is False

    def test_transitive_max_depth(self, db):
        """Test BFS respects max_depth limit."""
        from common_lib.modules.rbac.policies.service import ReBACEvaluator
        evaluator = ReBACEvaluator(db)

        # 4-hop chain: user → team-A → team-B → team-C → project
        evaluator.grant_relation("user", "1", "manages", "team", "team-A", transitive=True)
        evaluator.grant_relation("team", "team-A", "manages", "team", "team-B", transitive=True)
        evaluator.grant_relation("team", "team-B", "manages", "team", "team-C", transitive=True)
        evaluator.grant_relation("team", "team-C", "manages", "project", "p-deep", transitive=True)

        # max_depth=2 should NOT reach (team-C at depth 3 > 2)
        assert evaluator.resolve_transitive("user", "1", "manages", "project", "p-deep", max_depth=2) is False
        # max_depth=3 should reach (team-C at depth 3 <= 3)
        assert evaluator.resolve_transitive("user", "1", "manages", "project", "p-deep", max_depth=3) is True
        # max_depth=5 should also reach
        assert evaluator.resolve_transitive("user", "1", "manages", "project", "p-deep", max_depth=5) is True

# ===========================================================================
# Policy Engine Integration Tests
# ===========================================================================

class TestPolicyEngine:
    def test_explicit_deny_blocks_rbac_allow(self, db):
        db.execute(policy_rules.insert().values(
            id="pe-deny", name="Block admin delete", enabled=True,
            effect="deny", resource_type="project", actions=["delete"],
            subject_ids=["1"], priority=10,
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import PolicyEngine
        engine = PolicyEngine(db)
        result = engine.evaluate(1, "project", "delete", rbac_allowed=True)
        assert result.allowed is False
        assert result.decision.value == "deny"
        assert result.denied_by == "Block admin delete"

    def test_no_deny_and_rbac_allowed(self, db):
        from common_lib.modules.rbac.policies.service import PolicyEngine
        engine = PolicyEngine(db)
        result = engine.evaluate(1, "project", "read", rbac_allowed=True)
        assert result.allowed is True
        assert result.decision.value == "allow"

    def test_simulate_returns_reasoning(self, db):
        db.execute(policy_rules.insert().values(
            id="pe-sim", name="Allow project read", enabled=True,
            effect="allow", resource_type="project", actions=["read"],
            priority=100,
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import PolicyEngine
        engine = PolicyEngine(db)
        result = engine.simulate(1, "project", "read")
        assert "final_decision" in result
        assert "reasoning" in result
        assert isinstance(result["reasoning"], list)
        assert len(result["reasoning"]) >= 1

    def test_context_normalization_flat_dict(self, db):
        """Flat context dict is normalized to nested ABAC format."""
        from common_lib.modules.rbac.policies.service import PolicyEngine
        engine = PolicyEngine(db)

        db.execute(abac_conditions.insert().values(
            id="norm-cond", name="Role check", enabled=True,
            attribute_source="subject", attribute_name="role",
            operator="equals", value="admin", value_type="string",
        ))
        db.commit()

        result = engine.simulate(1, "project", "read", context={"role": "admin"})
        assert result["final_decision"] in ("allow", "deny")
        abac_info = result.get("abac", {})
        assert "matched_conditions" in abac_info

    def test_abac_condition_integration(self, db):
        db.execute(abac_conditions.insert().values(
            id="pe-abac-1", name="Must be admin", enabled=True,
            attribute_source="subject", attribute_name="role",
            operator="equals", value="admin", value_type="string",
        ))
        db.execute(policy_rules.insert().values(
            id="pe-abac-rule", name="Conditional allow", enabled=True,
            effect="allow", resource_type="project", actions=["read"],
            condition_ids=["pe-abac-1"], conditions_logic="and",
            priority=50,
        ))
        db.commit()

        from common_lib.modules.rbac.policies.service import PolicyEngine
        engine = PolicyEngine(db)
        result = engine.evaluate(1, "project", "read", context={"subject": {"role": "admin"}, "resource": {}, "context": {}})
        assert result.allowed is True

        result2 = engine.evaluate(1, "project", "read", context={"subject": {"role": "viewer"}, "resource": {}, "context": {}})
        assert result2.allowed is False
