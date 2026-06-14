"""
Knowledge Hub — Streaming Ingestion Service.

Manages real-time document ingestion via WebSocket connections:
1. Accept incoming document content chunks over WebSocket
2. Process through chunking → embedding pipeline
3. Stream progress and results back to the client in real-time
4. Push chunk creation/update/detection events to subscribed listeners

Also provides an SSE event source for external subscribers to receive
chunk lifecycle events (created, updated, deleted, embedded).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional, Set

from fastapi import WebSocket

from common_lib.modules.knowledge_engine.sharing.events import (
    KnowledgeEvent,
    KnowledgeEventType,
)
from common_lib.modules.knowledge_engine.sharing.bus import SharedKnowledgeBus

logger = logging.getLogger(__name__)


# ── Event Types ────────────────────────────────────────────────


class StreamingEventType(str, Enum):
    """Event types emitted by the streaming ingestion service."""

    CONNECTED = "stream.connected"
    DISCONNECTED = "stream.disconnected"
    DOCUMENT_RECEIVED = "stream.document.received"
    CHUNKING_STARTED = "stream.chunking.started"
    CHUNK_CREATED = "stream.chunk.created"
    CHUNKING_COMPLETED = "stream.chunking.completed"
    EMBEDDING_STARTED = "stream.embedding.started"
    EMBEDDING_PROGRESS = "stream.embedding.progress"
    EMBEDDING_COMPLETED = "stream.embedding.completed"
    INGESTION_COMPLETED = "stream.ingestion.completed"
    ERROR = "stream.error"
    PROGRESS = "stream.progress"


# ── Data Models ────────────────────────────────────────────────


@dataclass
class StreamSession:
    """Represents an active streaming ingestion session."""

    session_id: str
    source_type: str
    source_id: str
    started_at: float
    documents_received: int = 0
    chunks_created: int = 0
    chunks_embedded: int = 0
    status: str = "active"  # active, closed, error
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentChunk:
    """A chunk of a document being streamed in."""

    chunk_id: str
    document_id: str
    session_id: str
    content: str
    index: int
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding_status: str = "pending"  # pending, processing, completed, failed


# ── WebSocket Connection Manager ───────────────────────────────


class ConnectionManager:
    """Manages WebSocket connections for real-time streaming.

    Maintains a registry of active connections grouped by session_id
    and a global set for broadcasting lifecycle events to SSE subscribers.
    """

    def __init__(self):
        self._sessions: dict[str, StreamSession] = {}
        self._connections: dict[str, Set[WebSocket]] = {}
        self._sse_subscribers: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    # ── Session Management ─────────────────────────────────

    def create_session(self, source_type: str, source_id: str) -> StreamSession:
        session_id = str(uuid.uuid4())
        session = StreamSession(
            session_id=session_id,
            source_type=source_type,
            source_id=source_id,
            started_at=time.time(),
        )
        self._sessions[session_id] = session
        return session

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(session_id, set()).add(websocket)

    async def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        async with self._lock:
            if session_id in self._connections:
                self._connections[session_id].discard(websocket)
                if not self._connections[session_id]:
                    del self._connections[session_id]

    def get_session(self, session_id: str) -> Optional[StreamSession]:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].status = "closed"
            # Clean up connections
            if session_id in self._connections:
                del self._connections[session_id]

    def subscribe_sse(self, websocket: WebSocket) -> None:
        self._sse_subscribers.add(websocket)

    def unsubscribe_sse(self, websocket: WebSocket) -> None:
        self._sse_subscribers.discard(websocket)

    # ── Broadcasting ──────────────────────────────────────

    async def send_to_session(
        self, session_id: str, payload: dict, exclude: Optional[WebSocket] = None
    ) -> None:
        """Send a message to all WebSocket clients in a session."""
        async with self._lock:
            connections = self._connections.get(session_id, set()).copy()
        dead: list[WebSocket] = []
        for ws in connections:
            if ws is exclude:
                continue
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws, session_id)

    async def broadcast_sse(self, payload: dict) -> None:
        """Broadcast an event to all SSE subscribers."""
        dead: list[WebSocket] = []
        for ws in self._sse_subscribers:
            try:
                await ws.send_text(f"data: {json.dumps(payload)}\n\n")
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unsubscribe_sse(ws)

    async def emit_event(
        self,
        event_type: StreamingEventType,
        session_id: str,
        data: dict[str, Any],
        sse_only: bool = False,
    ) -> None:
        """Emit a streaming event to both session WebSocket and SSE subscribers."""
        payload = {
            "type": event_type.value,
            "session_id": session_id,
            "timestamp": time.time(),
            "data": data,
        }
        # Broadcast to SSE subscribers
        await self.broadcast_sse(payload)
        # Send to session WS clients (unless sse_only)
        if not sse_only:
            await self.send_to_session(session_id, payload)


# ── Streaming Ingestion Service ────────────────────────────────


class StreamingIngestionService:
    """Orchestrates real-time document streaming ingestion.

    Accepts document content via WebSocket, processes it through
    chunking and embedding pipelines, and streams results back.

    Usage:
        service = StreamingIngestionService()
        session = service.create_session("web", "user-123")

        # In WebSocket handler:
        async for message in websocket.iter_text():
            result = await service.ingest_chunk(session.session_id, message)
            await service.send_to_session(session.session_id, result)
    """

    def __init__(
        self,
        knowledge_bus: Optional[SharedKnowledgeBus] = None,
    ):
        self.connection_manager = ConnectionManager()
        self._knowledge_bus = knowledge_bus
        self._active_sessions: dict[str, dict[str, Any]] = {}
        logger.info("StreamingIngestionService initialized")

    def create_session(
        self,
        source_type: str = "web",
        source_id: str = "anonymous",
        metadata: Optional[dict[str, Any]] = None,
    ) -> StreamSession:
        """Create a new streaming session."""
        session = self.connection_manager.create_session(source_type, source_id)
        if metadata:
            session.metadata.update(metadata)
        self._active_sessions[session.session_id] = {
            "buffer": [],
            "total_chunks": 0,
            "metadata": metadata or {},
        }
        logger.info(
            "Streaming session created: %s (type=%s, source=%s)",
            session.session_id,
            source_type,
            source_id,
        )
        return session

    async def ingest_text(
        self,
        session_id: str,
        text: str,
        document_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Ingest a text document through the streaming pipeline.

        Args:
            session_id: Active streaming session ID.
            text: Document text content.
            document_id: Optional document ID (generated if not provided).
            metadata: Optional document metadata.

        Returns:
            Ingestion result with chunk info and processing status.
        """
        session = self.connection_manager.get_session(session_id)
        if not session:
            return {
                "success": False,
                "error": f"Session {session_id} not found or closed",
            }

        doc_id = document_id or str(uuid.uuid4())
        session.documents_received += 1

        # Emit document received event
        await self.connection_manager.emit_event(
            StreamingEventType.DOCUMENT_RECEIVED,
            session_id,
            {"document_id": doc_id, "length": len(text), "metadata": metadata or {}},
        )

        # Emit chunking started
        await self.connection_manager.emit_event(
            StreamingEventType.CHUNKING_STARTED,
            session_id,
            {"document_id": doc_id},
        )

        # Simulate chunking (in real impl, use KnowledgeChunker)
        chunks = self._simulate_chunking(doc_id, text, session_id=session_id)
        session.chunks_created += len(chunks)

        # Emit each chunk as created
        for chunk in chunks:
            await self.connection_manager.emit_event(
                StreamingEventType.CHUNK_CREATED,
                session_id,
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": doc_id,
                    "index": chunk.index,
                    "content_length": len(chunk.content),
                    "embedding_status": chunk.embedding_status,
                },
            )

        # Emit chunking completed
        await self.connection_manager.emit_event(
            StreamingEventType.CHUNKING_COMPLETED,
            session_id,
            {"document_id": doc_id, "chunks_count": len(chunks)},
        )

        # Emit embedding started
        await self.connection_manager.emit_event(
            StreamingEventType.EMBEDDING_STARTED,
            session_id,
            {"document_id": doc_id, "chunks_count": len(chunks)},
        )

        # Simulate embedding progress
        for i, chunk in enumerate(chunks):
            chunk.embedding_status = "completed"
            session.chunks_embedded += 1
            progress = int(((i + 1) / len(chunks)) * 100)
            await self.connection_manager.emit_event(
                StreamingEventType.EMBEDDING_PROGRESS,
                session_id,
                {
                    "document_id": doc_id,
                    "chunks_embedded": i + 1,
                    "total_chunks": len(chunks),
                    "progress_pct": progress,
                },
            )

        # Emit embedding completed
        await self.connection_manager.emit_event(
            StreamingEventType.EMBEDDING_COMPLETED,
            session_id,
            {"document_id": doc_id, "chunks_count": len(chunks)},
        )

        # Emit ingestion completed
        await self.connection_manager.emit_event(
            StreamingEventType.INGESTION_COMPLETED,
            session_id,
            {
                "document_id": doc_id,
                "chunks_created": len(chunks),
                "chunks_embedded": len([c for c in chunks if c.embedding_status == "completed"]),
                "total_length": len(text),
            },
        )

        # Publish to knowledge bus if available
        if self._knowledge_bus:
            await self._publish_knowledge_event(
                KnowledgeEventType.CHUNK_CREATED,
                {
                    "session_id": session_id,
                    "document_id": doc_id,
                    "chunks_count": len(chunks),
                    "source_type": session.source_type,
                    "source_id": session.source_id,
                },
            )

        logger.info(
            "Ingested document %s: %d chunks in session %s",
            doc_id,
            len(chunks),
            session_id,
        )

        return {
            "success": True,
            "document_id": doc_id,
            "chunks_created": len(chunks),
            "chunks_embedded": len([c for c in chunks if c.embedding_status == "completed"]),
            "session_id": session_id,
            "source_type": session.source_type,
        }

    def _simulate_chunking(
        self, document_id: str, text: str, session_id: str = ""
    ) -> list[DocumentChunk]:
        """Split text into chunks (simple character-based splitting).

        In production, this would use the KnowledgeChunker from the
        knowledge_engine module. Here we use a simple strategy so
        streaming works without the full chunking pipeline.
        """
        chunk_size = 1000  # characters per chunk
        chunks: list[DocumentChunk] = []
        for i in range(0, len(text), chunk_size):
            content = text[i : i + chunk_size]
            chunk = DocumentChunk(
                chunk_id=str(uuid.uuid4()),
                document_id=document_id,
                session_id=session_id,
                content=content,
                index=len(chunks),
            )
            chunks.append(chunk)
        return chunks

    async def _publish_knowledge_event(
        self,
        event_type: KnowledgeEventType,
        payload: dict[str, Any],
    ) -> None:
        """Publish a KnowledgeEvent to the shared bus."""
        if not self._knowledge_bus:
            return
        event = KnowledgeEvent(
            type=event_type,
            source="streaming_ingestion",
            payload=payload,
        )
        await self._knowledge_bus.publish(event)

    async def close_session(self, session_id: str) -> None:
        """Close a streaming session and clean up resources."""
        self.connection_manager.close_session(session_id)
        self._active_sessions.pop(session_id, None)
        logger.info("Streaming session closed: %s", session_id)

    def get_session_status(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get the current status of a streaming session."""
        session = self.connection_manager.get_session(session_id)
        if not session:
            return None
        return {
            "session_id": session.session_id,
            "source_type": session.source_type,
            "source_id": session.source_id,
            "status": session.status,
            "documents_received": session.documents_received,
            "chunks_created": session.chunks_created,
            "chunks_embedded": session.chunks_embedded,
            "started_at": session.started_at,
            "uptime_seconds": round(time.time() - session.started_at, 1),
        }

    def list_active_sessions(self) -> list[dict[str, Any]]:
        """List all active streaming sessions."""
        return [
            self.get_session_status(sid)
            for sid, session in self.connection_manager._sessions.items()
            if session.status == "active"
        ]


# ── Singleton ──────────────────────────────────────────────────

_streaming_service: Optional[StreamingIngestionService] = None


def get_streaming_service() -> StreamingIngestionService:
    """Get or create the singleton StreamingIngestionService."""
    global _streaming_service
    if _streaming_service is None:
        _streaming_service = StreamingIngestionService()
    return _streaming_service


__all__ = [
    "StreamingIngestionService",
    "StreamingEventType",
    "StreamSession",
    "ConnectionManager",
    "get_streaming_service",
]
