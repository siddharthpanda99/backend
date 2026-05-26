"""Run one vision workflow through the API and record results."""

import json, sys, os, time, re
import yaml
import requests
from pathlib import Path

WORKFLOWS_DIR = Path(
    "C:/Users/91797/Documents/Dev/JS/Monorepo/Backend Monorepo/Python Libs/common_lib/src/common_lib/templates/workflows/executable"
)
API_BASE = "http://localhost:8000"


def resolve_workflow_template(yaml_data: dict, config: dict):
    parameters = yaml_data.get("parameters", {})
    param_defaults = {
        k: str(v["default"])
        for k, v in parameters.items()
        if isinstance(v, dict) and "default" in v
    }

    def _lookup(name: str) -> str:
        parts = name.split(".")
        val = config
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                val = None
                break
        if val is not None:
            return str(val)
        if name in param_defaults:
            return param_defaults[name]
        return None

    def _resolve(v):
        if not isinstance(v, str) or "{{" not in v:
            return v

        def _replacer(m):
            resolved = _lookup(m.group(1))
            return resolved if resolved is not None else m.group(0)

        return re.sub(r"\{\{(\w+(?:\.\w+)*)\}\}", _replacer, v)

    nodes = []
    for n in yaml_data.get("nodes", []):
        node = dict(n)
        props = node.get("properties", {})
        if props:
            node["properties"] = {k: _resolve(v) for k, v in props.items()}
        nodes.append(node)
    return nodes, yaml_data.get("edges", [])


def find_workflow_file(workflow_id: str) -> Path:
    for f in sorted(WORKFLOWS_DIR.rglob("*.workflow.yaml")):
        try:
            with open(f) as fh:
                data = yaml.safe_load(fh)
            if data.get("id") == workflow_id:
                return f
        except Exception:
            continue
    return None


def run_workflow_via_api(workflow_id: str, config: dict, timeout: int = 300) -> dict:
    wf_path = find_workflow_file(workflow_id)
    if not wf_path:
        return {"success": False, "error": f"Workflow '{workflow_id}' not found"}

    with open(wf_path) as f:
        yaml_data = yaml.safe_load(f)

    nodes, edges = resolve_workflow_template(yaml_data, config)
    payload = {"nodes": nodes, "edges": edges, "inputs": config}
    url = f"{API_BASE}/api/v1/workflows/run-stream"

    print(f"  POST {url} with {len(nodes)} nodes, {len(edges)} edges")
    print(f"  Checkpoint: {config.get('checkpoint_name', 'default')}")
    print(f"  Prompt: {config.get('prompt', 'N/A')[:60]}...")

    start = time.time()
    try:
        resp = requests.post(url, json=payload, stream=True, timeout=(10, None))
        print(f"  Response status: {resp.status_code}")
        print(f"  Headers: {dict(resp.headers)}")
        resp.raise_for_status()
        event_count = 0
        for line in resp.iter_lines(decode_unicode=True):
            elapsed = time.time() - start
            if line:
                print(f"  Line ({elapsed:.1f}s): {line[:200]}")
                if line.startswith("data: "):
                    event_count += 1
                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError as e:
                        print(f"  JSON parse error: {e}")
                        continue
                    et = event.get("event_type")
                    if et == "workflow.completed":
                        return {"success": True, "elapsed": elapsed, "config": config}
                    if et == "workflow.failed":
                        err = (
                            event.get("error")
                            or event.get("metadata", {}).get("error")
                            or "Workflow failed"
                        )
                        return {
                            "success": False,
                            "elapsed": elapsed,
                            "error": err,
                            "config": config,
                        }
        print(f"  Total events: {event_count}")
        return {
            "success": False,
            "elapsed": time.time() - start,
            "error": f"No terminal event (got {event_count} events)",
            "config": config,
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "elapsed": time.time() - start,
            "error": f"Cannot connect to {API_BASE}",
        }
    except Exception as e:
        return {"success": False, "elapsed": time.time() - start, "error": str(e)}


if __name__ == "__main__":
    # Test 1: sd15 basic txt2img
    workflow_id = "sd15"
    config = {
        "checkpoint_name": "dreamshaper_8.safetensors",
        "model_type": "sd15",
        "prompt": "breathtaking landscape, hyper-realistic, 8k resolution, photorealistic",
        "negative_prompt": "blurry, low quality, distorted, watermark",
        "width": 512,
        "height": 512,
        "steps": 20,
        "cfg": 7.0,
        "sampler": "euler",
        "scheduler": "normal",
        "denoise": 1.0,
    }

    print(f"\n{'=' * 60}")
    print(f"Running workflow: {workflow_id}")
    print(f"{'=' * 60}")
    result = run_workflow_via_api(workflow_id, config)

    if result["success"]:
        print(f"\nPASS {workflow_id} in {result['elapsed']:.1f}s")
    else:
        print(
            f"\nFAIL {workflow_id}: {result.get('error', 'unknown')} in {result.get('elapsed', 0):.1f}s"
        )

    print(f"\n{'=' * 60}")
    print("RESULT SUMMARY")
    print(f"{'=' * 60}")
    print(json.dumps(result, indent=2, default=str))
