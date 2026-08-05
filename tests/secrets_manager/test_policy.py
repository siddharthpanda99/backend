"""
Tests for Secrets Manager Policy submodule (SSOT 02).

Tests policy CRUD, evaluation, binding (by path AND secret_id), and edge cases.
"""
from __future__ import annotations

import pytest
from common_lib.modules.secrets_manager.policy.service import PolicyEngine
from common_lib.modules.secrets_manager.policy.models import PolicyRule, PolicyCondition, PolicyEffect


class TestPolicyEngine:
    """Test policy CRUD, evaluation, and binding."""

    def test_create_policy(self, db):
        engine = PolicyEngine(session=db)
        rules = [{"actions": ["read_value"], "effect": "allow", "resources": ["secret:test-*"]}]
        result = engine.create_policy(name="test-policy", rules=rules, description="Test policy")
        assert result["name"] == "test-policy"
        assert "id" in result

    def test_get_policy(self, db):
        engine = PolicyEngine(session=db)
        rules = [{"actions": ["read_value"], "effect": "allow", "resources": ["*"]}]
        engine.create_policy(name="get-test", rules=rules)
        result = engine.get_policy(name="get-test")
        assert result is not None
        assert result["name"] == "get-test"
        assert len(result["rules"]) == 1

    def test_get_policy_not_found(self, db):
        engine = PolicyEngine(session=db)
        assert engine.get_policy(name="nonexistent") is None

    def test_list_policies(self, db):
        engine = PolicyEngine(session=db)
        rules = [{"actions": ["*"], "effect": "allow", "resources": ["*"]}]
        engine.create_policy(name="list-1", rules=rules)
        engine.create_policy(name="list-2", rules=rules)
        policies = engine.list_policies()
        assert len(policies) >= 2
        names = [p["name"] for p in policies]
        assert "list-1" in names
        assert "list-2" in names

    def test_delete_policy(self, db):
        engine = PolicyEngine(session=db)
        rules = [{"actions": ["*"], "effect": "allow", "resources": ["*"]}]
        engine.create_policy(name="delete-test", rules=rules)
        assert engine.delete_policy(name="delete-test") is True
        assert engine.get_policy(name="delete-test") is None

    def test_delete_policy_not_found(self, db):
        engine = PolicyEngine(session=db)
        assert engine.delete_policy(name="nonexistent") is False

    def test_evaluate_allow(self, db):
        """Test that a matching allow rule returns allowed=True."""
        engine = PolicyEngine(session=db)
        rules = [{"actions": ["read_value"], "effect": "allow", "resources": ["secret:api-key"]}]
        engine.create_policy(name="allow-test", rules=rules)
        engine.bind_policy(policy_name="allow-test", path="secret:api-key")

        result = engine.evaluate(action="read_value", resource="secret:api-key")
        assert result["allowed"] is True
        assert result["matched_policy"] == "allow-test"

    def test_evaluate_explicit_deny(self, db):
        """Test that explicit deny takes precedence."""
        engine = PolicyEngine(session=db)
        rules = [
            {"actions": ["read_value"], "effect": "deny", "resources": ["secret:api-key"]},
            {"actions": ["read_value"], "effect": "allow", "resources": ["*"]},
        ]
        engine.create_policy(name="deny-test", rules=rules)
        engine.bind_policy(policy_name="deny-test", path="secret:api-key")

        result = engine.evaluate(action="read_value", resource="secret:api-key")
        assert result["allowed"] is False
        assert result["reason"] == "explicit_deny"

    def test_evaluate_deny_by_default(self, db):
        """Test that no matching rule returns denied."""
        engine = PolicyEngine(session=db)
        rules = [{"actions": ["write_value"], "effect": "allow", "resources": ["*"]}]
        engine.create_policy(name="default-deny", rules=rules)
        engine.bind_policy(policy_name="default-deny", path="/")

        result = engine.evaluate(action="read_value", resource="secret:something")
        assert result["allowed"] is False
        assert result["reason"] == "no_matching_rule"

    def test_evaluate_secret_id_binding(self, db):
        """Test that evaluate checks secret_id bindings in addition to path bindings."""
        engine = PolicyEngine(session=db)

        # Create a policy bound by secret_id
        rules = [{"actions": ["admin_action"], "effect": "allow", "resources": ["*"]}]
        engine.create_policy(name="secret-id-policy", rules=rules)
        engine.bind_policy(policy_name="secret-id-policy", secret_id="sec-001-uuid")

        # Evaluate with secret_id — should match
        result = engine.evaluate(
            action="admin_action",
            resource="secret:some-secret",
            secret_id="sec-001-uuid",
        )
        assert result["allowed"] is True
        assert result["matched_policy"] == "secret-id-policy"

    def test_evaluate_both_path_and_secret_id_bindings(self, db):
        """Test that both path and secret_id bindings are checked."""
        engine = PolicyEngine(session=db)

        # Create a path-bound policy
        rules1 = [{"actions": ["read"], "effect": "allow", "resources": ["/prod/*"]}]
        engine.create_policy(name="path-policy", rules=rules1)
        engine.bind_policy(policy_name="path-policy", path="/prod/path-secret")

        # Create a secret_id-bound policy
        rules2 = [{"actions": ["admin"], "effect": "allow", "resources": ["*"]}]
        engine.create_policy(name="secret-bound-policy", rules=rules2)
        engine.bind_policy(policy_name="secret-bound-policy", secret_id="sec-002")

        # Path-based check
        result_path = engine.evaluate(action="read", resource="/prod/path-secret")
        assert result_path["allowed"] is True
        assert result_path["matched_policy"] == "path-policy"

        # Secret_id-based check
        result_secret = engine.evaluate(
            action="admin",
            resource="secret:something",
            secret_id="sec-002",
        )
        assert result_secret["allowed"] is True
        assert result_secret["matched_policy"] == "secret-bound-policy"

    def test_evaluate_path_priority_over_secret_id(self, db):
        """Test that path bindings take priority over secret_id bindings (first match wins)."""
        engine = PolicyEngine(session=db)

        # Path-bound policy that denies
        deny_rules = [{"actions": ["delete"], "effect": "deny", "resources": ["/app/*"]}]
        engine.create_policy(name="deny-path", rules=deny_rules)
        engine.bind_policy(policy_name="deny-path", path="/app/prod-secret")

        # Secret_id-bound policy that allows
        allow_rules = [{"actions": ["delete"], "effect": "allow", "resources": ["*"]}]
        engine.create_policy(name="allow-secret", rules=allow_rules)
        engine.bind_policy(policy_name="allow-secret", secret_id="sec-003")

        # Check with both — path binding evaluated first (deny)
        result = engine.evaluate(
            action="delete",
            resource="/app/prod-secret",
            secret_id="sec-003",
        )
        assert result["allowed"] is False  # Path deny wins (first in binding list)
        assert result["matched_policy"] == "deny-path"

    def test_find_binding_by_secret_id(self, db):
        """Test list_bindings can filter by secret_id."""
        engine = PolicyEngine(session=db)
        rules = [{"actions": ["*"], "effect": "allow", "resources": ["*"]}]
        engine.create_policy(name="bind-secret", rules=rules)
        engine.bind_policy(policy_name="bind-secret", secret_id="abc-123")

        bindings = engine.list_bindings(secret_id="abc-123")
        assert len(bindings) == 1
        assert bindings[0]["secret_id"] == "abc-123"

    def test_find_binding_by_path(self, db):
        """Test list_bindings can filter by path."""
        engine = PolicyEngine(session=db)
        rules = [{"actions": ["*"], "effect": "allow", "resources": ["*"]}]
        engine.create_policy(name="bind-path", rules=rules)
        engine.bind_policy(policy_name="bind-path", path="/test/")

        bindings = engine.list_bindings(path="/test/")
        assert len(bindings) == 1
        assert bindings[0]["path"] == "/test/"

    def test_check_secret_access(self, db):
        """Test check_secret_access works with both path and secret_id bindings."""
        engine = PolicyEngine(session=db)
        rules = [{"actions": ["read_value"], "effect": "allow", "resources": ["*"]}]
        engine.create_policy(name="access-check", rules=rules)
        engine.bind_policy(policy_name="access-check", path="secret:test-secret")
        allowed = engine.check_secret_access(secret_name="test-secret")
        assert allowed is True


