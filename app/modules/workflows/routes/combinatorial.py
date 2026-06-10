"""Combinatorial workflow generation API — cartesian product of prompts × params with parallel execution."""

import asyncio, datetime, json, logging, subprocess, time, traceback, uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from common_lib.modules.workflows.generation.combinatorial_schemas import (
    CombinatorialGenerateRequest,
    PromptConfig,
    compute_cartesian,
)

logger = logging.getLogger(__name__)
router = APIRouter()

MONOREPO_DIR = Path("C:/Users/91797/Documents/Dev/JS/Monorepo")
GENERATED_DIR = MONOREPO_DIR / "generated_content"
CLI_DIR = MONOREPO_DIR / "Backend Monorepo" / "Python Libs" / "common_lib"

WARN_THRESHOLD = 50

# In-memory store for combinatorial execution history
_execution_store: Dict[str, Dict[str, Any]] = {}


async def _run_subprocess(cmd: List[str], cwd: str, timeout: int) -> subprocess.CompletedProcess:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout),
    )


async def _run_one(
    sem: asyncio.Semaphore,
    runner: str | None,
    wf_id: str,
    output_subdir: str,
    overrides: Dict[str, Any],
    combo: Dict[str, Any],
    pc: PromptConfig,
    idx: int,
    total: int,
    execution_cfg: Any,
) -> Optional[Dict[str, Any]]:
    async with sem:
        logger.info(f"[Combinatorial] [{idx + 1}/{total}] {wf_id} | s={combo['sampler']} st={combo['steps']} cfg={combo['cfg']} {combo['width']}×{combo['height']} seed={combo['seed']}")
        try:
            if runner:
                cmd = ["uv", "run", "python", runner, wf_id, output_subdir]
                try:
                    result = await _run_subprocess(cmd, str(CLI_DIR), execution_cfg.timeoutMinutes * 60)
                except subprocess.TimeoutExpired:
                    return {"workflowId": wf_id, "status": "timeout", "prompt": pc.prompt[:60], "params": combo, "size": 0}
                if result.returncode != 0 and execution_cfg.retryOnFailure:
                    logger.info(f"[Combinatorial] Retry {wf_id} combo...")
                    try:
                        result = await _run_subprocess(cmd, str(CLI_DIR), execution_cfg.timeoutMinutes * 60)
                    except subprocess.TimeoutExpired:
                        return {"workflowId": wf_id, "status": "timeout", "prompt": pc.prompt[:60], "params": combo, "size": 0}
            else:
                cmd = ["uv", "run", "workflow-run", wf_id, "--inputs", json.dumps(overrides)]
                try:
                    result = await _run_subprocess(cmd, str(CLI_DIR), execution_cfg.timeoutMinutes * 60)
                except subprocess.TimeoutExpired:
                    return {"workflowId": wf_id, "status": "timeout", "prompt": pc.prompt[:60], "params": combo, "size": 0}

            for f in sorted(GENERATED_DIR.rglob("*.png")):
                age = time.time() - f.stat().st_mtime
                if age < 300:
                    return {"workflowId": wf_id, "filename": f.name, "path": str(f.relative_to(GENERATED_DIR)),
                            "size": f.stat().st_size, "width": combo["width"], "height": combo["height"],
                            "status": "completed", "prompt": pc.prompt[:60], "params": combo}
        except Exception as e:
            logger.error(f"[Combinatorial] Failed {wf_id}: {e}\n{traceback.format_exc()}")
            return {"workflowId": wf_id, "status": "failed", "error": f"{type(e).__name__}: {e}"[:200],
                    "prompt": pc.prompt[:60], "params": combo, "size": 0}
        return None


@router.get("/history")
async def combinatorial_history():
    entries = []
    for eid, record in _execution_store.items():
        entries.append({"executionId": eid, "timestamp": record["timestamp"], "status": record["status"],
                        "total": record["total"], "summary": record["summary"],
                        "workflowCount": len(record["config"]["workflows"]), "promptCount": len(record["config"]["prompts"])})
    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return {"entries": entries}


@router.get("/history/{execution_id}")
async def combinatorial_history_by_id(execution_id: str):
    record = _execution_store.get(execution_id)
    if not record:
        raise HTTPException(status_code=404, detail="Execution not found")
    return record


@router.post("/generate")
async def combinatorial_generate(req: CombinatorialGenerateRequest):
    execution_id = f"comb_{uuid.uuid4().hex[:8]}"
    runner = str(MONOREPO_DIR / "run_one_workflow.py")
    has_runner = Path(runner).exists()

    param_combos = compute_cartesian(req.common)
    prompts = req.prompts or [PromptConfig(
        prompt="beautiful woman, black transparent coat, full body shot, eyes closed, professional photoshoot, 8k, photorealistic",
        negativePrompt="blurry, low quality, distorted, bad anatomy, ugly",
    )]
    total = len(req.workflows) * len(prompts) * len(param_combos)

    if total > WARN_THRESHOLD:
        logger.warning(f"[Combinatorial] {execution_id}: LARGE GENERATION — {total} total images (threshold={WARN_THRESHOLD})")

    sem = asyncio.Semaphore(req.execution.maxConcurrent)
    tasks = []

    for wi, wf_id in enumerate(req.workflows):
        for pi, pc in enumerate(prompts):
            for ci, combo in enumerate(param_combos):
                base = req.output.baseDirectory
                if base.startswith("generated_content/"):
                    base = base[len("generated_content/"):]
                output_subdir = f"{base}/{wf_id}"
                overrides = {"prompt": pc.prompt, "negative_prompt": pc.negativePrompt, **combo}
                idx = wi * len(prompts) * len(param_combos) + pi * len(param_combos) + ci
                tasks.append(_run_one(sem, runner if has_runner else None, wf_id, output_subdir,
                                      overrides, combo, pc, idx, total, req.execution))

    results = await asyncio.gather(*tasks)
    all_artifacts = [r for r in results if r is not None]

    summary = {
        "completed": sum(1 for a in all_artifacts if a.get("status") == "completed"),
        "failed": sum(1 for a in all_artifacts if a.get("status") == "failed"),
        "timeout": sum(1 for a in all_artifacts if a.get("status") == "timeout"),
        "totalSize": sum(a.get("size", 0) for a in all_artifacts),
    }

    _execution_store[execution_id] = {
        "executionId": execution_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "status": "completed",
        "config": {"workflows": req.workflows,
                   "prompts": [{"prompt": p.prompt, "negativePrompt": p.negativePrompt} for p in prompts],
                   "common": req.common.model_dump(), "output": req.output.model_dump(),
                   "execution": req.execution.model_dump()},
        "total": total, "warnThreshold": total > WARN_THRESHOLD, "summary": summary, "artifacts": all_artifacts,
    }

    return {"executionId": execution_id, "status": "completed", "total": total,
            "warnThreshold": total > WARN_THRESHOLD, "artifacts": all_artifacts, "summary": summary}
