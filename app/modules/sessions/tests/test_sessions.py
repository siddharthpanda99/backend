# Sessions Tests
import pytest
from datetime import datetime, timedelta


class TestSessionService:
    """Tests for SessionService"""

    def test_service_has_revoke_all_sessions_method(self):
        from common_lib.modules.auth.sessions.service import session_service

        assert hasattr(session_service, "revoke_all_sessions")
        assert callable(session_service.revoke_all_sessions)

    def test_service_has_get_active_sessions_method(self):
        from common_lib.modules.auth.sessions.service import session_service

        assert hasattr(session_service, "get_active_sessions")
        assert callable(session_service.get_active_sessions)

    def test_service_has_revoke_session_method(self):
        from common_lib.modules.auth.sessions.service import session_service

        assert hasattr(session_service, "revoke_session")
        assert callable(session_service.revoke_session)

    def test_service_has_get_current_session_method(self):
        from common_lib.modules.auth.sessions.service import session_service

        assert hasattr(session_service, "get_current_session")
        assert callable(session_service.get_current_session)

    def test_revoke_all_sessions_returns_dict(self):
        from common_lib.modules.auth.sessions.service import session_service

        result = session_service.revoke_all_sessions("user-123")
        assert isinstance(result, dict)
        assert "message" in result

    def test_get_active_sessions_returns_list(self):
        from common_lib.modules.auth.sessions.service import session_service

        result = session_service.get_active_sessions("user-123")
        assert isinstance(result, list)

    def test_get_active_sessions_returns_session_responses(self):
        from common_lib.modules.auth.sessions.service import session_service
        from common_lib.modules.auth.sessions.schemas import SessionResponse

        result = session_service.get_active_sessions("user-123")
        for session in result:
            assert isinstance(session, SessionResponse)
            assert hasattr(session, "id")
            assert hasattr(session, "ip_address")
            assert hasattr(session, "device")
            assert hasattr(session, "last_active")
            assert hasattr(session, "is_current")

    def test_revoke_session_returns_dict(self):
        from common_lib.modules.auth.sessions.service import session_service

        result = session_service.revoke_session("user-123", "sess_456")
        assert isinstance(result, dict)
        assert "message" in result

    def test_get_current_session_returns_response(self):
        from common_lib.modules.auth.sessions.service import session_service
        from common_lib.modules.auth.sessions.schemas import SessionResponse

        result = session_service.get_current_session("token-123")
        assert isinstance(result, SessionResponse)
        assert result.is_current == True


class TestSessionSchemas:
    """Tests for Session schemas"""

    def test_session_response_schema_imports(self):
        from common_lib.modules.auth.sessions.schemas import SessionResponse

        assert SessionResponse is not None

    def test_session_response_has_required_fields(self):
        from common_lib.modules.auth.sessions.schemas import SessionResponse

        session = SessionResponse(
            id="test-id",
            ip_address="127.0.0.1",
            device="Test Browser",
            last_active=datetime.utcnow(),
            is_current=True,
        )
        assert session.id == "test-id"
        assert session.ip_address == "127.0.0.1"
        assert session.device == "Test Browser"
        assert session.is_current == True


class TestSessionServiceBehavior:
    """Tests for session service behavior"""

    def test_active_sessions_includes_current(self):
        from common_lib.modules.auth.sessions.service import session_service

        result = session_service.get_active_sessions("user-123")
        current_sessions = [s for s in result if s.is_current]
        assert len(current_sessions) >= 1

    def test_active_sessions_have_unique_ids(self):
        from common_lib.modules.auth.sessions.service import session_service

        result = session_service.get_active_sessions("user-123")
        ids = [s.id for s in result]
        assert len(ids) == len(set(ids))
