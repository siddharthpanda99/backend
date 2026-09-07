"""HuggingFace Recommender Panel.

Reuses the hf_recommender plugin's adapter. The panel drives the
plugin's `search_models`, `list_tasks`, and `get_model_info` tools
through a pre-built form, so the user can:
  - See all available HF task types
  - Search models for a task with filters
  - Pick a model and see its details

The panel returns data in a structured "rows" format that the
React frontend renders as a table + summary + chart.
"""

from __future__ import annotations

from typing import Any

from common_lib.modules.plugin_sdk.panels import BasePanel


class HfRecommenderPanel(BasePanel):
    """Demo panel for the HuggingFace model recommender plugin."""

    id = "hf_recommender"
    title = "HuggingFace Model Recommender"
    description = (
        "Browse HuggingFace models for any task. "
        "Search by task type, framework, popularity."
    )
    version = "1.0.0"
    icon = "FiBox"
    category = "ai"

    def schema(self) -> dict[str, Any]:
        # Get the available tasks from the plugin if it's bound
        task_enum = [
            "text-generation",
            "text-classification",
            "translation",
            "summarization",
            "image-classification",
        ]
        try:
            if self.plugin is not None and hasattr(self.plugin, "list_tasks"):
                task_enum = self.plugin.list_tasks() or task_enum
        except Exception:
            pass

        return {
            "type": "object",
            "title": "Search HuggingFace Models",
            "description": "Find models on HuggingFace Hub for any task.",
            "properties": {
                "task": {
                    "type": "string",
                    "title": "Task",
                    "enum": task_enum,
                    "default": task_enum[0] if task_enum else "text-generation",
                },
                "framework": {
                    "type": "string",
                    "title": "Framework (optional)",
                    "enum": ["", "pytorch", "transformers", "gguf", "tensorflow"],
                    "default": "",
                },
                "min_downloads": {
                    "type": "integer",
                    "title": "Min Downloads",
                    "default": 0,
                    "minimum": 0,
                },
                "sort_by": {
                    "type": "string",
                    "title": "Sort By",
                    "enum": ["downloads", "likes", "trending"],
                    "default": "downloads",
                },
                "top_k": {
                    "type": "integer",
                    "title": "Max Results",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["task"],
        }

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.plugin is None:
            return {"error": "Plugin not bound", "rows": []}

        # Call the plugin's tool — this is the same code path the
        # agentic loop uses. The adapter wraps the 3rd-party call.
        results = self.plugin.search_models(
            task=payload["task"],
            min_downloads=payload.get("min_downloads", 0),
            framework=payload.get("framework") or None,
            sort_by=payload.get("sort_by", "downloads"),
            top_k=payload.get("top_k", 5),
        )

        # Render as a table with the columns the UI expects
        rows = [
            {
                "id": m.get("id"),
                "description": m.get("description"),
                "params": m.get("params"),
                "downloads": m.get("downloads", 0),
                "likes": m.get("likes", 0),
                "tags": ", ".join(m.get("tags", [])),
            }
            for m in results
        ]

        # Build a tiny chart spec: downloads by model
        chart = None
        if rows:
            chart = {
                "type": "bar",
                "title": f"Top {len(rows)} models for {payload['task']} (by downloads)",
                "x_label": "Model",
                "y_label": "Downloads",
                "data": [{"x": r["id"], "y": r["downloads"]} for r in rows],
            }

        return {
            "rows": rows,
            "summary": (
                f"Found {len(rows)} HuggingFace models for task "
                f"'{payload['task']}'"
                + (
                    f" (framework: {payload['framework']})"
                    if payload.get("framework")
                    else ""
                )
                + "."
            ),
            "chart": chart,
            "meta": {
                "task": payload.get("task"),
                "framework": payload.get("framework"),
                "sort_by": payload.get("sort_by", "downloads"),
            },
        }


PANEL_CLASS = HfRecommenderPanel
