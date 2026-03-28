import os
import yaml
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException
from pathlib import Path
from app.modules.common.types.index import APIResponse

router = APIRouter()

# --- CONFIGURATION ---
REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.resolve()
TEMPLATES_DIR = REPO_ROOT / "Python Libs" / "common_lib" / "src" / "common_lib" / "templates" / "prompts" / "simple"

CATEGORY_MAP = {
    "instructions": "system",
    "guardrails": "safety",
    "constraints": "constraints",
    "preferences": "guidelines",
    "knowledge": "knowledge",
    "skills": "skills",
    "agents": "agents",
    "examples": "examples"
}

REVERSE_CATEGORY_MAP = {v: k for k, v in CATEGORY_MAP.items()}

def load_template(file_path: Path) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        # Ensure category matches our logical division if it's in a subfolder
        folder_name = file_path.parent.name
        logical_category = REVERSE_CATEGORY_MAP.get(folder_name, folder_name)
        data["logical_category"] = logical_category
        return data

@router.get("/", response_model=APIResponse[Dict[str, List[Dict[str, Any]]]])
def list_templates(category: Optional[str] = Query(None, description="Filter by logical category: instructions, guardrails, constraints, preferences")):
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
            # If not in map, try raw folder name or return empty
            mapped_folder = category
        folders_to_scan.append(mapped_folder)
    else:
        folders_to_scan = list(CATEGORY_MAP.values())

    for folder in folders_to_scan:
        folder_path = TEMPLATES_DIR / folder
        if not folder_path.exists():
            continue
            
        logical_name = REVERSE_CATEGORY_MAP.get(folder, folder)
        results[logical_name] = []
        
        for file in folder_path.glob("*.yaml"):
            try:
                template_data = load_template(file)
                results[logical_name].append(template_data)
            except Exception as e:
                print(f"Error loading template {file}: {e}")

    return APIResponse(data=results, message="Templates retrieved successfully")

@router.get("/{template_id}", response_model=APIResponse[Dict[str, Any]])
def get_template(template_id: str):
    """
    Retrieve a specific template by its ID across all categories.
    """
    for folder_path in TEMPLATES_DIR.iterdir():
        if not folder_path.is_dir():
            continue
            
        for file in folder_path.glob("*.yaml"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data.get("id") == template_id:
                        logical_category = REVERSE_CATEGORY_MAP.get(folder_path.name, folder_path.name)
                        data["logical_category"] = logical_category
                        return APIResponse(data=data, message="Template retrieved successfully")
            except Exception:
                continue
                
    raise HTTPException(status_code=404, detail=f"Template with ID '{template_id}' not found")
