"""Tests for Machine Auth submodule — API Keys & Agent Credentials.

Uses a SQLModelSession wrapper for raw SQLAlchemy compatibility.
"""


import pytest
from datetime import datetime, timedelta

# ===========================================================================
# API Key Tests
# ===========================================================================

class TestAPIKey:
    def test_create_api_key(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import APIKeyService
        svc = APIKeyService(sqlmodel_db)
        api_key, key = svc.create(name="Test Key", owner_user_id=1, scopes=["projects:read"])
        assert api_key.id is not None
        assert key.startswith("sk_")
        assert api_key.key_prefix == key[:12]

    def test_validate_api_key(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import APIKeyService
        svc = APIKeyService(sqlmodel_db)
        api_key, key = svc.create(name="Test Key", owner_user_id=1)
        validated = svc.validate(key)
        assert validated is not None
        assert validated.id == api_key.id

    def test_validate_invalid_key(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import APIKeyService
        svc = APIKeyService(sqlmodel_db)
        validated = svc.validate("sk_invalid_key_12345")
        assert validated is None

    def test_revoke_api_key(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import APIKeyService
        svc = APIKeyService(sqlmodel_db)
        api_key, key = svc.create(name="Test Key", owner_user_id=1)
        success = svc.revoke(api_key.id)
        assert success is True
        validated = svc.validate(key)
        assert validated is None

    def test_list_user_keys(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import APIKeyService
        svc = APIKeyService(sqlmodel_db)
        svc.create(name="Key 1", owner_user_id=1)
        svc.create(name="Key 2", owner_user_id=1)
        svc.create(name="Key 3", owner_user_id=2)
        keys = svc.list_user_keys(user_id=1)
        assert len(keys) == 2

    def test_scope_check(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import APIKeyService
        svc = APIKeyService(sqlmodel_db)
        api_key, _ = svc.create(name="Scoped Key", owner_user_id=1, scopes=["projects:read", "issues:write"])
        assert svc.has_scope(api_key, "projects:read") is True
        assert svc.has_scope(api_key, "projects:delete") is False
        api_key2, _ = svc.create(name="Wildcard Key", owner_user_id=1, scopes=["*"])
        assert svc.has_scope(api_key2, "anything") is True

# ===========================================================================
# Agent Credential Tests
# ===========================================================================

class TestAgentCredential:
    def test_create_credential(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import AgentCredentialService
        svc = AgentCredentialService(sqlmodel_db)
        cred, plain = svc.create(agent_id="agent-1", agent_name="Test Agent", owner_user_id=1)
        assert cred.agent_id == "agent-1"
        assert plain.startswith("ag_")

    def test_validate_credential(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import AgentCredentialService
        svc = AgentCredentialService(sqlmodel_db)
        cred, plain = svc.create(agent_id="agent-1", agent_name="Test Agent", owner_user_id=1)
        validated = svc.validate(plain)
        assert validated is not None
        assert validated.agent_id == "agent-1"

    def test_validate_invalid_credential(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import AgentCredentialService
        svc = AgentCredentialService(sqlmodel_db)
        validated = svc.validate("ag_invalid_credential")
        assert validated is None

    def test_action_allowed(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import AgentCredentialService
        svc = AgentCredentialService(sqlmodel_db)
        cred, _ = svc.create(agent_id="agent-1", agent_name="Agent", owner_user_id=1,
                              allowed_actions=["read", "write"])
        assert svc.can_action(cred, "read") is True
        assert svc.can_action(cred, "delete") is False

    def test_action_denied(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import AgentCredentialService
        svc = AgentCredentialService(sqlmodel_db)
        cred, _ = svc.create(agent_id="agent-1", agent_name="Agent", owner_user_id=1,
                              denied_actions=["delete"])
        assert svc.can_action(cred, "read") is True
        assert svc.can_action(cred, "delete") is False

    def test_revoke_credential(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import AgentCredentialService
        svc = AgentCredentialService(sqlmodel_db)
        cred, plain = svc.create(agent_id="agent-1", agent_name="Agent", owner_user_id=1)
        success = svc.revoke("agent-1")
        assert success is True
        validated = svc.validate(plain)
        assert validated is None

    def test_list_user_agents(self, sqlmodel_db):
        from common_lib.modules.rbac.agent_apikey_service import AgentCredentialService
        svc = AgentCredentialService(sqlmodel_db)
        svc.create(agent_id="agent-1", agent_name="A1", owner_user_id=1)
        svc.create(agent_id="agent-2", agent_name="A2", owner_user_id=1)
        svc.create(agent_id="agent-3", agent_name="A3", owner_user_id=2)
        agents = svc.list_user_agents(user_id=1)
        assert len(agents) == 2
