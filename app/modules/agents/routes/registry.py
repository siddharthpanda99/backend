from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException, Body
from pathlib import Path
import yaml
from app.modules.common.types.index import APIResponse

router = APIRouter()

# --- CONFIGURATION ---
# Correctly resolve to the 'Backend Monorepo' root
# Current: Monorepo/Backend Monorepo/Backend/app/modules/agents/routes/registry.py
# Current: Monorepo/Backend Monorepo/Backend/app/modules/agents/routes/registry.py
# Target: Monorepo/Backend Monorepo/
REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATES_DIR = REPO_ROOT / "Python Libs" / "common_lib" / "src" / "common_lib" / "templates"

CATEGORY_MAP = {
    "instructions": "prompts",
    "guardrails": "prompts",
    "constraints": "prompts",
    "preferences": "prompts",
    "knowledge": "knowledge",
    "skills": "skills",
    "agents": "configs/agents",
    "examples": "prompts/examples",
    "tools": "tools",
    "workflows": "configs/workflows"
}

REVERSE_CATEGORY_MAP = {v: k for k, v in CATEGORY_MAP.items()}

def load_template(file_path: Path) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        if not data:
            return {}
        # Ensure category matches our logical division if it's in a subfolder
        folder_name = file_path.parent.name
        # Special case for configs/agents which has two levels
        if "agents" in str(file_path):
            logical_category = "agents"
        else:
            logical_category = REVERSE_CATEGORY_MAP.get(folder_name, folder_name)
        data["logical_category"] = logical_category
        # Ensure an 'id' exists for the UI
        if "id" not in data:
            data["id"] = data.get("agent_id") or data.get("workflow_id") or data.get("skill_id") or file_path.stem
        return data

@router.get("/", response_model=APIResponse[Dict[str, List[Dict[str, Any]]]])
def list_templates(category: Optional[str] = Query(None, description="Filter by logical category: instructions, guardrails, agents, tools, etc.")):
    """
    List all available templates from the common_lib registry.
    Supports filtering by logical category.
    """
    if not TEMPLATES_DIR.exists():
        raise HTTPException(status_code=500, detail=f"Templates directory not found at {TEMPLATES_DIR}")

    results = {}
    
    # Determine which folders to scan
    folders_to_scan = []
    if category:
        mapped_folder = CATEGORY_MAP.get(category.lower())
        if not mapped_folder:
            mapped_folder = category
        folders_to_scan.append(mapped_folder)
    else:
        # Scan all primary categories
        folders_to_scan = list(set(CATEGORY_MAP.values()))

    for folder in folders_to_scan:
        folder_path = TEMPLATES_DIR / folder
        if not folder_path.exists():
            continue
            
        logical_name = REVERSE_CATEGORY_MAP.get(folder, folder)
        if logical_name not in results:
            results[logical_name] = []
        
        # Recursive glob to find nested templates (e.g. in configs/agents)
        for file in folder_path.rglob("*.yaml"):
            # Skip hidden files and special metadata
            if file.name.startswith(("_", "index", "manifest")):
                continue
            try:
                template_data = load_template(file)
                if template_data:
                    results[logical_name].append(template_data)
            except Exception as e:
                print(f"Error loading template {file}: {e}")

    return APIResponse(data=results, message="Templates retrieved successfully")

@router.get("/{template_id}", response_model=APIResponse[Dict[str, Any]])
def get_template(template_id: str):
    """
    Retrieve a specific template by its ID across all categories.
    """
    # Scan all directories in CATEGORY_MAP
    for folder in set(CATEGORY_MAP.values()):
        folder_path = TEMPLATES_DIR / folder
        if not folder_path.exists():
            continue
            
        for file in folder_path.rglob("*.yaml"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if not data:
                        continue
                    
                    # Check multiple ID fields for legacy compatibility
                    current_id = data.get("id") or data.get("agent_id") or data.get("workflow_id") or data.get("skill_id")
                    if current_id == template_id:
                        logical_category = REVERSE_CATEGORY_MAP.get(folder, folder)
                        data["logical_category"] = logical_category
                        if "id" not in data:
                            data["id"] = current_id
                        return APIResponse(data=data, message="Template retrieved successfully")
            except Exception:
                continue
    raise HTTPException(status_code=404, detail=f"Template with ID '{template_id}' not found")

@router.post("/save", response_model=APIResponse[Dict[str, Any]])
def save_template(
    payload: Dict[str, Any] = Body(...),
    category: str = Query(..., description="Logical category: instructions, guardrails, etc.")
):
    """
    Save a new template or update an existing one in the registry.
    """
    if not TEMPLATES_DIR.exists():
        raise HTTPException(status_code=500, detail="Templates directory not found")

    mapped_folder = CATEGORY_MAP.get(category.lower())
    if not mapped_folder:
        raise HTTPException(status_code=400, detail=f"Invalid category '{category}'")

    target_dir = TEMPLATES_DIR / mapped_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    template_id = payload.get("id")
    if not template_id:
        # Generate ID from name
        name = payload.get("name", "unnamed_template")
        template_id = name.lower().replace(" ", "_")
        payload["id"] = template_id

    file_path = target_dir / f"{template_id}.yaml"
    
    # Save as YAML
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, sort_keys=False, allow_unicode=True)

    return APIResponse(data=payload, message=f"Template '{template_id}' saved successfully to {category}")
