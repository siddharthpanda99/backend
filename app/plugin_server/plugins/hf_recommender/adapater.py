"""Adapter for hf_recommender — wraps the 3rd-party
huggingface_model_recommender library into a BaseToolPlugin.

This is the ONLY file in this plugin folder that imports
common_lib. The 3rd-party code in `cloned_or_extracted_repo/` is
untouched.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from common_lib.modules.plugin_sdk.runtime.adapter_base import BaseAdapter
from common_lib.modules.plugins.base import BaseToolPlugin
from common_lib.modules.plugins.schemas import PluginMetadata

logger = logging.getLogger(__name__)


class HfRecommenderAdapter(BaseAdapter):
    """Adapter for the 3rd-party HuggingFace model recommender."""

    def discover(self) -> list[BaseToolPlugin]:

     # Universal deepseek-style lifecycle applied to this plugin
        # Universal deepseek-style lifecycle applied to this plugin
        from app.plugin_server.panels import PluginLifecycle, PluginPhase, PluginCapability
        self.lifecycle = PluginLifecycle(
            plugin_id="hf_recommender",
            phases=[
                PluginPhase("init", "Initialize HF catalog"),
                PluginPhase("ready", "Ready to recommend models"),
            ],
            capabilities=[
                PluginCapability("search", "Search HF models for a task", requires_auth=False),
                PluginCapability("recommend", "Recommend best model", requires_auth=False),
            ],
            model_invocable=True,    # AI agents can call
            user_invocable=True,      # UI can use
            health_check_interval_sec=60.0,
        )

        # Make the cloned/ code importable
        """Build the plugin instance from the 3rd-party library."""
        # Make the 3rd-party code importable
        self.add_cloned_to_sys_path()

        # Import the 3rd-party library
        try:
            # The 3rd-party code is in cloned_or_extracted_repo/
            import hf_recommender_lib as hf  # 3rd-party
        except ImportError as e:
            raise ImportError(
                f"hf_recommender: failed to import 3rd-party library: {e}"
            ) from e

        metadata = PluginMetadata(
            id="hf_recommender",
            name="HuggingFace Model Recommender",
            version="1.0.0",
            description=(
                "Recommend HuggingFace models for any task. "
                "Search by task type, framework, and popularity."
            ),
            category="ai",
            author="3rd-party (RashAlbainy/huggingface_model_recommender)",
            tags=["huggingface", "model-recommender", "ai", "third-party"],
            dependencies=[],
            required_keys=[],  # No API key needed for the public HF Hub
        )

        from common_lib.modules import plugin_sdk as sdk

        class HfRecommenderPlugin(BaseToolPlugin):
            """Adapter exposing the 3rd-party recommender as @tool methods."""

            def __init__(self):
                self.metadata = metadata
                self._hf = hf  # 3rd-party module reference

            def check_health(self):
                from common_lib.modules.plugins.schemas import (
                    HealthStatus,
                    PluginHealth,
                )

                try:
                    tasks = self._hf.list_tasks()
                    return PluginHealth(
                        status=HealthStatus.HEALTHY,
                        message=f"OK ({len(tasks)} tasks available)",
                    )
                except Exception as e:
                    return PluginHealth(
                        status=HealthStatus.DEGRADED,
                        message=str(e),
                    )

            def get_nodes(self):
                return [
                    {
                        "name": "hf_recommender.search_models",
                        "entity_type": "tool",
                        "description": "Search HuggingFace models for a task.",
                    },
                    {
                        "name": "hf_recommender.list_tasks",
                        "entity_type": "tool",
                        "description": "List available HF task types.",
                    },
                    {
                        "name": "hf_recommender.get_model_info",
                        "entity_type": "tool",
                        "description": "Get info about a specific HF model.",
                    },
                ]

            @sdk.tool(
                name="search_models",
                description=(
                    "Search HuggingFace Hub for models matching a task. "
                    "Filter by minimum downloads, framework, and sort by "
                    "downloads/likes/trending."
                ),
            )
            @sdk.node(
                name="hf_recommender.search_models",
                description="Search HuggingFace models for a task.",
                category="hf_recommender",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "task": sdk.string_field(
                            "HF task (e.g. 'text-generation', 'translation', "
                            "'summarization', 'image-classification')."
                        ),
                        "min_downloads": sdk.number_field(
                            "Minimum download count.",
                            default=0,
                        ),
                        "framework": sdk.string_field(
                            "Framework filter (e.g. 'pytorch', 'gguf').",
                            required=False,
                        ),
                        "sort_by": sdk.string_field(
                            "Sort field.",
                            default="downloads",
                        ),
                        "top_k": sdk.number_field("Max results.", default=5),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "models": sdk.array_field("Matching models.", items=sdk.string_field("Item.")),
                    },
                ),
            )
            def search_models(
                self,
                task: str,
                min_downloads: int = 0,
                framework: str | None = None,
                sort_by: str = "downloads",
                top_k: int = 5,
            ) -> list[dict[str, Any]]:
                """Search HuggingFace models for a given task.

                Args:
                    task: HF pipeline tag.
                    min_downloads: Minimum download count filter.
                    framework: Optional framework filter.
                    sort_by: One of 'downloads', 'likes', 'trending'.
                    top_k: Maximum number of results.

                Returns:
                    List of model metadata dicts.
                """
                return self._hf.search_models(
                    task=task,
                    min_downloads=min_downloads,
                    framework=framework,
                    sort_by=sort_by,
                    top_k=top_k,
                )

            @sdk.tool(
                name="list_tasks",
                description="List all available HuggingFace task types.",
            )
            @sdk.node(
                name="hf_recommender.list_tasks",
                description="List all available HF task types.",
                category="hf_recommender",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(properties={}),
                output_schema=sdk.output_object(
                    properties={
                        "tasks": sdk.array_field("List of task names.", items=sdk.string_field("Item.")),
                    },
                ),
            )
            def list_tasks(self) -> list[str]:
                """Return all available HF task types."""
                return self._hf.list_tasks()

            @sdk.tool(
                name="get_model_info",
                description="Get metadata for a specific HF model by id.",
            )
            @sdk.node(
                name="hf_recommender.get_model_info",
                description="Get metadata for a specific HF model.",
                category="hf_recommender",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "model_id": sdk.string_field(
                            "HF model id (e.g. 'gpt2', 'mistralai/Mistral-7B-v0.1')."
                        ),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "model": sdk.object_field("Model metadata, or null.", properties={}),
                    },
                ),
            )
            def get_model_info(self, model_id: str) -> dict[str, Any] | None:
                """Get metadata for a specific HF model by id.

                Returns:
                    Dict with model metadata, or None if not found.
                """
                return self._hf.get_model_info(model_id)

        return [HfRecommenderPlugin()]

    def warm_up(self) -> None:
        """Optional: validate the 3rd-party library is loadable."""
        try:
            self.add_cloned_to_sys_path()
            import hf_recommender_lib as hf

            n_tasks = len(hf.list_tasks())
            n_models = sum(len(v) for v in hf.HF_MODEL_CATALOG.values())
            self.log(f"warm_up: catalog loaded ({n_tasks} tasks, {n_models} models)")
        except Exception as e:
            raise RuntimeError(f"hf_recommender warm_up failed: {e}")

    def dispose(self) -> None:
        self.log("dispose: no-op (in-process state)")
