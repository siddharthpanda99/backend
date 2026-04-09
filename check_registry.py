import os
import yaml
from common_lib.modules.orchestration.agent.schemas import AgentTemplate

def scan_all():
    root = "Backend Monorepo/Python Libs/common_lib/src/common_lib/templates"
    paths = [
        "configs/agents",
        "configs/skills",
        "prompt_registry"
    ]
    
    print(f"{'Path':<60} | {'Status':<10}")
    print("-" * 75)
    
    for p in paths:
        full_p = os.path.join(root, p)
        if not os.path.exists(full_p):
            print(f"Directory not found: {full_p}")
            continue
            
        for f in os.listdir(full_p):
            if f.endswith(".yaml"):
                file_path = os.path.join(full_p, f)
                try:
                    with open(file_path, "r", encoding="utf-8") as stream:
                        docs = list(yaml.safe_load_all(stream))
                        for doc in docs:
                            if not doc:
                                continue
                            # Lightweight validation with AgentTemplate
                            try:
                                AgentTemplate.from_dict(doc)
                                print(f"{os.path.join(p, f):<60} | [PASS]")
                            except Exception as e:
                                print(f"{os.path.join(p, f):<60} | [FAIL] {str(e)[:40]}...")
                except Exception as e:
                    print(f"{os.path.join(p, f):<60} | [ERROR] {str(e)[:40]}...")

if __name__ == "__main__":
    scan_all()
