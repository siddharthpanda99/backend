from app.core.common_lib_integration import common_memory
from sqlalchemy import text

with common_memory.engine.connect() as conn:
    print('Tools:', conn.execute(text('SELECT count(*) FROM tool_definitions')).scalar())
    print('Agents:', conn.execute(text('SELECT count(*) FROM agent_definitions')).scalar())
    print('Skills:', conn.execute(text('SELECT count(*) FROM skill_definitions')).scalar())
    print('Workflows:', conn.execute(text('SELECT count(*) FROM workflow_definitions')).scalar())
    print('Sections:', conn.execute(text('SELECT count(*) FROM shared_capability_sections')).scalar())
