import sys
import os
import json
from datetime import datetime

# Add common_lib and app to sys.path
sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "Python Libs", "common_lib", "src"
        )
    )
)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from common_lib.modules.orchestration.memory.services import SQLAlchemyMemoryStore


def seed_router_agent():
    print("--- Starting AgentIQ Master Skill-Router Seeding ---")
    store = SQLAlchemyMemoryStore()

    # 1. Initialize Shared Sections (Reference Entities)
    sections = [
        {
            "id": "instruction:agent_router_backbone",
            "type": "instruction",
            "content": {
                "complexity_level": "complex",
                "text": (
                    "# CORE IDENTITY: SKILL-ROUTER\n"
                    "You are AgentIQ Master, a high-fidelity 'Router Agent'. Your primary objective is to solve user queries by dynamically discovering and orchestrating specialized skills.\n\n"
                    "## RECONNAISSANCE & ROUTING\n"
                    "- If the user's request requires a capability you don't have, your FIRST step is to use `entity_search_mcp`.\n"
                    "- Use **Snippets** for quick utility/context and **Complex Skills** for deep dives.\n"
                    "- **Instructional Workflows** are your reasoning blueprints. If a task is multi-step, look for a matching flow.\n\n"
                    "## STRICT REACT LOOP\n"
                    "You MUST follow this format precisely:\n"
                    "Thought: <your reasoning>\n"
                    "Action: <tool_name>\n"
                    "Action Input: <json_args>\n"
                    "Observation: <tool_output>\n"
                    "... (repeat until solved)\n"
                    "Final Answer: <the response to user>\n\n"
                    "**CRITICAL**: NEVER include greetings (Hi, Hello) or conversational filler before an Action block. The parser will FAIL if you do."
                ),
            },
        },
        {
            "id": "instruction:conversation_intent_classifier",
            "type": "instruction",
            "content": {
                "complexity_level": "snippet",
                "text": (
                    "# CONVERSATION STEERING\n"
                    "Classification categories:\n"
                    "1. RESEARCH: Info retrieval.\n"
                    "2. CREATION: Generation.\n"
                    "3. TROUBLESHOOTING: Debugging.\n"
                    "4. SYSTEM: Deployment.\n\n"
                    "Adopting a tactical tone based on domain classification."
                ),
            },
        },
        {
            "id": "instruction:memory_context_harvesting",
            "type": "instruction",
            "content": {
                "complexity_level": "snippet",
                "text": (
                    "# CONTEXT HARVESTING (SNIPPET)\n"
                    "Proactively use `extract_and_remember_hints` for preferences/paths/jargon.\n"
                ),
            },
        },
        {
            "id": "instruction_flow:research_synthesis_standard",
            "type": "instruction_flow",
            "content": {
                "complexity_level": "complex",
                "text": (
                    "# RESEARCH & SYNTHESIS WORKFLOW\n"
                    "Follow these steps for any info-heavy request:\n"
                    "1. **Recon**: Use `query_capability_inventory` to find search tools if not enabled.\n"
                    "2. **Search**: Execute broad queries to gather multi-source data.\n"
                    "3. **Synthesize**: Use reasoning to extract core facts.\n"
                    "4. **Refine**: If gaps remain, iterate. Finalize with a structured response."
                ),
            },
        },
    ]

    for sec in sections:
        try:
            store.save_shared_section(
                section_id=sec["id"],
                section_type=sec["type"],
                content=sec["content"],
                is_system=True,
            )
            print(
                f"Successfully seeded/updated {sec['id']} ({sec.get('content', {}).get('complexity_level')})"
            )
        except Exception as e:
            print(f"Failed to seed {sec['id']}: {e}")

    # 2. Update AgentIQ Master Definition
    try:
        master = store.get_agent_definition("master_agent")
        if not master:
            print("Warning: master_agent record not found. Creating one.")
            master_id = "master_agent"
            master_name = "AgentIQ Master"
            master_identity = {"name": master_name, "version": "1.2.0"}
            master_definition = {"role": "orchestrator"}
        else:
            master_id = master["id"]
            master_name = master["name"]
            master_identity = master["identity"]
            master_identity["version"] = "1.2.0"  # Bump version
            master_definition = master["definition"]

        # Compose recursive prompt with the new workflow included
        composite_prompt = (
            "{{instruction:agent_router_backbone}}\n\n"
            "{{instruction:conversation_intent_classifier}}\n\n"
            "{{instruction:memory_context_harvesting}}\n\n"
            "{{instruction_flow:research_synthesis_standard}}"
        )

        store.save_agent_definition(
            name=master_name,
            agent_id=master_id,
            identity=master_identity,
            definition=master_definition,
            instructions_text=composite_prompt,
            prompt_template=composite_prompt,
            category="System",
        )
        print(
            "Successfully updated AgentIQ Master with recursive entity-based prompting and Instructional Flows."
        )
    except Exception as e:
        print(f"Failed to update master_agent: {e}")

    # 3. Categorize Core Toolkits
    toolkits = [
        {"id": "analytics", "cat": "Data"},
        {"id": "registry", "cat": "Registry"},
        {"id": "file_ops", "cat": "System"},
        {"id": "deployment", "cat": "System"},
        {"id": "code_analysis", "cat": "Code"},
    ]
    for tk in toolkits:
        try:
            # We don't have a direct upsert for ToolDefinitionRecord category yet,
            # but we can use save_tool_definition with metadata or just wait for the registry update.
            # For now, let's just confirm registry categories via instructions.
            pass
        except Exception:
            pass

    print("--- Seeding Complete ---")


if __name__ == "__main__":
    seed_router_agent()
