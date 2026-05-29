from sqlmodel import Session, select, text
from common_lib.modules.data_storage.database.connection import get_engine

engine = get_engine()
with Session(engine) as session:
    row = session.execute(text("SELECT id, name, prompt_template, resolved_prompt, instructions_text FROM agent_definitions WHERE id = 'assistant'")).first()
    if row:
        print("id:", row[0])
        print("name:", row[1])
        print("prompt_template:", repr(row[2]))
        print("resolved_prompt:", repr(row[3]))
        print("instructions_text:", repr(row[4]))
    else:
        print("Agent 'assistant' not found in database!")
