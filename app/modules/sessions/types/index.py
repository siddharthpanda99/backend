from pydantic import BaseModel
from datetime import datetime

class SessionResponse(BaseModel):
    id: str
    ip_address: str
    device: str
    last_active: datetime
    is_current: bool
