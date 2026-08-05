"""
Tests for Secrets Manager Dynamic submodule (SSOT 03).

Tests dynamic secret CRUD, lease issuance/renewal/revocation, TTL enforcement.
"""
from __future__ import annotations

import pytest
from common_lib.modules.secrets_manager.dynamic.service import DynamicSecretsService


class TestDynamicSecrets:
    """Test dynamic secret management and lease lifecycle."""

    def test_create_dynamic_secret(self, db):
        svc = DynamicSecretsService(session=db)
        result = svc.create_dynamic_secret(
            name="db-prod",
            secret_type="database",
            provider="postgres",
            config={"host": "pg.example.com", "port": 5432},
            default_ttl_seconds=3600,
        )
        assert result["name"] == "db-prod"
        assert "id" in result

    def test_list_dynamic_secrets(self, db):
        svc = DynamicSecretsService(session=db)
        svc.create_dynamic_secret(name="ds-1", secret_type="database", provider="postgres")
        svc.create_dynamic_secret(name="ds-2", secret_type="aws", provider="iam")
        secrets = svc.list_dynamic_secrets()
        assert len(secrets) >= 2
        names = [s["name"] for s in secrets]
        assert "ds-1" in names
        assert "ds-2" in names

    def test_issue_lease(self, db):
        svc = DynamicSecretsService(session=db)
        svc.create_dynamic_secret(name="lease-source", secret_type="database", provider="postgres")
        result = svc.issue_lease(dynamic_secret_name="lease-source", requested_by="test-user")
        assert "lease_id" in result
        assert "credential" in result
        assert result["ttl_seconds"] == 3600

    def test_issue_lease_not_found(self, db):
        svc = DynamicSecretsService(session=db)
        result = svc.issue_lease(dynamic_secret_name="nonexistent")
        assert "error" in result
        assert "not found" in result["error"]

    def test_issue_lease_custom_ttl(self, db):
        svc = DynamicSecretsService(session=db)
        svc.create_dynamic_secret(
            name="custom-ttl", secret_type="database", provider="postgres",
            default_ttl_seconds=3600, max_ttl_seconds=7200,
        )
        result = svc.issue_lease(dynamic_secret_name="custom-ttl", ttl_seconds=1800)
        assert result["ttl_seconds"] == 1800

    def test_issue_lease_ttl_capped_at_max(self, db):
        svc = DynamicSecretsService(session=db)
        svc.create_dynamic_secret(
            name="capped-ttl", secret_type="database", provider="postgres",
            default_ttl_seconds=3600, max_ttl_seconds=7200,
        )
        result = svc.issue_lease(dynamic_secret_name="capped-ttl", ttl_seconds=86400)
        assert result["ttl_seconds"] == 7200  # Capped at max_ttl

    def test_renew_lease(self, db):
        svc = DynamicSecretsService(session=db)
        svc.create_dynamic_secret(name="renew-source", secret_type="database", provider="postgres")
        issued = svc.issue_lease(dynamic_secret_name="renew-source")
        lease_id = issued["lease_id"]

        renewed = svc.renew_lease(lease_id=lease_id)
        assert renewed["lease_id"] == lease_id
        assert renewed["renew_count"] == 1

    def test_renew_lease_not_found(self, db):
        svc = DynamicSecretsService(session=db)
        result = svc.renew_lease(lease_id="nonexistent-id")
        assert "error" in result
        assert "not found" in result["error"]

    def test_revoke_lease(self, db):
        svc = DynamicSecretsService(session=db)
        svc.create_dynamic_secret(name="revoke-source", secret_type="database", provider="postgres")
        issued = svc.issue_lease(dynamic_secret_name="revoke-source")

        assert svc.revoke_lease(lease_id=issued["lease_id"], reason="testing") is True

    def test_revoke_lease_not_found(self, db):
        svc = DynamicSecretsService(session=db)
        assert svc.revoke_lease(lease_id="nonexistent") is False

    def test_list_active_leases(self, db):
        svc = DynamicSecretsService(session=db)
        svc.create_dynamic_secret(name="list-active", secret_type="database", provider="postgres")
        svc.issue_lease(dynamic_secret_name="list-active")
        svc.issue_lease(dynamic_secret_name="list-active")
        leases = svc.list_active_leases(dynamic_secret_name="list-active")
        assert len(leases) >= 2

    def test_cleanup_expired_leases(self, db):
        svc = DynamicSecretsService(session=db)
        svc.create_dynamic_secret(
            name="cleanup-source", secret_type="database", provider="postgres",
            default_ttl_seconds=1,  # 1-second TTL
        )
        svc.issue_lease(dynamic_secret_name="cleanup-source", ttl_seconds=1)
        import time
        time.sleep(1.1)

        count = svc.cleanup_expired_leases()
        assert count >= 1
