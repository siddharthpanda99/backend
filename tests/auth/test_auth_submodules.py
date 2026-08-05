"""Comprehensive tests for all auth submodules (MFA, Sessions, User Lifecycle, Domain Verification, SSO).

Tests use SQLite in-memory database with only auth submodule tables created.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, create_engine, SQLModel


_AUTH_MODELS = []


def _collect_auth_models():
    """Collect all auth submodule models and register them with SQLModel.metadata."""
    global _AUTH_MODELS
    if not _AUTH_MODELS:
        from common_lib.modules.auth.mfa.models import UserMFASecret, MFABackupCode, MFAVerification, TrustedDevice, MFAChallenge
        from common_lib.modules.auth.sessions.models import UserSession, SessionEvent
        from common_lib.modules.auth.user_lifecycle.models import UserProfile, UserDeactivation, UserActivity
        from common_lib.modules.auth.domain_verification.models import DomainClaim, DomainVerificationAttempt
        from common_lib.modules.auth.sso.models import OAuthProvider, OAuthAccountLink, SSOProvider, SSOConfiguration
        _AUTH_MODELS = [
            UserMFASecret, MFABackupCode, MFAVerification, TrustedDevice, MFAChallenge,
            UserSession, SessionEvent,
            UserProfile, UserDeactivation, UserActivity,
            DomainClaim, DomainVerificationAttempt,
            OAuthProvider, OAuthAccountLink, SSOProvider, SSOConfiguration,
        ]
    return _AUTH_MODELS


@pytest.fixture
def session():
    """Create an in-memory SQLite session with only auth submodule tables."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models = _collect_auth_models()
    tables = [m.__table__ for m in models if hasattr(m, '__table__')]
    SQLModel.metadata.create_all(engine, tables=tables)
    with Session(engine) as s:
        yield s


# ===========================================================================
# MFA Submodule
# ===========================================================================