class TestPolicyRule:
    """Unit tests for PolicyRule evaluation."""

    def test_action_match(self):
        rule = PolicyRule(actions=["read_value"], effect=PolicyEffect.ALLOW, resources=["*"])
        assert rule.evaluate("read_value", "any-resource", {}) is True

    def test_action_no_match(self):
        rule = PolicyRule(actions=["read_value"], effect=PolicyEffect.ALLOW, resources=["*"])
        assert rule.evaluate("write_value", "any-resource", {}) is None

    def test_wildcard_action(self):
        rule = PolicyRule(actions=["*"], effect=PolicyEffect.ALLOW, resources=["*"])
        assert rule.evaluate("anything", "any-resource", {}) is True

    def test_resource_match_exact(self):
        rule = PolicyRule(actions=["*"], effect=PolicyEffect.ALLOW, resources=["secret:api-key"])
        assert rule.evaluate("read_value", "secret:api-key", {}) is True
        assert rule.evaluate("read_value", "secret:other", {}) is None

    def test_resource_wildcard(self):
        rule = PolicyRule(actions=["*"], effect=PolicyEffect.ALLOW, resources=["secret:*"])
        assert rule.evaluate("read_value", "secret:api-key", {}) is True
        assert rule.evaluate("read_value", "secret:something-else", {}) is True
        assert rule.evaluate("read_value", "other:thing", {}) is None

    def test_deny_effect(self):
        rule = PolicyRule(actions=["*"], effect=PolicyEffect.DENY, resources=["*"])
        assert rule.evaluate("anything", "any", {}) is False

    def test_condition_met(self):
        condition = PolicyCondition(field="ip", operator="eq", value="10.0.0.1")
        rule = PolicyRule(
            actions=["*"], effect=PolicyEffect.ALLOW, resources=["*"],
            conditions=[condition],
        )
        assert rule.evaluate("read", "x", {"ip": "10.0.0.1"}) is True

    def test_condition_not_met(self):
        condition = PolicyCondition(field="ip", operator="eq", value="10.0.0.1")
        rule = PolicyRule(
            actions=["*"], effect=PolicyEffect.ALLOW, resources=["*"],
            conditions=[condition],
        )
        # Condition not met → rule is skipped (returns None)
        assert rule.evaluate("read", "x", {"ip": "192.168.0.1"}) is None

    def test_condition_exists(self):
        condition = PolicyCondition(field="user.role", operator="exists", value=None)
        rule = PolicyRule(
            actions=["*"], effect=PolicyEffect.ALLOW, resources=["*"],
            conditions=[condition],
        )
        assert rule.evaluate("read", "x", {"user": {"role": "admin"}}) is True
        assert rule.evaluate("read", "x", {"user": {}}) is None


class TestPolicyCondition:
    """Unit tests for PolicyCondition evaluation."""

    def test_eq(self):
        c = PolicyCondition(field="env", operator="eq", value="prod")
        assert c.evaluate({"env": "prod"}) is True
        assert c.evaluate({"env": "dev"}) is False

    def test_neq(self):
        c = PolicyCondition(field="env", operator="neq", value="prod")
        assert c.evaluate({"env": "dev"}) is True
        assert c.evaluate({"env": "prod"}) is False

    def test_in(self):
        c = PolicyCondition(field="role", operator="in", value=["admin", "manager"])
        assert c.evaluate({"role": "admin"}) is True
        assert c.evaluate({"role": "viewer"}) is False

    def test_not_in(self):
        c = PolicyCondition(field="role", operator="not_in", value=["guest"])
        assert c.evaluate({"role": "admin"}) is True
        assert c.evaluate({"role": "guest"}) is False

    def test_nested_field(self):
        c = PolicyCondition(field="user.department", operator="eq", value="engineering")
        assert c.evaluate({"user": {"department": "engineering"}}) is True
        assert c.evaluate({"user": {"department": "sales"}}) is False
