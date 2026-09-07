"""3rd-party data analytics library (untouched).

This is what extracting a .zip file from a vendor would produce.
The vendor wrote this without knowing about our platform.

We wrap it in our adapter with zero modifications.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from typing import Any


def describe_series(values: list[float]) -> dict[str, float]:
    """Return basic descriptive statistics for a numeric series.

    Args:
        values: A list of numeric values.

    Returns:
        Dict with n, min, max, mean, median, stddev, sum.
    """
    if not values:
        return {
            "n": 0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "stddev": 0.0,
            "sum": 0.0,
        }
    n = len(values)
    return {
        "n": n,
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stddev": statistics.stdev(values) if n > 1 else 0.0,
        "sum": sum(values),
    }


def detect_outliers_zscore(
    values: list[float],
    threshold: float = 2.5,
) -> dict[str, Any]:
    """Detect outliers using the z-score method.

    Args:
        values: Numeric series.
        threshold: Z-score threshold (default 2.5).

    Returns:
        Dict with 'count', 'indices' (positions in input), 'values'.
    """
    if len(values) < 2:
        return {"count": 0, "indices": [], "values": []}
    mean = statistics.mean(values)
    stddev = statistics.stdev(values)
    if stddev == 0:
        return {"count": 0, "indices": [], "values": []}
    indices = []
    out_values = []
    for i, v in enumerate(values):
        z = abs((v - mean) / stddev)
        if z > threshold:
            indices.append(i)
            out_values.append(v)
    return {"count": len(indices), "indices": indices, "values": out_values}


def correlation(x: list[float], y: list[float]) -> float:
    """Pearson correlation between two series. Returns 0.0 if degenerate."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    n = len(x)
    mx = statistics.mean(x)
    my = statistics.mean(y)
    sx = statistics.stdev(x)
    sy = statistics.stdev(y)
    if sx == 0 or sy == 0:
        return 0.0
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / (n - 1)
    return cov / (sx * sy)


def linear_regression(x: list[float], y: list[float]) -> dict[str, float]:
    """Fit y = slope * x + intercept via OLS.

    Returns:
        {"slope": m, "intercept": b, "r_squared": R^2}
    """
    n = len(x)
    if n != len(y) or n < 2:
        return {"slope": 0.0, "intercept": 0.0, "r_squared": 0.0}
    mx = statistics.mean(x)
    my = statistics.mean(y)
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx == 0:
        return {"slope": 0.0, "intercept": my, "r_squared": 0.0}
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    slope = sxy / sxx
    intercept = my - slope * mx
    # R^2
    ss_tot = sum((yi - my) ** 2 for yi in y)
    ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
    r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {"slope": slope, "intercept": intercept, "r_squared": r_sq}


def top_n(counter: dict[str, int], n: int = 5) -> list[dict[str, Any]]:
    """Return the top-N keys in a counter, sorted by count."""
    items = sorted(counter.items(), key=lambda kv: -kv[1])
    return [{"key": k, "count": v} for k, v in items[:n]]


def value_counts(values: list[str]) -> dict[str, int]:
    """Count occurrences of each unique value."""
    return dict(Counter(values))
