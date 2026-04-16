import sys
import os
from common_lib.modules.orchestration.agents.skill.schemas import CapabilityDefinition
from app.core.common_lib_integration import common_memory
import logging

logging.basicConfig(level=logging.INFO)

def check_skills():
    print("--- Listing and Validating Skills ---")
    skills = common_memory.list_skill_definitions()
    print(f"Count: {len(skills)}")
    
    for s in skills:
        s_id = s.get('id', 'unknown')
        print(f"Checking skill: {s_id}")
        try:
            # Skill normalization logic from registry.py
            if not isinstance(s.get('description'), str):
                 from app.modules.entities.routes.registry import normalize_description
                 s['description'] = normalize_description(s.get('description'))
            
            meta = s.get("metadata") or {}
            if "format" not in meta:
                meta["format"] = "config"
            if "subtype" not in meta:
                meta["subtype"] = "skill"
            s["metadata"] = meta
            
            CapabilityDefinition.model_validate(s)
            print(f"  [OK] {s_id}")
        except Exception as e:
            print(f"  [ERROR] {s_id}: {e}")
            # print(f"  Raw data: {s}")

if __name__ == "__main__":
    check_skills()
