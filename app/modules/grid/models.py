from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, JSON, Column
from datetime import datetime

class GridConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    config_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    schema_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    metadata_json: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))
    is_favorite: bool = Field(default=False)
    user_comments: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
