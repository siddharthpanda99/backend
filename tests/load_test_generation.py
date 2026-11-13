#!/usr/bin/env python3
"""Load test for the Character Studio generation endpoints.

Hits a *live* backend (default http://localhost:8000) with configurable
concurrency. Generation is GPU-bound — this tool is for measuring
queueing/throughput behaviour of the job API, not raw inference speed.

Usage:
    python tests/load_test_generation.py \
        --base-url http://localhost:8000 \
        --concurrency 4 --duration 30 \
        --character-id <existing-character-id>

    # cheap smoke of the read path only (no generation submitted)
    python tests/load_test_generation.py --read-only --concurrency 20

Reports: requests/s, latency p50/p95/p99, error rate, job submission
success rate. NOT a pytest module — run standalone.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import Counter

import httpx

API = "/api/v1/character-studio"


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(pct / 100.0 * (len(ordered) - 1))))
    return ordered[idx]


class LoadStats:
    def __init__(self) -> None:
        self.latencies: list[float] = []
        self.status: Counter[int] = Counter()
        self.errors: Counter[str] = Counter()
        self.submitted_jobs: list[str] = []
        self.started = time.time()

    def record(self, resp: httpx.Response, latency_s: float) -> None:
        self.latencies.append(latency_s)
        self.status[resp.status_code] += 1

    def record_error(self, exc: Exception) -> None:
        self.errors[exc.__class__.__name__] += 1

    def report(self) -> str:
        elapsed = time.time() - self.started
        total = len(self.latencies) + sum(self.errors.values())
        p50 = _percentile(self.latencies, 50)
        p95 = _percentile(self.latencies, 95)
        p99 = _percentile(self.latencies, 99)
        avg = statistics.mean(self.latencies) if self.latencies else 0.0
        lines = [
            "=" * 60,
            "Character Studio generation load test",
            "=" * 60,
            f"elapsed:            {elapsed:.1f}s",
            f"total requests:     {total}",
            f"throughput:         {total / elapsed:.2f} req/s" if elapsed else "n/a",
            f"statuses:           {dict(self.status)}",
            f"errors:             {dict(self.errors) if self.errors else 'none'}",
            f"latency avg:        {avg * 1000:.1f} ms",
            f"latency p50:        {p50 * 1000:.1f} ms",
            f"latency p95:        {p95 * 1000:.1f} ms",
            f"latency p99:        {p99 * 1000:.1f} ms",
            f"jobs submitted:     {len(self.submitted_jobs)}",
        ]
        return "\n".join(lines)


async def _worker_read_only(
    client: httpx.AsyncClient, stats: LoadStats, deadline: float
) -> None:
    while time.time() < deadline:
        t0 = time.perf_counter()
        try:
            resp = await client.get(f"{API}/health", timeout=10.0)
            stats.record(resp, time.perf_counter() - t0)
        except httpx.HTTPError as exc:
            stats.record_error(exc)


async def _worker_generate(
    client: httpx.AsyncClient, stats: LoadStats, character_id: str, deadline: float
) -> None:
    while time.time() < deadline:
        t0 = time.perf_counter()
        try:
            resp = await client.post(
                f"{API}/characters/{character_id}/generate",
                json={
                    "intent": "load_test",
                    "provider": "sd15",
                    "steps": 1,
                    "cfg": 1.0,
                    "seed": 42,
                },
                timeout=30.0,
            )
            stats.record(resp, time.perf_counter() - t0)
            if resp.status_code in (200, 201, 202):
                body = resp.json()
                job_id = body.get("job_id")
                if job_id:
                    stats.submitted_jobs.append(job_id)
        except httpx.HTTPError as exc:
            stats.record_error(exc)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--duration", type=int, default=30, help="seconds")
    parser.add_argument(
        "--character-id", default=None, help="required unless --read-only"
    )
    parser.add_argument(
        "--read-only", action="store_true", help="load the health/read path only"
    )
    args = parser.parse_args()

    if not args.read_only and not args.character_id:
        parser.error("--character-id is required unless --read-only")

    deadline = time.time() + args.duration
    stats = LoadStats()

    async with httpx.AsyncClient(base_url=args.base_url) as client:
        if args.read_only:
            workers = [
                _worker_read_only(client, stats, deadline)
                for _ in range(args.concurrency)
            ]
        else:
            workers = [
                _worker_generate(client, stats, args.character_id, deadline)
                for _ in range(args.concurrency)
            ]
        await asyncio.gather(*workers)

    print(stats.report())


if __name__ == "__main__":
    asyncio.run(main())
