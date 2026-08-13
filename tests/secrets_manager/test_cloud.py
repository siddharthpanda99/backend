"""
Tests for Secrets Manager Cloud submodule (SSOT 11).

Tests cloud provider management, external vault sync, replication configs.
"""

from __future__ import annotations

from common_lib.modules.secrets_manager.cloud.service import CloudFederationService


class TestCloudFederationService:
    """Test cloud provider, external vault, and replication management."""

    def test_create_provider(self, db):
        svc = CloudFederationService(session=db)
        result = svc.create_provider(
            name="aws-prod", provider_type="aws", region="us-west-2"
        )
        assert result["name"] == "aws-prod"
        assert result["provider_type"] == "aws"

    def test_list_providers(self, db):
        svc = CloudFederationService(session=db)
        svc.create_provider(name="aws-1", provider_type="aws")
        svc.create_provider(name="gcp-1", provider_type="gcp")
        providers = svc.list_providers()
        assert len(providers) >= 2

    def test_register_vault(self, db):
        svc = CloudFederationService(session=db)
        result = svc.register_vault(
            name="hashicorp-prod",
            vault_type="hashicorp",
            endpoint_url="https://vault.example.com",
        )
        assert result["name"] == "hashicorp-prod"
        assert result["vault_type"] == "hashicorp"

    def test_list_external_vaults(self, db):
        svc = CloudFederationService(session=db)
        svc.register_vault(name="vault-1", vault_type="hashicorp")
        svc.register_vault(name="vault-2", vault_type="aws_sm")
        vaults = svc.list_external_vaults()
        assert len(vaults) >= 2

    def test_create_replication(self, db):
        svc = CloudFederationService(session=db)
        result = svc.create_replication(
            name="us-to-eu", target_cluster="eu-cluster", replication_mode="async"
        )
        assert result["name"] == "us-to-eu"
        assert result["replication_mode"] == "async"

    def test_list_replications(self, db):
        svc = CloudFederationService(session=db)
        svc.create_replication(name="rep-1", target_cluster="cluster-a")
        svc.create_replication(name="rep-2", target_cluster="cluster-b")
        reps = svc.list_replications()
        assert len(reps) >= 2
