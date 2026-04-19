import logging
from typing import Any, Dict, AsyncGenerator
from common_lib.modules.image_processing.controllers.vision_task_controller import (
    VisionTaskController,
)
from .schemas import VisionGenerateRequest

logger = logging.getLogger(__name__)


class VisionService:
    def __init__(self):
        self.controller = VisionTaskController()

    def generate_high_res(self, request: VisionGenerateRequest) -> Dict[str, Any]:
        """
        Calls the common_lib VisionTaskController to execute the upscale workflow.
        """
        try:
            inference_response = self.controller.generate_sd15_high_res(
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                model_name=request.model_name,
                upscale_by=request.upscale_by,
                denoise=request.denoise,
                seed=request.seed,
            )

            return {
                "status": "success",
                "file_path": inference_response.file_path,
                "metadata": inference_response.metadata,
            }
        except Exception as e:
            logger.error(f"Vision Generation Failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def generate_high_res_stream(
        self, request: VisionGenerateRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the SD 1.5 Hires-Upscale as a real workflow and streams telemetry.
        """
        import os
        import asyncio
        import threading
        import uuid
        from dataclasses import asdict
        from common_lib.modules.workflows.standard.loaders.workflow_loader import WorkflowLoader
        from common_lib.modules.workflows.standard.execution.executor import GraphExecutor
        from common_lib.modules.workflows.standard.execution.core import ExecutionEngine
        from common_lib.modules.workflows.standard.execution.context import ExecutionContext
        from common_lib.modules.workflows.standard.observability import EventTracer, EventType

        # 1. Setup the inputs Exactly like common_lib controller does
        inputs = {
            "model": {"checkpoint_name": request.model_name, "device": "cuda"},
            "prompt": {
                "positive": request.prompt,
                "negative": request.negative_prompt,
                "clip_skip": 2,
            },
            "latent": {"width": 512, "height": 512},
            "sampler": {
                "steps": request.steps if request.steps else 25,
                "cfg": 7.0,
                "sampler_name": "dpmpp_2m_sde",
                "scheduler": "karras",
                "seed": request.seed,
            },
            "postprocess": {
                "upscale_by": request.upscale_by,
                "denoise": 0.55 if not request.denoise else request.denoise,
            },
            "output": {
                "output_dir": "generated_content/{workflow}/{date}/{model}",
                "filename_pattern": f"high_res_{request.seed or 'auto'}",
            },
        }

        # 2. Resolve Graph Path from common_lib templates
        import common_lib

        base_path = os.path.dirname(common_lib.__file__)
        workflow_path = os.path.join(
            base_path, "templates/workflows/vision/vision_sd15_upscale.workflow.yaml"
        )

        loader = WorkflowLoader()
        graph = loader.load_from_file(workflow_path)

        # 3. Setup Queue and Streaming context
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        class QueueBackend:
            def emit(self, event):
                try:
                    data = asdict(event)
                    if "event_type" in data and isinstance(
                        data["event_type"], EventType
                    ):
                        data["event_type"] = data["event_type"].value
                    if "timestamp" in data and hasattr(data["timestamp"], "isoformat"):
                        data["timestamp"] = data["timestamp"].isoformat()
                    loop.call_soon_threadsafe(queue.put_nowait, data)
                except Exception as e:
                    logger.error(f"Failed to emit vision event: {e}")

            def flush(self):
                pass

            def close(self):
                pass

        def run_sync():
            try:
                # 1. Initialize Registry and discover tools
                from common_lib.modules.core_infrastructure.registry import (
                    RegistryService,
                )

                # We try to get the shared registry from the demo module if it's already initialized
                # to save memory and skip discovery, but we don't block on it.
                registry = None
                try:
                    from app.modules.agents.runtime.core import get_engine_manager

                    em = get_engine_manager()
                    if em and em.registry_svc:
                        registry = em.registry_svc
                except Exception:
                    pass

                if registry is None:
                    # Fallback: Create a local registry for this vision task
                    logger.info(
                        "Initializing local tool registry for vision workflow..."
                    )
                    registry = RegistryService()

                # Force discovery to ensure all new YAML-based tools are registered
                # This ensures Character DNA tools from templates/tools are active
                logger.info("Forcing Vision Tool Discovery Refresh...")
                registry.auto_register_common_lib_tools()

                engine = ExecutionEngine(registry=registry)
                tracer = EventTracer()
                tracer.add_backend(QueueBackend())
                executor = GraphExecutor(engine, tracer)
                context = ExecutionContext(agent_id="vision_system", role="executor")
                executor.execute(graph, inputs, context)
            except Exception as e:
                logger.error(f"Streaming vision execution failed: {e}")
            finally:
                loop.call_soon_threadsafe(
                    queue.put_nowait, {"event_type": "workflow.finished"}
                )

        # Execute in background thread to avoid blocking the event loop
        threading.Thread(target=run_sync, daemon=True).start()

        while True:
            event = await queue.get()
            if event.get("event_type") == "workflow.finished":
                break
            yield event

    def save_upload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Saves a base64-encoded image to the ASSETS_DIR.
        """
        import os
        import uuid
        import base64
        from common_lib.paths import ASSETS_DIR

        try:
            os.makedirs(ASSETS_DIR, exist_ok=True)

            image_data = data.get("image", "")
            filename = data.get("filename", "upload.png")

            # Extract actual base64 content if it's a data URL
            if "," in image_data:
                image_data = image_data.split(",")[1]

            img_bytes = base64.b64decode(image_data)

            name, ext = os.path.splitext(filename)
            unique_name = f"{name}_{uuid.uuid4().hex[:6]}{ext or '.png'}"
            save_path = ASSETS_DIR / unique_name

            with open(save_path, "wb") as f:
                f.write(img_bytes)

            logger.info(f"Saved base64 upload to {save_path}")

            return {
                "status": "success",
                "filename": unique_name,
                "path": f"assets/{unique_name}",
                "full_path": str(save_path),
            }
        except Exception as e:
            logger.error(f"Failed to save base64 upload: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def get_gallery(self) -> Dict[str, Any]:
        """
        Recursively scans the generated_content directory and returns a structured list of images.
        """
        import os
        from PIL import Image

        # Base directory relative to the project root (where main.py runs)
        # Assuming we are in Monorepo/Backend Monorepo/Backend
        base_dir = os.path.join(os.getcwd(), "generated_content")

        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)
            return {"folders": []}

        folders = []
        for root, dirs, files in os.walk(base_dir):
            # Calculate relative path for URL and name
            rel_path = os.path.relpath(root, base_dir)

            # Filter for images
            files_to_process = [
                f
                for f in files
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
            ]

            if files_to_process:
                # Construct clean URL path
                url_prefix = rel_path.replace("\\", "/")
                if url_prefix == ".":
                    url_prefix = ""
                else:
                    url_prefix = url_prefix.strip("/") + "/"

                image_list = []
                for f in files_to_process:
                    full_path = os.path.join(root, f)
                    metadata = {}
                    try:
                        # Only try to read metadata for supported formats, primarily PNG for SD settings
                        if f.lower().endswith(".png"):
                            with Image.open(full_path) as img_obj:
                                metadata = {
                                    k: v
                                    for k, v in img_obj.info.items()
                                    if isinstance(v, (str, int, float, bool))
                                }
                    except Exception as e:
                        logger.warning(f"Could not read metadata for {f}: {e}")

                    image_list.append(
                        {
                            "filename": f,
                            "url": f"http://localhost:8000/generated/{url_prefix}{f}",
                            "timestamp": os.path.getmtime(full_path),
                            "metadata": metadata,
                        }
                    )

                folders.append(
                    {
                        "name": "Latest" if rel_path == "." else rel_path,
                        "path": rel_path,
                        "images": image_list,
                    }
                )

        # Sort folders by name (Latest first)
        folders.sort(key=lambda x: x["name"] if x["name"] != "Latest" else "0")

        # Sort images in each folder by timestamp (Newest first)
        for f in folders:
            f["images"].sort(key=lambda x: x["timestamp"], reverse=True)

        return {"folders": folders}

    def run_workflow_with_config(
        self, workflow_yaml: str, config_yaml: str, seed: int = None
    ) -> Dict[str, Any]:
        """
        Run a workflow with data config overlay.

        Args:
            workflow_yaml: Name of workflow YAML (e.g., 'hires_fix.sd15.dreamshaper')
            config_yaml: Name of data config YAML (e.g., 'cyberpunk_streetscape')
            seed: Optional random seed

        Returns:
            Dict with status, file_path, and metadata
        """
        import os
        import yaml as pyyaml
        from common_lib.paths import TEMPLATES_ROOT

        try:
            # 1. Load workflow template - check multiple locations
            workflow_candidates = [
                TEMPLATES_ROOT
                / "workflows"
                / "executable"
                / "stable_diffusion"
                / "sd15"
                / f"{workflow_yaml}.yaml",
                TEMPLATES_ROOT
                / "workflows"
                / "executable"
                / "stable_diffusion"
                / "sd15"
                / f"{workflow_yaml}.workflow.yaml",
            ]

            workflow_path = None
            for candidate in workflow_candidates:
                if candidate.exists():
                    workflow_path = candidate
                    break

            if not workflow_path:
                return {
                    "status": "error",
                    "message": f"Workflow not found: {workflow_yaml}",
                }

            with open(workflow_path, "r", encoding="utf-8") as f:
                workflow_data = pyyaml.safe_load(f)

            # 2. Load data config
            config_candidates = [
                TEMPLATES_ROOT
                / "workflows"
                / "data-config"
                / "sd15"
                / f"{config_yaml}.yaml",
                TEMPLATES_ROOT
                / "workflows"
                / "data-config"
                / "sd15"
                / f"{config_yaml}.yml",
            ]

            config_path = None
            for candidate in config_candidates:
                if candidate.exists():
                    config_path = candidate
                    break

            if not config_path:
                return {
                    "status": "error",
                    "message": f"Config not found: {config_yaml}",
                }

            with open(config_path, "r", encoding="utf-8") as f:
                config_data = pyyaml.safe_load(f)

            data_config = config_data.get("data_config", {})

            # 3. Extract parameters from config and merge with workflow defaults
            prompt = data_config.get("prompt", "hyper-realistic portrait")
            negative_prompt = data_config.get("negative_prompt", "blurry, low quality")
            width = data_config.get("width", 1024)
            height = data_config.get("height", 1536)
            steps = data_config.get("steps", 20)
            cfg = data_config.get("cfg_scale", 7.0)
            sampler = data_config.get("sampler", "dpmpp_2m_sde")
            scheduler = data_config.get("scheduler", "karras")

            # 4. Build inputs for execution
            inputs = {
                "model": {
                    "checkpoint_name": "dreamshaper_8.safetensors",
                    "device": "cuda",
                },
                "prompt": {
                    "positive": prompt,
                    "negative": negative_prompt,
                    "clip_skip": 2,
                },
                "latent": {"width": width, "height": height},
                "sampler": {
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": sampler,
                    "scheduler": scheduler,
                    "seed": seed,
                },
                "postprocess": {"upscale_by": 2.0, "denoise": 0.55},
                "output": {
                    "output_dir": "generated_content/{workflow}/{date}/{model}",
                    "filename_pattern": f"{config_yaml}_{seed or 'auto'}",
                },
            }

            logger.info(f"Running workflow {workflow_yaml} with config {config_yaml}")
            logger.info(f"Prompt: {prompt[:50]}...")

            # 5. Execute workflow using GraphExecutor directly
            from common_lib.modules.workflows.standard.loaders.workflow_loader import (
                WorkflowLoader,
            )
            from common_lib.modules.workflows.standard.execution.executor import GraphExecutor
            from common_lib.modules.workflows.standard.execution.core import ExecutionEngine
            from common_lib.modules.workflows.standard.execution.context import ExecutionContext
            from common_lib.modules.core_infrastructure.registry import RegistryService

            # Load the workflow
            loader = WorkflowLoader()

            # Debug: Show raw data before load
            import yaml

            with open(workflow_path, "r") as f:
                raw_data = yaml.safe_load(f)
            logger.info(
                f"Raw workflow data keys: {raw_data.keys() if raw_data else 'None'}"
            )
            logger.info(
                f"Raw nodes count: {len(raw_data.get('nodes', [])) if raw_data else 0}"
            )
            logger.info(
                f"Raw edges count: {len(raw_data.get('edges', [])) if raw_data else 0}"
            )

            if raw_data and raw_data.get("nodes"):
                logger.info(f"First node keys: {raw_data['nodes'][0].keys()}")

            # Enable debug logging for loader
            import logging

            loader_logger = logging.getLogger(
                "common_lib.modules.workflows.standard.loaders.workflow_loader"
            )
            old_level = loader_logger.level
            loader_logger.setLevel(logging.DEBUG)

            graph = loader.load_from_file(str(workflow_path))

            # Restore log level
            loader_logger.setLevel(old_level)

            logger.info(
                f"Loader result: graph={graph}, states={len(graph.states) if graph and graph.states else 0}"
            )

            # Debug: Show raw data before load
            import yaml

            with open(workflow_path, "r") as f:
                raw_data = yaml.safe_load(f)
            logger.info(
                f"Raw workflow data keys: {raw_data.keys() if raw_data else 'None'}"
            )
            logger.info(
                f"Raw nodes count: {len(raw_data.get('nodes', [])) if raw_data else 0}"
            )
            logger.info(
                f"Raw edges count: {len(raw_data.get('edges', [])) if raw_data else 0}"
            )

            # Try to understand what format nodes are in
            if raw_data and raw_data.get("nodes"):
                logger.info(f"First node structure: {raw_data['nodes'][0]}")

            logger.info(f"Loaded workflow graph: {graph}")
            logger.info(
                f"Graph states: {list(graph.states.keys()) if graph else 'None'}"
            )
            if graph:
                for state_id, state in graph.states.items():
                    logger.info(
                        f"  State: {state_id}, tool_id: {state.tool_id}, static_inputs: {state.static_inputs}"
                    )

            logger.info(f"Graph start_state: {graph.start_state_id}")
            logger.info(f"Graph states count: {len(graph.states)}")

            # Log all states and their transitions
            for state_id, state in graph.states.items():
                trans_list = (
                    [t.to_state_id for t in state.transitions]
                    if state.transitions
                    else []
                )
                logger.info(
                    f"  State: {state_id}, tool_id: {state.tool_id}, transitions: {trans_list}"
                )

            # Initialize registry and execution engine
            registry = RegistryService()
            registry.auto_register_common_lib_tools()

            # Check if vision tools are registered
            all_tools = registry.list_tools()
            vision_tools = [
                t.id if hasattr(t, "id") else str(t)
                for t in all_tools
                if (hasattr(t, "id") and t.id.startswith("vision."))
                or str(t).startswith("vision.")
            ]
            logger.info(f"Registered vision tools count: {len(vision_tools)}")

            # Also check if there's a load_checkpoint tool
            checkpoint_tool = registry.get_tool("vision.load_checkpoint")
            logger.info(f"vision.load_checkpoint tool: {checkpoint_tool}")

            engine = ExecutionEngine(registry=registry)
            executor = GraphExecutor(engine)
            context = ExecutionContext(agent_id="vision_system", role="executor")

            try:
                # Execute with inputs
                memory = executor.execute(graph, inputs, context)
            except Exception as exec_error:
                logger.error(
                    f"GraphExecutor.execute failed: {exec_error}", exc_info=True
                )
                # Try to get partial results
                memory = {}

            logger.info(
                f"Execution memory keys: {list(memory.keys()) if isinstance(memory, dict) else type(memory)}"
            )
            logger.info(
                f"Last output: {memory.get('last_output') if isinstance(memory, dict) else 'N/A'}"
            )
            if isinstance(memory, dict) and memory.get("error"):
                logger.error(f"Execution error: {memory.get('error')}")
                logger.error(f"Failed state: {memory.get('failed_state')}")

            # Extract output file path
            last_out = {}
            if isinstance(memory, dict):
                last_out = memory.get("last_output", {})
            file_path = None
            if last_out and isinstance(last_out, dict):
                paths = last_out.get("output_paths", [])
                if paths and len(paths) > 0:
                    file_path = paths[0]

            return {
                "status": "success" if file_path else "partial",
                "file_path": file_path,
                "metadata": {
                    "workflow": workflow_yaml,
                    "config": config_yaml,
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "width": width,
                    "height": height,
                    "steps": steps,
                    "cfg": cfg,
                    "latency_ms": last_out.get("latency_ms", 0) if last_out else 0,
                },
            }

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}


vision_service = VisionService()