class TestMFASubmodule:
    """Test mfa/ — TOTP setup, verify, backup codes, trusted devices."""

    def test_setup_totp(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        result = svc.setup_totp("user-1", "user@example.com")
        assert result["is_verified"] is False
        assert "secret" in result
        assert "otpauth_url" in result
        assert "otpauth://totp/" in result["otpauth_url"]

    def test_verify_totp_wrong_code(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        svc.setup_totp("user-1", "user@example.com")
        verified = svc.verify_totp("user-1", "000000")
        assert verified is False

    def test_get_mfa_status_not_setup(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        status = svc.get_mfa_status("user-nonexistent")
        assert status["has_mfa"] is False
        assert status["methods"] == []

    def test_get_mfa_status_setup(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        svc.setup_totp("user-2", "user2@example.com")
        status = svc.get_mfa_status("user-2")
        assert status["has_mfa"] is True
        assert "totp" in status["methods"]

    def test_generate_backup_codes(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        codes = svc.generate_backup_codes("user-1", count=5)
        assert len(codes) == 5
        for c in codes:
            assert "code" in c

    def test_verify_backup_code_valid(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        codes = svc.generate_backup_codes("user-1", count=3)
        assert svc.verify_backup_code("user-1", codes[0]["code"]) is True

    def test_verify_backup_code_invalid(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        assert svc.verify_backup_code("user-1", "INVALID-CODE") is False

    def test_verify_backup_code_twice_fails(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        codes = svc.generate_backup_codes("user-1", count=1)
        assert svc.verify_backup_code("user-1", codes[0]["code"]) is True
        assert svc.verify_backup_code("user-1", codes[0]["code"]) is False

    def test_backup_codes_remaining(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        svc.generate_backup_codes("user-1", count=5)
        assert svc.get_backup_codes_remaining("user-1") == 5

    def test_trust_device(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        result = svc.trust_device("user-1", "fp-abc123", device_name="My Phone", duration_days=30)
        assert "id" in result
        assert "expires_at" in result

    def test_is_device_trusted(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        svc.trust_device("user-1", "fp-abc123", duration_days=30)
        assert svc.is_device_trusted("user-1", "fp-abc123") is True
        assert svc.is_device_trusted("user-1", "fp-unknown") is False

    def test_list_trusted_devices(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        svc.trust_device("user-1", "fp-1", device_name="Device 1")
        svc.trust_device("user-1", "fp-2", device_name="Device 2")
        devices = svc.list_trusted_devices("user-1")
        assert len(devices) == 2

    def test_remove_trusted_device(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        result = svc.trust_device("user-1", "fp-abc")
        assert svc.remove_trusted_device(result["id"]) is True
        assert svc.remove_trusted_device("nonexistent") is False

    def test_remove_mfa(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        svc.setup_totp("user-1", "user@example.com")
        svc.remove_mfa("user-1")
        status = svc.get_mfa_status("user-1")
        assert status["has_mfa"] is False

    def test_create_challenge(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        challenge = svc.create_challenge("user-1", ttl_seconds=300)
        assert "challenge_id" in challenge
        assert challenge["mfa_type"] == "totp"

    def test_verify_challenge_valid(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        challenge = svc.create_challenge("user-1")
        assert svc.verify_challenge(challenge["challenge_id"], "user-1") is True

    def test_verify_challenge_invalid_user(self, session):
        from common_lib.modules.auth.mfa.service import MFAService
        svc = MFAService(session)
        challenge = svc.create_challenge("user-1")
        assert svc.verify_challenge(challenge["challenge_id"], "user-2") is False


# ===========================================================================
# Sessions Submodule
# ===========================================================================

class TestSessionsSubmodule:
    """Test sessions/ — session creation, listing, revocation, cleanup."""

    def test_create_session(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        result = svc.create_session("user-1", ip_address="127.0.0.1", user_agent="test-agent")
        assert result["is_active"] is True
        assert "session_token" in result
        assert "expires_at" in result

    def test_get_session_by_token(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        created = svc.create_session("user-1")
        found = svc.get_session_by_token(created["session_token"])
        assert found is not None
        assert found["user_id"] == "user-1"

    def test_get_session_invalid_token(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        assert svc.get_session_by_token("invalid-token") is None

    def test_list_active_sessions(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        svc.create_session("user-1")
        svc.create_session("user-1")
        sessions = svc.list_active_sessions("user-1")
        assert len(sessions) == 2

    def test_list_active_sessions_empty(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        assert svc.list_active_sessions("user-nonexistent") == []

    def test_revoke_session(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        svc.create_session("user-1", ip_address="127.0.0.1")
        active = svc.list_active_sessions("user-1")
        assert len(active) == 1
        assert svc.revoke_session(active[0]["id"], reason="logged out") is True
        assert len(svc.list_active_sessions("user-1")) == 0

    def test_revoke_session_nonexistent(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        assert svc.revoke_session("nonexistent") is False  # Not found

    def test_revoke_all_user_sessions(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        svc.create_session("user-1")
        svc.create_session("user-1")
        count = svc.revoke_all_user_sessions("user-1", reason="security_breach")
        assert count == 2
        assert len(svc.list_active_sessions("user-1")) == 0

    def test_revoke_all_with_exclusion(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        s1 = svc.create_session("user-1")
        svc.create_session("user-1")
        count = svc.revoke_all_user_sessions("user-1", exclude_session_id=s1["id"])
        assert count == 1

    def test_update_session_activity(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        result = svc.create_session("user-1")
        assert svc.update_session_activity(result["id"]) is True
        assert svc.update_session_activity("nonexistent") is False

    def test_mark_session_mfa_verified(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        result = svc.create_session("user-1")
        assert svc.mark_session_mfa_verified(result["id"]) is True
        assert svc.mark_session_mfa_verified("nonexistent") is False

    def test_cleanup_expired_sessions(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        svc.create_session("user-1")
        # No expired sessions to cleanup (just created)
        count = svc.cleanup_expired_sessions()
        assert count == 0

    def test_list_sessions_include_revoked(self, session):
        from common_lib.modules.auth.sessions.service import SessionManagementService
        svc = SessionManagementService(session)
        svc.create_session("user-1")
        svc.create_session("user-1")
        active = svc.list_active_sessions("user-1")
        svc.revoke_session(active[0]["id"])
        all_sessions = svc.list_sessions("user-1", include_revoked=True)
        assert len(all_sessions) == 2
        active_only = svc.list_sessions("user-1", include_revoked=False)
        assert len(active_only) == 1


# ===========================================================================
# User Lifecycle Submodule
# ===========================================================================

class TestUserLifecycleSubmodule:
    """Test user_lifecycle/ — profile CRUD, deactivation, activity log."""

    def test_get_profile_not_found(self, session):
        from common_lib.modules.auth.user_lifecycle.service import UserLifecycleService
        svc = UserLifecycleService(session)
        assert svc.get_profile("user-nonexistent") is None

    def test_upsert_profile_creates(self, session):
        from common_lib.modules.auth.user_lifecycle.service import UserLifecycleService
        svc = UserLifecycleService(session)
        result = svc.upsert_profile("user-1", display_name="Alice", locale="en", timezone="UTC")
        assert result["user_id"] == "user-1"
        assert result["display_name"] == "Alice"

    def test_upsert_profile_updates(self, session):
        from common_lib.modules.auth.user_lifecycle.service import UserLifecycleService
        svc = UserLifecycleService(session)
        svc.upsert_profile("user-1", display_name="Alice")
        result = svc.upsert_profile("user-1", display_name="Alice Updated", job_title="Engineer")
        assert result["display_name"] == "Alice Updated"
        assert result["job_title"] == "Engineer"

    def test_update_profile(self, session):
        from common_lib.modules.auth.user_lifecycle.service import UserLifecycleService
        svc = UserLifecycleService(session)
        svc.upsert_profile("user-1", display_name="Bob")
        result = svc.update_profile("user-1", {"locale": "fr", "timezone": "Europe/Paris"})
        assert result is not None
        assert result["locale"] == "fr"
        assert result["timezone"] == "Europe/Paris"

    def test_log_activity(self, session):
        from common_lib.modules.auth.user_lifecycle.service import UserLifecycleService
        svc = UserLifecycleService(session)
        result = svc.log_activity("user-1", "login", ip_address="127.0.0.1")
        assert result["activity_type"] == "login"
        assert "id" in result

    def test_get_activity_log(self, session):
        from common_lib.modules.auth.user_lifecycle.service import UserLifecycleService
        svc = UserLifecycleService(session)
        svc.log_activity("user-1", "login", details="Logged in")
        svc.log_activity("user-1", "logout", details="Logged out")
        activities = svc.get_activity_log("user-1")
        assert len(activities) == 2

    def test_deactivation_record(self, session):
        """Test that deactivation records can be created (without User integration dependency)."""
        from common_lib.modules.auth.user_lifecycle.models import UserDeactivation
        from datetime import datetime
        record = UserDeactivation(
            user_id="user-1",
            action="deactivated",
            reason="User request",
            deactivated_by="admin",
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        assert record.action == "deactivated"
        assert record.user_id == "user-1"
        assert record.reason == "User request"


# ===========================================================================
# Domain Verification Submodule
# ===========================================================================

class TestDomainVerificationSubmodule:
    """Test domain_verification/ — domain claiming, DNS verification."""

    def test_claim_domain(self, session):
        from common_lib.modules.auth.domain_verification.service import DomainVerificationService
        svc = DomainVerificationService(session)
        result = svc.claim_domain("org-1", "example.com")
        assert result["domain"] == "example.com"
        assert result["status"] == "pending"
        assert "verification_token" in result
        assert "dns_record_name" in result

    def test_claim_domain_again_same_org(self, session):
        from common_lib.modules.auth.domain_verification.service import DomainVerificationService
        svc = DomainVerificationService(session)
        first = svc.claim_domain("org-1", "example.com")
        second = svc.claim_domain("org-1", "example.com")
        assert second["id"] == first["id"]
        assert second["status"] == first["status"]

    def test_list_org_domains(self, session):
        from common_lib.modules.auth.domain_verification.service import DomainVerificationService
        svc = DomainVerificationService(session)
        svc.claim_domain("org-1", "example.com")
        svc.claim_domain("org-1", "test.org")
        domains = svc.list_org_domains("org-1")
        assert len(domains) == 2

    def test_list_org_domains_empty(self, session):
        from common_lib.modules.auth.domain_verification.service import DomainVerificationService
        svc = DomainVerificationService(session)
        assert svc.list_org_domains("org-empty") == []

    def test_get_domain_status_not_found(self, session):
        from common_lib.modules.auth.domain_verification.service import DomainVerificationService
        svc = DomainVerificationService(session)
        assert svc.get_domain_status("nonexistent.com") is None

    def test_get_domain_status_found(self, session):
        from common_lib.modules.auth.domain_verification.service import DomainVerificationService
        svc = DomainVerificationService(session)
        svc.claim_domain("org-1", "example.com")
        status = svc.get_domain_status("example.com")
        assert status is not None
        assert status["status"] == "pending"

    def test_remove_domain(self, session):
        from common_lib.modules.auth.domain_verification.service import DomainVerificationService
        svc = DomainVerificationService(session)
        result = svc.claim_domain("org-1", "example.com")
        assert svc.remove_domain(result["id"]) is True
        assert svc.remove_domain("nonexistent") is False

    def test_verify_all_pending(self, session):
        from common_lib.modules.auth.domain_verification.service import DomainVerificationService
        svc = DomainVerificationService(session)
        svc.claim_domain("org-1", "example.com")
        results = svc.verify_all_pending("org-1")
        # DNS verification will fail in test (no real DNS)
        assert len(results) == 1
        assert results[0]["verified"] is False


# ===========================================================================
# SSO Submodule
# ===========================================================================

class TestSSOSubmodule:
    """Test sso/ — OAuth provider linking, account linking, SSO config."""

    def test_register_provider(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        result = svc.register_provider(
            "google", "Google",
            "https://accounts.google.com/o/oauth2/auth",
            "https://oauth2.googleapis.com/token",
            "https://openidconnect.googleapis.com/v1/userinfo",
            scopes=["openid", "email", "profile"],
        )
        assert result["name"] == "google"
        assert result["display_name"] == "Google"

    def test_register_provider_duplicate(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        svc.register_provider("google", "Google", "https://auth.url", "https://token.url", "https://userinfo.url")
        import pytest as _pytest
        with _pytest.raises(ValueError, match="already registered"):
            svc.register_provider("google", "Google", "https://auth.url", "https://token.url", "https://userinfo.url")

    def test_list_providers(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        svc.register_provider("google", "Google", "url", "url", "url")
        svc.register_provider("github", "GitHub", "url", "url", "url")
        providers = svc.list_providers()
        assert len(providers) >= 2
        names = [p["name"] for p in providers]
        assert "google" in names
        assert "github" in names

    def test_link_oauth_account(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        result = svc.link_oauth_account("user-1", "google", "google-123", provider_email="user@gmail.com")
        assert result["provider"] == "google"
        assert result["already_linked"] is False

    def test_link_oauth_account_duplicate(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        svc.link_oauth_account("user-1", "google", "google-123")
        result = svc.link_oauth_account("user-1", "google", "google-123")
        assert result["already_linked"] is True

    def test_list_user_oauth_links(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        svc.link_oauth_account("user-1", "google", "g-1")
        svc.link_oauth_account("user-1", "github", "gh-1")
        links = svc.list_user_oauth_links("user-1")
        assert len(links) == 2

    def test_list_user_oauth_links_empty(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        assert svc.list_user_oauth_links("user-empty") == []

    def test_unlink_oauth_account(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        result = svc.link_oauth_account("user-1", "google", "g-1")
        assert svc.unlink_oauth_account(result["id"]) is True
        assert svc.unlink_oauth_account("nonexistent") is False

    def test_get_user_by_oauth(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        svc.link_oauth_account("user-1", "google", "google-123")
        found = svc.get_user_by_oauth("google", "google-123")
        assert found is not None
        assert found["user_id"] == "user-1"

    def test_get_user_by_oauth_not_found(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        assert svc.get_user_by_oauth("google", "unknown-id") is None

    def test_configure_sso(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        result = svc.configure_sso("org-1", sso_only=False, allow_password_login=True)
        assert result["org_id"] == "org-1"
        assert result["sso_only"] is False

    def test_get_sso_config_not_found(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        assert svc.get_sso_config("org-nonexistent") is None

    def test_get_sso_config_found(self, session):
        from common_lib.modules.auth.sso.service import SSOService
        svc = SSOService(session)
        svc.configure_sso("org-1", sso_only=True)
        config = svc.get_sso_config("org-1")
        assert config is not None
        assert config["sso_only"] is True
