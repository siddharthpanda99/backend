"""Tests for RBAC Integrations Submodule (SSOT 22, 25).

Verifies SCIMService, SSOService, DirectorySyncService, APIAuthService.
"""

import pytest
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import Session as RawSession

class TestSCIMService:
    """Test SCIM provisioning service."""

    def test_register_provider(self, db):
        from common_lib.modules.rbac.integrations.service import SCIMService, SCIMConfig
        svc = SCIMService(db)
        config = SCIMConfig(provider="azure_ad", base_url="https://scim.example.com", api_token="tok_123")
        pid = svc.register_provider(config)
        assert pid is not None
        assert len(pid) > 0

    def test_provision_user(self, db):
        from common_lib.modules.rbac.integrations.service import SCIMService, SCIMConfig
        svc = SCIMService(db)
        config = SCIMConfig(provider="okta", base_url="https://okta.example.com", api_token="tok_456")
        pid = svc.register_provider(config)
        result = svc.provision_user(pid, {"userName": "john.doe", "emails": [{"value": "john@example.com"}], "active": True})
        assert result["username"] == "john.doe"
        assert result["email"] == "john@example.com"

    def test_deprovision_user(self, db):
        from common_lib.modules.rbac.integrations.service import SCIMService, SCIMConfig
        svc = SCIMService(db)
        config = SCIMConfig(provider="okta", base_url="https://okta.example.com", api_token="tok_789")
        pid = svc.register_provider(config)
        result = svc.deprovision_user(pid, "john.doe")
        assert result["action"] == "deprovisioned"

    def test_sync_groups(self, db):
        from common_lib.modules.rbac.integrations.service import SCIMService, SCIMConfig
        svc = SCIMService(db)
        config = SCIMConfig(provider="azure_ad", base_url="https://scim.example.com", api_token="tok_abc")
        pid = svc.register_provider(config)
        groups = [{"name": "Engineering", "members": ["user1", "user2"]}]
        result = svc.sync_groups(pid, groups)
        assert result["groups_synced"] == 1

    def test_provision_unknown_provider(self, db):
        from common_lib.modules.rbac.integrations.service import SCIMService
        svc = SCIMService(db)
        result = svc.provision_user("nonexistent", {"userName": "test"})
        assert "error" in result

class TestSSOService:
    """Test SSO configuration service."""

    def test_configure_saml(self):
        from common_lib.modules.rbac.integrations.service import SSOService, SSOConfig
        svc = SSOService()
        config = SSOConfig(provider="saml", issuer_url="https://saml.example.com", client_id="cid", client_secret="secret")
        pid = svc.configure_saml(config)
        assert pid is not None
        provider = svc.get_provider(pid)
        assert provider.provider == "saml"

    def test_configure_oidc(self):
        from common_lib.modules.rbac.integrations.service import SSOService, SSOConfig
        svc = SSOService()
        config = SSOConfig(provider="oidc", issuer_url="https://oidc.example.com", client_id="cid", client_secret="secret")
        pid = svc.configure_oidc(config)
        assert pid is not None
        provider = svc.get_provider(pid)
        assert provider.provider == "oidc"

    def test_list_providers(self):
        from common_lib.modules.rbac.integrations.service import SSOService, SSOConfig
        svc = SSOService()
        svc.configure_saml(SSOConfig(provider="saml", issuer_url="https://saml.example.com", client_id="cid", client_secret="secret"))
        svc.configure_oidc(SSOConfig(provider="oidc", issuer_url="https://oidc.example.com", client_id="cid", client_secret="secret"))
        providers = svc.list_providers()
        assert len(providers) == 2

    def test_enable_disable_provider(self):
        from common_lib.modules.rbac.integrations.service import SSOService, SSOConfig
        svc = SSOService()
        config = SSOConfig(provider="saml", issuer_url="https://saml.example.com", client_id="cid", client_secret="secret")
        pid = svc.configure_saml(config)
        assert svc.disable_provider(pid) is True
        assert svc.enable_provider(pid) is True

class TestDirectorySyncService:
    """Test directory sync service."""

    def test_configure_directory(self):
        from common_lib.modules.rbac.integrations.service import DirectorySyncService, DirectoryConfig
        svc = DirectorySyncService()
        config = DirectoryConfig(provider="ldap", server_url="ldap://localhost", base_dn="dc=example,dc=com", bind_dn="cn=admin", bind_password="pass")
        did = svc.configure_directory(config)
        assert did is not None

    def test_trigger_sync(self):
        from common_lib.modules.rbac.integrations.service import DirectorySyncService, DirectoryConfig
        svc = DirectorySyncService()
        config = DirectoryConfig(provider="ad", server_url="ldap://ad.example.com", base_dn="dc=example,dc=com", bind_dn="cn=admin", bind_password="pass")
        did = svc.configure_directory(config)
        result = svc.trigger_sync(did)
        assert "sync_completed" in result

    def test_list_configs(self):
        from common_lib.modules.rbac.integrations.service import DirectorySyncService, DirectoryConfig
        svc = DirectorySyncService()
        config = DirectoryConfig(provider="ldap", server_url="ldap://localhost", base_dn="dc=example,dc=com", bind_dn="cn=admin", bind_password="pass")
        svc.configure_directory(config)
        configs = svc.list_configs()
        assert len(configs) == 1

class TestAPIAuthService:
    """Test API authentication service."""

    def test_validate_token_valid(self):
        from common_lib.modules.rbac.integrations.service import APIAuthService
        svc = APIAuthService()
        svc.register_token("tok_valid", {"user_id": 1, "scopes": ["project:read"]})
        result = svc.validate_api_token("tok_valid")
        assert result is not None
        assert result["user_id"] == 1

    def test_validate_token_invalid(self):
        from common_lib.modules.rbac.integrations.service import APIAuthService
        svc = APIAuthService()
        result = svc.validate_api_token("tok_nonexistent")
        assert result is None

    def test_revoke_token(self):
        from common_lib.modules.rbac.integrations.service import APIAuthService
        svc = APIAuthService()
        svc.register_token("tok_revoke", {"user_id": 2})
        assert svc.revoke_token("tok_revoke") is True
        assert svc.validate_api_token("tok_revoke") is None

    def test_check_graphql_action(self):
        from common_lib.modules.rbac.integrations.service import APIAuthService
        svc = APIAuthService()
        assert svc.check_graphql_action("project:read", {"user_id": 1}) is True
        assert svc.check_graphql_action("project:write", {}) is False
