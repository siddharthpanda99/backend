"""
Tests for Secrets Manager Rotation submodule (SSOT 04).

Tests rotation policy management, execution, and record tracking.
"""
from __future__ import annotations

import pytest
from common_lib.modules.secrets_manager.rotation.service import RotationService
from common_lib.modules.secrets_manager.vault.service import VaultService


class TestRotationService:
    """Test rotation orchestration."""

    def test_create_rotation_policy(self, db):
        svc = RotationService(session=db)
        result = svc.create_policy(
            name="monthly-rotate",
            interval_days=30,
            secret_name="test-secret",
        )
        assert result["name"] == "monthly-rotate"
        assert "next_rotation_at" in result

    def test_list_policies(self, db):
        svc = RotationService(session=db)
        svc.create_policy(name="pol-1", interval_days=30)
        svc.create_policy(name="pol-2", interval_days=90)
        policies = svc.list_policies()
        assert len(policies) >= 2
        names = [p["name"] for p in policies]
        assert "pol-1" in names
        assert "pol-2" in names

    def test_execute_rotation_success(self, db):
        """Test that rotation creates a new version via vault service."""
        # First create a secret
        vault = VaultService(session=db)
        vault.create_secret(name="rotate-secret", value="original-value")

        # Set up rotation policy with secret_name
        rot = RotationService(session=db)
        policy = rot.create_policy(
            name="rotate-exec",
            interval_days=30,
            secret_name="rotate-secret",
        )

        result = rot.execute_rotation(policy_id=policy["id"])
        assert result["status"] == "success"
        assert result["new_version"] == 2

    def test_execute_rotation_policy_not_found(self, db):
        rot = RotationService(session=db)
        result = rot.execute_rotation(policy_id="nonexistent-id")
        assert "error" in result
        assert "not found" in result["error"]

    def test_execute_rotation_no_secret_name(self, db):
        """Test rotation fails when policy has no secret_name."""
        rot = RotationService(session=db)
        policy = rot.create_policy(name="no-secret", interval_days=30)
        result = rot.execute_rotation(policy_id=policy["id"])
        assert result["status"] == "failed"
        assert "No secret_name" in result["error"]

    def test_list_records(self, db):
        """Test listing rotation execution records."""
        vault = VaultService(session=db)
        vault.create_secret(name="record-secret", value="v1")

        rot = RotationService(session=db)
        policy = rot.create_policy(name="record-pol", interval_days=30, secret_name="record-secret")
        rot.execute_rotation(policy_id=policy["id"])

        records = rot.list_records(policy_id=policy["id"])
        assert len(records) >= 1
        assert records[0]["status"] == "success"
