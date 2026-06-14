"""
Knowledge Hub — Streaming Ingestion Routes.

Provides real-time document ingestion via WebSocket and Server-Sent Events (SSE):

WebSocket:
    ws://host/api/v1/knowledge-hub/streaming/ws/{session_id}
    — Accepts JSON messages with document content, streams progress back.

SSE:
    GET /api/v1/knowledge-hub/streaming/events
    — Subscribes to chunk lifecycle events (created, updated, deleted, embedded).

REST:
    POST /api/v1/knowledge-hub/streaming/ingest
    — Ingest a text document and stream progress via SSE.
    GET  /api/v1/knowledge-hub/streaming/sessions
    — List active streaming sessions.
    GET  /api/v1/knowledge-hub/streaming/sessions/{session_id}
    — Get session status.
    POST /api/v1/knowledge-hub/streaming/sessions/{session_id}/close
    — Close a streaming session.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import asyncio

from fastapi import APIRouter, HTTPException, Path, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from fastapi.responses import StreamingResponse

from app.modules.knowledge_hub.services.streaming_service import (
    StreamingEventType,
    get_streaming_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-hub/streaming", tags=["Knowledge Hub — Streaming"])


# ── Pydantic Schemas ───────────────────────────────────────────


class IngestDocumentRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Document text content to ingest")
    document_id: Optional[str] = Field(None, description="Optional document ID")
    metadata: Optional[dict[str, Any]] = Field(None, description="Optional document metadata")


class CreateSessionRequest(BaseModel):
    source_type: str = Field("web", description="Source type identifier")
    source_id: str = Field("anonymous", description="Source identifier (user, system, etc.)")
    metadata: Optional[dict[str, Any]] = Field(None, description="Session metadata")


# ═══════════════════════════════════════════════════════════════════
# REST Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.post("/sessions", status_code=201)
async def create_streaming_session(
    request: CreateSessionRequest,
) -> dict[str, Any]:
    """Create a new streaming ingestion session.

    Returns the session ID which is used for subsequent WebSocket
    connections and ingestion requests.
    """
    service = get_streaming_service()
    session = service.create_session(
        source_type=request.source_type,
        source_id=request.source_id,
        metadata=request.metadata,
    )
    return {
        "success": True,
        "data": {
            "session_id": session.session_id,
            "source_type": session.source_type,
            "source_id": session.source_id,
            "started_at": session.started_at,
        },
        "message": f"Streaming session {session.session_id[:8]} created",
    }


@router.post("/sessions/{session_id}/ingest")
async def ingest_document(
    request: IngestDocumentRequest,
    session_id: str = Path(..., description="Active streaming session ID"),
) -> dict[str, Any]:
    """Ingest a text document through the streaming pipeline.

    Processes the document through chunking → embedding pipeline
    and returns the result with chunk information. Progress is also
    streamed to any connected WebSocket clients in the session.
    """
    service = get_streaming_service()
    result = await service.ingest_text(
        session_id=session_id,
        text=request.text,
        document_id=request.document_id,
        metadata=request.metadata,
    )
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Session not found"))
    return {
        "success": True,
        "data": result,
        "message": f"Ingested document: {result['chunks_created']} chunks created, {result['chunks_embedded']} embedded",
    }


@router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    """List all active streaming sessions."""
    service = get_streaming_service()
    sessions = service.list_active_sessions()
    return {
        "success": True,
        "data": sessions,
        "total": len(sessions),
    }


@router.get("/sessions/{session_id}")
async def get_session_status(
    session_id: str = Path(..., description="Streaming session ID"),
) -> dict[str, Any]:
    """Get the current status of a streaming session."""
    service = get_streaming_service()
    status = service.get_session_status(session_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {
        "success": True,
        "data": status,
    }


@router.post("/sessions/{session_id}/close")
async def close_session(
    session_id: str = Path(..., description="Streaming session ID to close"),
) -> dict[str, Any]:
    """Close a streaming session and clean up resources."""
    service = get_streaming_service()
    session = service.connection_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    await service.close_session(session_id)
    return {
        "success": True,
        "message": f"Streaming session {session_id[:8]} closed",
    }


# ═══════════════════════════════════════════════════════════════════
# Server-Sent Events (SSE) Endpoint
# ═══════════════════════════════════════════════════════════════════


@router.get("/events")
async def stream_events():
    """Subscribe to chunk lifecycle events via Server-Sent Events.

    Returns SSE stream with chunk.created, chunk.deleted,
    embedding.updated, and validation.issue events.
    """
    service = get_streaming_service()

    async def event_generator():
        """Generate SSE events for chunk lifecycle."""

        # Use an asyncio.Queue as a bridge to push events to the SSE stream
        queue: asyncio.Queue = asyncio.Queue()

        class SSEWebSocket:
            """Minimal WebSocket-like wrapper that pushes to a Queue."""
            async def send_text(self, text: str) -> None:
                await queue.put(text)
            async def close(self) -> None:
                await queue.put(None)
            async def receive_text(self) -> str:
                return ""

        sse_ws = SSEWebSocket()
        service.connection_manager.subscribe_sse(sse_ws)  # type: ignore[arg-type]

        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': time.time()})}\n\n"

            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    if msg is None:
                        break
                    yield f"{msg}\n"
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield f": keepalive\n\n"
        finally:
            service.connection_manager.unsubscribe_sse(sse_ws)  # type: ignore[arg-type]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════════════════════════════
# WebSocket Ingestion Endpoint
# ═══════════════════════════════════════════════════════════════════


@router.websocket("/ws/{session_id}")
async def streaming_ws(websocket: WebSocket, session_id: str):
    """Real-time document ingestion WebSocket.

    Accepts JSON messages with document content. Each message is
    processed through the chunking → embedding pipeline in real-time,
    with progress and results streamed back to the client.

    Inbound message format:
    ```json
    {
      "type": "ingest",
      "document_id": "optional-doc-id",
      "text": "Document content to ingest",
      "metadata": { "key": "value" }
    }
    ```

    Outbound events:
    - stream.document.received    — Document received
    - stream.chunking.started     — Chunking phase started
    - stream.chunk.created        — Individual chunk created
    - stream.chunking.completed   — Chunking phase completed
    - stream.embedding.started    — Embedding phase started
    - stream.embedding.progress   — Embedding progress update
    - stream.embedding.completed  — Embedding phase completed
    - stream.ingestion.completed  — Full ingestion complete
    - stream.error                — Error occurred
    - stream.progress             — Overall progress update
    """
    service = get_streaming_service()
    cm = service.connection_manager

    # Validate session exists
    session = cm.get_session(session_id)
    if not session:
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "type": "stream.error",
            "error": f"Session '{session_id}' not found. Create a session first via POST /knowledge-hub/streaming/sessions",
        }))
        await websocket.close()
        return

    await cm.connect(websocket, session_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "stream.error",
                    "error": "Invalid JSON message",
                }))
                continue

            msg_type = msg.get("type", "ingest")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "timestamp": time.time()}))

            elif msg_type == "ingest":
                text = msg.get("text", "")
                if not text.strip():
                    await websocket.send_text(json.dumps({
                        "type": "stream.error",
                        "error": "Empty document text",
                    }))
                    continue

                # Process the document through the streaming pipeline
                result = await service.ingest_text(
                    session_id=session_id,
                    text=text,
                    document_id=msg.get("document_id"),
                    metadata=msg.get("metadata"),
                )

                # Send result directly to the caller
                await websocket.send_text(json.dumps({
                    "type": "stream.ingestion.completed",
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "data": result,
                }))

            elif msg_type == "status":
                status = service.get_session_status(session_id)
                await websocket.send_text(json.dumps({
                    "type": "stream.session.status",
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "data": status,
                }))

            elif msg_type == "close":
                await service.close_session(session_id)
                await websocket.send_text(json.dumps({
                    "type": "stream.session.closed",
                    "session_id": session_id,
                }))
                break

            else:
                await websocket.send_text(json.dumps({
                    "type": "stream.error",
                    "error": f"Unknown message type: {msg_type}",
                }))

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session=%s", session_id)
    except Exception as e:
        logger.exception("WebSocket error in session %s: %s", session_id, e)
    finally:
        await cm.disconnect(websocket, session_id)
        logger.info("WebSocket cleaned up: session=%s", session_id)
