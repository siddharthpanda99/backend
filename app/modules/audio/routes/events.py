"""SSE event type definitions and helpers (C082 — W8-L06).

Shared event types for TTS streaming and other async operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import json


class SSEEventType(str, Enum):
    """Standard SSE event types for audio operations."""

    # Lifecycle
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    # Audio-specific
    CHUNK_READY = "chunk_ready"
    METADATA = "metadata"
    ERROR = "error"

    # Heartbeat
    HEARTBEAT = "heartbeat"


@dataclass
class SSEEvent:
    """Structured SSE event."""

    event: SSEEventType
    data: Dict[str, Any]
    id: Optional[str] = None
    retry: Optional[int] = None  # milliseconds

    def to_sse(self) -> str:
        """Encode as SSE format string."""
        lines = []
        if self.id:
            lines.append(f"id: {self.id}")
        if self.retry:
            lines.append(f"retry: {self.retry}")
        lines.append(f"event: {self.event.value}")
        lines.append(f"data: {json.dumps(self.data)}")
        return "\n".join(lines) + "\n\n"

    @classmethod
    def progress(
        cls, job_id: str, progress: float, status: str = "running"
    ) -> "SSEEvent":
        return cls(
            event=SSEEventType.PROGRESS,
            data={"job_id": job_id, "progress": progress, "status": status},
        )

    @classmethod
    def completed(
        cls, job_id: str, result: Optional[Dict[str, Any]] = None
    ) -> "SSEEvent":
        data = {"job_id": job_id, "status": "completed"}
        if result:
            data["result"] = result
        return cls(event=SSEEventType.COMPLETED, data=data)

    @classmethod
    def failed(cls, job_id: str, error: str) -> "SSEEvent":
        return cls(
            event=SSEEventType.FAILED,
            data={"job_id": job_id, "status": "failed", "error": error},
        )

    @classmethod
    def cancelled(cls, job_id: str) -> "SSEEvent":
        return cls(
            event=SSEEventType.CANCELLED,
            data={"job_id": job_id, "status": "cancelled"},
        )

    @classmethod
    def started(cls, job_id: str) -> "SSEEvent":
        return cls(
            event=SSEEventType.STARTED,
            data={"job_id": job_id, "status": "started"},
        )

    @classmethod
    def chunk_ready(cls, job_id: str, chunk_index: int, size: int) -> "SSEEvent":
        return cls(
            event=SSEEventType.CHUNK_READY,
            data={"job_id": job_id, "chunk_index": chunk_index, "size": size},
        )

    @classmethod
    def metadata(cls, job_id: str, metadata: Dict[str, Any]) -> "SSEEvent":
        return cls(
            event=SSEEventType.METADATA,
            data={"job_id": job_id, "metadata": metadata},
        )

    @classmethod
    def heartbeat(cls) -> "SSEEvent":
        return cls(
            event=SSEEventType.HEARTBEAT,
            data={"timestamp": datetime.utcnow().isoformat()},
        )


class SSEEncoder:
    """Helper to encode events for StreamingResponse."""

    @staticmethod
    def encode(event: SSEEvent) -> str:
        return event.to_sse()

    @staticmethod
    def encode_batch(events: list[SSEEvent]) -> str:
        return "".join(e.to_sse() for e in events)


def create_sse_stream(generator):
    """Wrap an async generator of SSEEvent into an SSE string generator."""

    async def _gen():
        async for event in generator:
            yield event.to_sse()

    return _gen()


# Common event schemas for OpenAPI documentation
SSE_EVENT_SCHEMAS = {
    "started": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "status": {"type": "string", "enum": ["started"]},
        },
    },
    "progress": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "progress": {"type": "number", "minimum": 0, "maximum": 1},
            "status": {"type": "string"},
        },
    },
    "completed": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "status": {"type": "string", "enum": ["completed"]},
            "result": {"type": "object"},
        },
    },
    "failed": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "status": {"type": "string", "enum": ["failed"]},
            "error": {"type": "string"},
        },
    },
    "cancelled": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "status": {"type": "string", "enum": ["cancelled"]},
        },
    },
    "chunk_ready": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "chunk_index": {"type": "integer"},
            "size": {"type": "integer"},
        },
    },
    "metadata": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "metadata": {"type": "object"},
        },
    },
    "heartbeat": {
        "type": "object",
        "properties": {
            "timestamp": {"type": "string", "format": "date-time"},
        },
    },
}


__all__ = [
    "SSEEventType",
    "SSEEvent",
    "SSEEncoder",
    "create_sse_stream",
    "SSE_EVENT_SCHEMAS",
]
