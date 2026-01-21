from datetime import datetime, timedelta
from app.modules.sessions.types.index import SessionResponse

class SessionService:
    def revoke_all_sessions(self, user_id: str) -> dict:
        return {"message": "All sessions revoked"}
    
    def get_active_sessions(self, user_id: str) -> list[SessionResponse]:
        # Mock sessions
        return [
            SessionResponse(
                id="sess_123", 
                ip_address="192.168.1.1", 
                device="Chrome / Windows", 
                last_active=datetime.utcnow(), 
                is_current=True
            ),
            SessionResponse(
                id="sess_456", 
                ip_address="10.0.0.1", 
                device="Safari / iPhone", 
                last_active=datetime.utcnow() - timedelta(days=1), 
                is_current=False
            )
        ]

    def revoke_session(self, user_id: str, session_id: str) -> dict:
        return {"message": f"Session {session_id} revoked"}
    
    def get_current_session(self, token: str) -> SessionResponse:
        return SessionResponse(
            id="sess_123", 
            ip_address="192.168.1.1", 
            device="Chrome / Windows", 
            last_active=datetime.utcnow(), 
            is_current=True
        )

session_service = SessionService()
