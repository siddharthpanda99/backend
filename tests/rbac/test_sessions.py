"""Tests for Sessions & MFA submodule — session lifecycle, MFA setup/verify.

Uses a SQLModelSession wrapper and adds created_at/updated_at to mfa_backup_codes.
"""


import pytest
from datetime import datetime, timedelta, timezone

# ===========================================================================
# Session Tests
# ===========================================================================

class TestSession:
    def test_create_session(self, sqlmodel_db):
        from common_lib.modules.rbac.session_mfa_service import SessionService
        svc = SessionService(sqlmodel_db)
        sess, token = svc.create_session(user_id=1, ip_address="127.0.0.1")
        assert sess.id is not None
        assert token is not None
        assert len(token) > 10

    def test_validate_session(self, sqlmodel_db):
        from common_lib.modules.rbac.session_mfa_service import SessionService
        svc = SessionService(sqlmodel_db)
        sess, token = svc.create_session(user_id=1)
        validated = svc.validate_session(token)
        assert validated is not None
        assert validated.user_id == 1

    def test_validate_invalid_token(self, sqlmodel_db):
        from common_lib.modules.rbac.session_mfa_service import SessionService
        svc = SessionService(sqlmodel_db)
        validated = svc.validate_session("invalid-token-abc123")
        assert validated is None

    def test_revoke_session(self, sqlmodel_db):
        from common_lib.modules.rbac.session_mfa_service import SessionService
        svc = SessionService(sqlmodel_db)
        sess, token = svc.create_session(user_id=1)
        success = svc.revoke_session(sess.id, reason="logout")
        assert success is True
        validated = svc.validate_session(token)
        assert validated is None

    def test_revoke_all_user_sessions(self, sqlmodel_db):
        from common_lib.modules.rbac.session_mfa_service import SessionService
        svc = SessionService(sqlmodel_db)
        svc.create_session(user_id=1)
        svc.create_session(user_id=1)
        count = svc.revoke_all_user_sessions(user_id=1)
        assert count == 2

    def test_list_user_sessions(self, sqlmodel_db):
        from common_lib.modules.rbac.session_mfa_service import SessionService
        svc = SessionService(sqlmodel_db)
        svc.create_session(user_id=1)
        svc.create_session(user_id=1)
        sessions = svc.list_user_sessions(user_id=1)
        assert len(sessions) == 2

# ===========================================================================
# MFA Tests
# ===========================================================================

class TestMFA:
    def test_setup_totp(self, sqlmodel_db):
        from common_lib.modules.rbac.session_mfa_service import MFAService
        svc = MFAService(sqlmodel_db)
        secret, uri = svc.setup_totp(user_id=1)
        assert secret is not None
        assert "otpauth://totp" in uri

    def test_verify_totp_enables_mfa(self, sqlmodel_db):
        """First successful verify enables MFA."""
        import pyotp
        from common_lib.modules.rbac.session_mfa_service import MFAService
        svc = MFAService(sqlmodel_db)
        secret, _ = svc.setup_totp(user_id=1)
        totp = pyotp.TOTP(secret)
        code = totp.now()
        ok = svc.verify_totp(user_id=1, code=code)
        assert ok is True
        assert svc.is_enabled(user_id=1) is True

    def test_verify_invalid_code(self, sqlmodel_db):
        from common_lib.modules.rbac.session_mfa_service import MFAService
        svc = MFAService(sqlmodel_db)
        svc.setup_totp(user_id=1)
        ok = svc.verify_totp(user_id=1, code="000000")
        assert ok is False
        assert svc.is_enabled(user_id=1) is False

    def test_disable_mfa(self, sqlmodel_db):
        import pyotp
        from common_lib.modules.rbac.session_mfa_service import MFAService
        svc = MFAService(sqlmodel_db)
        secret, _ = svc.setup_totp(user_id=1)
        totp = pyotp.TOTP(secret)
        svc.verify_totp(user_id=1, code=totp.now())
        assert svc.is_enabled(user_id=1) is True
        success = svc.disable(user_id=1)
        assert success is True
        assert svc.is_enabled(user_id=1) is False

    def test_backup_codes(self, sqlmodel_db):
        from common_lib.modules.rbac.session_mfa_service import MFAService
        svc = MFAService(sqlmodel_db)
        svc.setup_totp(user_id=1)
        codes = svc.generate_backup_codes(user_id=1)
        assert len(codes) == 10
        # Verify one code
        ok = svc.verify_backup_code(user_id=1, code=codes[0])
        assert ok is True
        # Same code can't be reused
        ok2 = svc.verify_backup_code(user_id=1, code=codes[0])
        assert ok2 is False

    def test_cannot_setup_mfa_twice(self, sqlmodel_db):
        """Can't setup TOTP if already enabled."""
        import pyotp
        from common_lib.modules.rbac.session_mfa_service import MFAService
        svc = MFAService(sqlmodel_db)
        secret, _ = svc.setup_totp(user_id=1)
        totp = pyotp.TOTP(secret)
        svc.verify_totp(user_id=1, code=totp.now())
        with pytest.raises(ValueError, match="already enabled"):
            svc.setup_totp(user_id=1)
