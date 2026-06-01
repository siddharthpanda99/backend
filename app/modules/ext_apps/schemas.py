from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class ExtAppViewBase(BaseModel):
    name: str
    component_url: str
    csp_config: Optional[Dict[str, Any]] = None
    default_display_mode: Optional[str] = "inline"
    description: Optional[str] = None
    is_active: Optional[bool] = True

class ExtAppViewCreate(ExtAppViewBase):
    pass

class ExtAppViewUpdate(BaseModel):
    name: Optional[str] = None
    component_url: Optional[str] = None
    csp_config: Optional[Dict[str, Any]] = None
    default_display_mode: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class ExtAppViewResponse(ExtAppViewBase):
    id: str

    class Config:
        from_attributes = True

class ExtAppSessionBase(BaseModel):
    view_id: str
    user_id: str
    session_state: Optional[Dict[str, Any]] = {}
    context_llm: Optional[Dict[str, Any]] = {}

class ExtAppSessionCreate(ExtAppSessionBase):
    pass

class ExtAppSessionResponse(ExtAppSessionBase):
    id: str

    class Config:
        from_attributes = True
