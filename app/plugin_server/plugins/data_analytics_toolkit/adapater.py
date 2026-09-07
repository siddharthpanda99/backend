"""Adapter for data_analytics_toolkit — wraps the 3rd-party
analytics library into a BaseToolPlugin.

The 3rd-party code in `cloned_or_extracted_repo/` is untouched.
"""

from __future__ import annotations

import logging
from typing import Any

from common_lib.modules.plugin_sdk.runtime.adapter_base import BaseAdapter
from common_lib.modules.plugins.base import BaseToolPlugin
from common_lib.modules.plugins.schemas import PluginMetadata

logger = logging.getLogger(__name__)


class DataAnalyticsAdapter(BaseAdapter):
    """Adapter for the 3rd-party data analytics library."""

    def discover(self) -> list[BaseToolPlugin]:

     # Universal deepseek-style lifecycle applied to this plugin
        # Universal deepseek-style lifecycle
        from app.plugin_server.panels import PluginLifecycle, PluginPhase, PluginCapability
        self.lifecycle = PluginLifecycle(
            plugin_id="data_analytics_toolkit",
            phases=[
                PluginPhase("init", "Initialize stats engine"),
                PluginPhase("ready", "Ready to analyze"),
            ],
            capabilities=[
                PluginCapability("describe", "Compute summary stats", requires_auth=False),
                PluginCapability("outliers", "Detect outliers", requires_auth=False),
                PluginCapability("fit", "Fit OLS regression", requires_auth=False),
            ],
            model_invocable=True,
            user_invocable=True,
            health_check_interval_sec=60.0,
        )

        self.add_cloned_to_sys_path()
        self.add_cloned_to_sys_path()
        try:
            import analytics_lib as al
        except ImportError as e:
            raise ImportError(
                f"data_analytics_toolkit: failed to import 3rd-party library: {e}"
            ) from e

        metadata = PluginMetadata(
            id="data_analytics_toolkit",
            name="Data Analytics Toolkit",
            version="1.0.0",
            description=(
                "Statistical and analytical functions: descriptive stats, "
                "outlier detection, correlation, linear regression, "
                "value counts, top-N."
            ),
            category="analytics",
            author="3rd-party (data_analytics_toolkit.zip)",
            tags=["analytics", "statistics", "data", "third-party"],
            dependencies=[],
            required_keys=[],
        )

        from common_lib.modules import plugin_sdk as sdk

        class DataAnalyticsPlugin(BaseToolPlugin):
            def __init__(self):
                self.metadata = metadata
                self._al = al

            def check_health(self):
                from common_lib.modules.plugins.schemas import (
                    HealthStatus,
                    PluginHealth,
                )

                return PluginHealth(
                    status=HealthStatus.HEALTHY,
                    message="OK (pure-stdlib analytics, no deps)",
                )

            def get_nodes(self):
                return [
                    {
                        "name": "data_analytics_toolkit.describe_series",
                        "entity_type": "tool",
                        "description": "Descriptive statistics for a numeric series.",
                    },
                    {
                        "name": "data_analytics_toolkit.detect_outliers",
                        "entity_type": "tool",
                        "description": "Detect outliers via z-score.",
                    },
                    {
                        "name": "data_analytics_toolkit.correlation",
                        "entity_type": "tool",
                        "description": "Pearson correlation between two series.",
                    },
                    {
                        "name": "data_analytics_toolkit.linear_regression",
                        "entity_type": "tool",
                        "description": "Fit y = m*x + b via OLS.",
                    },
                    {
                        "name": "data_analytics_toolkit.value_counts",
                        "entity_type": "tool",
                        "description": "Count occurrences of each unique value.",
                    },
                    {
                        "name": "data_analytics_toolkit.top_n",
                        "entity_type": "tool",
                        "description": "Top-N keys of a counter.",
                    },
                ]

            @sdk.tool(
                name="describe_series",
                description=(
                    "Compute descriptive statistics (n, min, max, mean, "
                    "median, stddev, sum) for a numeric series."
                ),
            )
            @sdk.node(
                name="data_analytics_toolkit.describe_series",
                description="Descriptive statistics for a numeric series.",
                category="data_analytics_toolkit",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "values": sdk.array_field("Numeric series.", items=sdk.string_field("Item.")),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "stats": sdk.object_field("Dict of descriptive stats.", properties={}),
                    },
                ),
            )
            def describe_series(self, values: list[float]) -> dict[str, float]:
                return self._al.describe_series(values)

            @sdk.tool(
                name="detect_outliers",
                description="Detect outliers in a numeric series using z-score.",
            )
            @sdk.node(
                name="data_analytics_toolkit.detect_outliers",
                description="Detect outliers via z-score.",
                category="data_analytics_toolkit",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "values": sdk.array_field("Numeric series.", items=sdk.string_field("Item.")),
                        "threshold": sdk.number_field(
                            "Z-score threshold.", default=2.5
                        ),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "outliers": sdk.object_field("Dict of outliers.", properties={}),
                    },
                ),
            )
            def detect_outliers(
                self, values: list[float], threshold: float = 2.5
            ) -> dict[str, Any]:
                return self._al.detect_outliers_zscore(values, threshold=threshold)

            @sdk.tool(
                name="correlation",
                description="Pearson correlation between two numeric series.",
            )
            @sdk.node(
                name="data_analytics_toolkit.correlation",
                description="Pearson correlation between two series.",
                category="data_analytics_toolkit",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "x": sdk.array_field("First series.", items=sdk.string_field("Item.")),
                        "y": sdk.array_field("Second series.", items=sdk.string_field("Item.")),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "r": sdk.number_field("Pearson r in [-1, 1]."),
                    },
                ),
            )
            def correlation(self, x: list[float], y: list[float]) -> float:
                return self._al.correlation(x, y)

            @sdk.tool(
                name="linear_regression",
                description="Fit y = m*x + b via OLS, return slope/intercept/R^2.",
            )
            @sdk.node(
                name="data_analytics_toolkit.linear_regression",
                description="Fit y = m*x + b via OLS.",
                category="data_analytics_toolkit",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "x": sdk.array_field("Predictor values.", items=sdk.string_field("Item.")),
                        "y": sdk.array_field("Response values.", items=sdk.string_field("Item.")),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "fit": sdk.object_field("slope, intercept, r_squared.", properties={}),
                    },
                ),
            )
            def linear_regression(
                self, x: list[float], y: list[float]
            ) -> dict[str, float]:
                return self._al.linear_regression(x, y)

            @sdk.tool(
                name="value_counts",
                description="Count occurrences of each unique value in a list.",
            )
            @sdk.node(
                name="data_analytics_toolkit.value_counts",
                description="Count occurrences of each unique value.",
                category="data_analytics_toolkit",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "values": sdk.array_field("List of values.", items=sdk.string_field("Item.")),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "counts": sdk.object_field("Dict of value -> count.", properties={}),
                    },
                ),
            )
            def value_counts(self, values: list[str]) -> dict[str, int]:
                return self._al.value_counts(values)

            @sdk.tool(
                name="top_n",
                description="Return the top-N keys of a counter, sorted by count.",
            )
            @sdk.node(
                name="data_analytics_toolkit.top_n",
                description="Top-N keys of a counter.",
                category="data_analytics_toolkit",
                audience=["planner", "executor"],
                input_schema=sdk.input_object(
                    properties={
                        "counter": sdk.object_field("Dict of value -> count.", properties={}),
                        "n": sdk.number_field("Top-N.", default=5),
                    },
                ),
                output_schema=sdk.output_object(
                    properties={
                        "top": sdk.array_field("List of {key, count}.", items=sdk.string_field("Item.")),
                    },
                ),
            )
            def top_n(
                self, counter: dict[str, int], n: int = 5
            ) -> list[dict[str, Any]]:
                return self._al.top_n(counter, n)

        return [DataAnalyticsPlugin()]

    def warm_up(self) -> None:
        self.add_cloned_to_sys_path()
        import analytics_lib as al

        # Smoke-test
        result = al.describe_series([1.0, 2.0, 3.0, 4.0, 5.0])
        if result["n"] != 5:
            raise RuntimeError(f"warm_up smoke test failed: {result}")
        self.log(f"warm_up: OK (smoke test n=5)")

    def dispose(self) -> None:
        self.log("dispose: no-op")
