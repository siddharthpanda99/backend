"""Data Analytics Toolkit Panel.

Reuses the data_analytics_toolkit plugin's adapter. The panel
drives the plugin's 6 tools (describe_series, detect_outliers,
correlation, linear_regression, value_counts, top_n) through a
single form that lets the user:

  - Paste a CSV-like list of numbers
  - Pick which analysis to run (descriptive, outliers, etc.)
  - See the result as a table + summary + optional chart

This reuses the same pattern as the HF recommender panel:
the panel only knows about ``self.plugin`` (the BaseToolPlugin
instance the adapter built). The 3rd-party code stays untouched
in ``cloned_or_extracted_repo/``.
"""

from __future__ import annotations

import statistics
from typing import Any

from common_lib.modules.plugin_sdk.panels import BasePanel


def _parse_numbers(s: str) -> list[float]:
    """Parse a free-form string of numbers (comma, space, newline)."""
    out: list[float] = []
    for token in s.replace("\n", ",").replace("\t", ",").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            out.append(float(token))
        except ValueError:
            continue
    return out


class DataAnalyticsPanel(BasePanel):
    """Demo panel for the data analytics plugin."""

    id = "data_analytics_toolkit"
    title = "Data Analytics Toolkit"
    description = (
        "Quick stats, outlier detection, correlation, and OLS "
        "regression on numeric data. Paste a list of numbers."
    )
    version = "1.0.0"
    icon = "FiActivity"
    category = "analytics"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "title": "Analyze Numeric Data",
            "description": (
                "Paste a comma- or newline-separated list of numbers, "
                "pick an analysis, and see results."
            ),
            "properties": {
                "values": {
                    "type": "string",
                    "title": "Values",
                    "description": "Comma- or newline-separated numbers",
                    "default": "1, 2, 3, 4, 5, 6, 7, 8, 9, 10",
                },
                "analysis": {
                    "type": "string",
                    "title": "Analysis",
                    "enum": [
                        "describe",
                        "outliers",
                        "correlation",
                        "regression",
                    ],
                    "default": "describe",
                },
                "y_values": {
                    "type": "string",
                    "title": "Y values (for correlation/regression)",
                    "default": "2, 4, 6, 8, 10, 12, 14, 16, 18, 20",
                    "description": "Required only for correlation / regression",
                },
                "outlier_threshold": {
                    "type": "number",
                    "title": "Outlier z-score threshold",
                    "default": 2.5,
                },
            },
            "required": ["values", "analysis"],
        }

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.plugin is None:
            return {"error": "Plugin not bound", "rows": []}

        values = _parse_numbers(payload.get("values", ""))
        analysis = payload.get("analysis", "describe")
        threshold = float(payload.get("outlier_threshold", 2.5))

        if not values:
            return {
                "error": "No numeric values parsed from input",
                "rows": [],
                "summary": "Parse 0 numbers — please check your input",
            }

        if analysis == "describe":
            stats = self.plugin.describe_series(values)
            rows = [{"metric": k, "value": v} for k, v in stats.items()]
            return {
                "rows": rows,
                "summary": f"Descriptive stats for {len(values)} values: mean={stats.get('mean', 0):.2f}, sd={stats.get('stddev', 0):.2f}",
                "meta": {"analysis": "describe", "n": stats.get("n")},
            }

        if analysis == "outliers":
            res = self.plugin.detect_outliers(values, threshold=threshold)
            rows = [
                {"index": i, "value": v} for i, v in zip(res["indices"], res["values"])
            ]
            chart = None
            if values:
                chart = {
                    "type": "scatter",
                    "title": f"Outliers (z>{threshold}): {res['count']} of {len(values)}",
                    "x_label": "Index",
                    "y_label": "Value",
                    "data": [
                        {"x": i, "y": v, "is_outlier": i in res["indices"]}
                        for i, v in enumerate(values)
                    ],
                }
            return {
                "rows": rows,
                "summary": f"{res['count']} outliers at z>{threshold} in {len(values)} values",
                "chart": chart,
                "meta": {"threshold": threshold, "n_outliers": res["count"]},
            }

        if analysis in ("correlation", "regression"):
            y = _parse_numbers(payload.get("y_values", ""))
            if len(y) != len(values):
                return {
                    "error": (
                        f"X and Y must have the same length "
                        f"(got {len(values)} and {len(y)})"
                    ),
                    "rows": [],
                }
            if analysis == "correlation":
                r = self.plugin.correlation(values, y)
                rows = [{"metric": "pearson_r", "value": r}]
                return {
                    "rows": rows,
                    "summary": f"Pearson r = {r:.4f} (n={len(values)})",
                    "meta": {"n": len(values)},
                }
            fit = self.plugin.linear_regression(values, y)
            rows = [
                {"parameter": "slope", "value": fit["slope"]},
                {"parameter": "intercept", "value": fit["intercept"]},
                {"parameter": "r_squared", "value": fit["r_squared"]},
            ]
            chart = {
                "type": "scatter_with_line",
                "title": f"y = {fit['slope']:.3f}*x + {fit['intercept']:.3f} (R²={fit['r_squared']:.3f})",
                "x_label": "x",
                "y_label": "y",
                "data": [{"x": xi, "y": yi} for xi, yi in zip(values, y)],
                "line": {
                    "slope": fit["slope"],
                    "intercept": fit["intercept"],
                },
            }
            return {
                "rows": rows,
                "summary": f"OLS fit: y = {fit['slope']:.3f}x + {fit['intercept']:.3f} (R²={fit['r_squared']:.3f})",
                "chart": chart,
                "meta": fit,
            }

        return {"error": f"Unknown analysis: {analysis!r}", "rows": []}


PANEL_CLASS = DataAnalyticsPanel
