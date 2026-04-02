from sqlalchemy import create_engine, text
import json

# Connection string for the registry database
engine = create_engine("postgresql+psycopg2://postgres:postgres@localhost:5432/nexus_db")

def verify_enrichment():
    with engine.connect() as conn:
        print("--- Verifying Skill Enrichment (automated_pr_reviewer) ---")
        res = conn.execute(text("SELECT input_schema, output_schema FROM skill_definitions WHERE name = 'automated_pr_reviewer'")).fetchone()
        if res:
            print("\nInput Schema Sample:")
            print(json.dumps(res[0], indent=2))
            print("\nOutput Schema Sample:")
            print(json.dumps(res[1], indent=2))
        else:
            print("Skill 'automated_pr_reviewer' not found in database!")

        print("\n--- Verifying Agent Enrichment (senior_dev) ---")
        res = conn.execute(text("SELECT input_schema, output_schema FROM agent_definitions WHERE agent_id = 'senior_dev'")).fetchone()
        if res:
            print("\nInput Schema Sample:")
            print(json.dumps(res[0], indent=2))
        else:
            print("Agent 'senior_dev' not found in database!")

if __name__ == "__main__":
    verify_enrichment()
