import sqlite3
import json
from datetime import datetime
from typing import Any, Optional


class NexusTestDB:
    def __init__(self, db_path: str = "test_nexus_db.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()

    def get_table_names(self) -> list[str]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_table_count(self, table: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]

    def get_all_rows(self, table: str, limit: int = 10) -> list[dict]:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {table} LIMIT ?", (limit,))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_row_by_id(self, table: str, id: str) -> Optional[dict]:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {table} WHERE id = ?", (id,))
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None

    def get_agents(self, limit: int = 10) -> list[dict]:
        return self.get_all_rows("agent_definitions", limit)

    def get_tools(self, limit: int = 10) -> list[dict]:
        return self.get_all_rows("tool_definitions", limit)

    def get_skills(self, limit: int = 10) -> list[dict]:
        return self.get_all_rows("skill_definitions", limit)

    def get_workflows(self, limit: int = 10) -> list[dict]:
        return self.get_all_rows("workflow_definitions", limit)

    def get_prompts(self, limit: int = 10) -> list[dict]:
        return self.get_all_rows("prompt_definitions", limit)

    def search_agents(self, **kwargs) -> list[dict]:
        cursor = self.conn.cursor()
        conditions = []
        values = []
        for k, v in kwargs.items():
            conditions.append(f"{k} LIKE ?")
            values.append(f"%{v}%")
        sql = (
            f"SELECT * FROM agent_definitions WHERE {' OR '.join(conditions)} LIMIT 50"
        )
        cursor.execute(sql, values)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_agent_by_id(self, agent_id: str) -> Optional[dict]:
        return self.get_row_by_id("agent_definitions", agent_id)

    def get_tool_by_id(self, tool_id: str) -> Optional[dict]:
        return self.get_row_by_id("tool_definitions", tool_id)

    def get_skill_by_id(self, skill_id: str) -> Optional[dict]:
        return self.get_row_by_id("skill_definitions", skill_id)

    def get_workflow_by_id(self, workflow_id: str) -> Optional[dict]:
        return self.get_row_by_id("workflow_definitions", workflow_id)


def test_database_structure():
    db = NexusTestDB()
    tables = db.get_table_names()
    expected = [
        "agent_definitions",
        "tool_definitions",
        "skill_definitions",
        "workflow_definitions",
        "prompt_definitions",
    ]
    for table in expected:
        assert table in tables, f"Missing table: {table}"
    db.close()
    print("PASS: Database structure test passed")


def test_data_counts():
    db = NexusTestDB()
    tables = db.get_table_names()
    total = 0
    for table in tables:
        count = db.get_table_count(table)
        total += count
        print(f"  {table}: {count} rows")
    print(f"  Total: {total} rows")
    assert total > 0, "No data in database"
    db.close()
    print("PASS: Data count test passed")


def test_agent_data():
    db = NexusTestDB()
    agents = db.get_agents()
    assert len(agents) > 0, "No agents found"
    agent = agents[0]
    assert "id" in agent, "Missing id field"
    assert "name" in agent, "Missing name field"
    print(f"  Sample agent: {agent['name']} ({agent['id']})")
    first_agent = db.get_agent_by_id(agents[0]["id"])
    assert first_agent is not None, "Failed to get agent by ID"
    db.close()
    print("PASS: Agent data test passed")


def test_tool_data():
    db = NexusTestDB()
    tools = db.get_tools()
    assert len(tools) > 0, "No tools found"
    tool = tools[0]
    assert "id" in tool, "Missing id field"
    print(f"  Sample tool: {tool['name']} ({tool['id']})")
    first_tool = db.get_tool_by_id(tools[0]["id"])
    assert first_tool is not None, "Failed to get tool by ID"
    db.close()
    print("PASS: Tool data test passed")


def test_skill_data():
    db = NexusTestDB()
    skills = db.get_skills()
    assert len(skills) > 0, "No skills found"
    skill = skills[0]
    assert "id" in skill, "Missing id field"
    print(f"  Sample skill: {skill['name']} ({skill['id']})")
    first_skill = db.get_skill_by_id(skills[0]["id"])
    assert first_skill is not None, "Failed to get skill by ID"
    db.close()
    print("PASS: Skill data test passed")


def test_workflow_data():
    db = NexusTestDB()
    workflows = db.get_workflows()
    assert len(workflows) > 0, "No workflows found"
    workflow = workflows[0]
    assert "id" in workflow, "Missing id field"
    print(f"  Sample workflow: {workflow['name']} ({workflow['id']})")
    first_workflow = db.get_workflow_by_id(workflows[0]["id"])
    assert first_workflow is not None, "Failed to get workflow by ID"
    db.close()
    print("PASS: Workflow data test passed")


def test_prompt_data():
    db = NexusTestDB()
    prompts = db.get_prompts()
    assert len(prompts) > 0, "No prompts found"
    prompt = prompts[0]
    assert "id" in prompt, "Missing id field"
    print(f"  Sample prompt: {prompt['name']} ({prompt['id']})")
    db.close()
    print("PASS: Prompt data test passed")


def test_query_samples():
    db = NexusTestDB()
    agents = db.search_agents(agent_type="react")
    print(f"  React agents: {len(agents)}")
    tools = db.get_tools(limit=5)
    categories = set()
    for t in tools:
        if t.get("category"):
            categories.add(t["category"])
    print(f"  Tool categories: {list(categories)[:5]}")
    db.close()
    print("PASS: Query samples test passed")


def run_all_tests():
    print("=== Nexus DB Test Suite ===\n")
    print("1. Structure Tests")
    test_database_structure()
    print("\n2. Data Counts")
    test_data_counts()
    print("\n3. Entity Data Tests")
    test_agent_data()
    test_tool_data()
    test_skill_data()
    test_workflow_data()
    test_prompt_data()
    print("\n4. Query Tests")
    test_query_samples()
    print("\n=== All Tests Passed ===")


if __name__ == "__main__":
    run_all_tests()
