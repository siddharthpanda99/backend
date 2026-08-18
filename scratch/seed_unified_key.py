import json
import secrets
from datetime import datetime
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_engine
from common_lib.modules.secrets_manager.keys_management.models import Settings

engine = get_engine()

# Config details for AIO Key
key_id = "sk-un-aio-" + secrets.token_hex(16)
unified_key_data = {
    "id": key_id,
    "name": "AIO",
    "providers": ["gemini", "groq", "openrouter", "openai", "anthropic"],
    "models": [
        "gemini-2.5-flash", 
        "gemini-3.1-pro", 
        "gpt-4o", 
        "gpt-4o-mini", 
        "claude-3-5-sonnet", 
        "deepseek-r1", 
        "llama-3.3-70b", 
        "qwen-2.5-coder"
    ],
    "rpm": 120,
    "tpd": 200000,
    "guardrails": True,
    "created_at": datetime.utcnow().isoformat(),
    "status": "healthy"
}

with Session(engine) as session:
    # Delete any existing unified key starting with sk-un-aio- to clean up first
    existing = session.exec(
        select(Settings).where(Settings.key_name.like("unified_key:sk-un-aio-%"))
    ).all()
    for row in existing:
        session.delete(row)
        
    setting_row = Settings(
        key_name=f"unified_key:{key_id}",
        value=json.dumps(unified_key_data)
    )
    session.add(setting_row)
    session.commit()
    print(f"Successfully seeded AIO Unified Key: '{key_id}'")
