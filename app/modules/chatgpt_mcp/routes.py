"""
ChatGPT MCP Integration — FastAPI Router

Provides REST API endpoints for importing and querying ChatGPT conversation
exports. These routes delegate to the MCP tool helpers for processing logic
and persist data via SQLModel.

Endpoints:
  POST /chatgpt/import          — Import a ChatGPT conversations.json export
  GET  /chatgpt/conversations    — List imported conversations
  GET  /chatgpt/conversations/{id} — Get a specific conversation
  POST /chatgpt/search           — Search imported conversations
  POST /chatgpt/summary          — Get thematic summary
  POST /chatgpt/action-items     — Extract action items
  GET  /chatgpt/entities         — Get entity mentions
  GET  /chatgpt/imports          — List import sessions
  DELETE /chatgpt/imports        — Delete imported data by source tag
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete
from sqlmodel import Session, select

from common_lib.modules.data_storage.database.connection import get_session as get_db_session

# Delegate to the MCP tool processing helpers
from app.mcp.tools.chatgpt import (
    _parse_conversations_file,
    run_import_pipeline,
)
from common_lib.modules.connectors.chatgpt_mcp.models import (
    ChatGPTConversationRecord,
    ChatGPTImportSession,
)
from common_lib.modules.connectors.chatgpt_mcp.adapters import registry as provider_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatgpt", tags=["AI Chat History"])


# ── Pydantic Schemas ───────────────────────────────────────────────


class ImportRequest(BaseModel):
    file_path: str
    provider: Optional[str] = None  # Auto-detected if omitted
    extract_entities: bool = True
    generate_summaries: bool = True
    store_in_memory: bool = True
    store_in_knowledge_graph: bool = True
    create_vector_embeddings: bool = True
    tag_with_source: Optional[str] = None
    overwrite_existing: bool = False
    max_conversations: Optional[int] = None
    include_deleted: bool = False


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    source_tag: Optional[str] = None
    timeframe: Optional[str] = None


class SummaryRequest(BaseModel):
    topic: Optional[str] = None
    timeframe: Optional[str] = None


class ActionItemsRequest(BaseModel):
    include_completed: bool = False
    limit: int = 20


class DeleteRequest(BaseModel):
    source_tag: str


# ── Processing Logic ───────────────────────────────────────────────


def _process_export(
    file_path: str,
    body: ImportRequest,
    db: Session,
) -> dict[str, Any]:
    """Import and persist AI chat conversations from any supported provider.

    Steps:
      1. Auto-detect or use specified provider adapter to parse
      2. Run the shared processing pipeline (entities, summaries)
      3. Persist results to DB
      4. Return processing report
    """
    detected_provider, normalized = _parse_conversations_file(
        file_path,
        provider_id=body.provider,
        max_conversations=body.max_conversations,
        include_deleted=body.include_deleted,
    )

    result = run_import_pipeline(
        normalized,
        provider_id=detected_provider,
        extract_entities=body.extract_entities,
        generate_summaries=body.generate_summaries,
        store_in_memory=body.store_in_memory,
        store_in_knowledge_graph=body.store_in_knowledge_graph,
        create_vector_embeddings=body.create_vector_embeddings,
        tag_with_source=body.tag_with_source,
    )
    result["conversations_found"] = len(normalized)
    result["provider"] = detected_provider

    # ---- Persist to DB ----

    session_id = str(uuid.uuid4())
    import_session = ChatGPTImportSession(
        id=session_id,
        file_path=file_path,
        provider=detected_provider,
        source_tag=body.tag_with_source,
        status="completed" if result.get("status") == "success" else "error",
        conversations_found=result.get("conversations_found", 0),
        conversations_processed=result.get("conversations_processed", 0),
        messages_total=result.get("messages_total", 0),
        entities_extracted=result.get("entities_extracted", 0),
        summaries_generated=result.get("summaries_generated", 0),
        processing_time_ms=result.get("processing_time_ms"),
        error_message=result.get("error"),
        metadata_json={"flags": body.model_dump(exclude={"file_path"})},
    )
    db.add(import_session)

    # Generate embeddings in batch if requested
    embeddings_map: dict[str, list[float]] = {}
    if body.create_vector_embeddings:
        try:
            from common_lib.modules.memory.memory_storage.embedding_service import EmbeddingService
            svc = EmbeddingService.get_instance("all-MiniLM-L6-v2")
            texts = []
            conv_ids = []
            for conv in normalized:
                # Build text for embedding: title + summary + first few messages
                parts = [conv.get("title", "")]
                if conv.get("summary"):
                    parts.append(conv["summary"])
                for msg in conv.get("messages", [])[:5]:
                    parts.append(msg.get("content", "")[:200])
                texts.append(" ".join(parts)[:1000])  # cap at 1000 chars
                conv_ids.append(conv.get("conversation_id", ""))
            if texts:
                vecs = svc.encode_batch(texts)
                embeddings_map = dict(zip(conv_ids, vecs))
                result["vector_embeddings_created"] = len(vecs)
                logger.info("Generated %d embeddings for import", len(vecs))
        except Exception as e:
            logger.warning("Embedding generation failed (non-fatal): %s", e)

    # Store each conversation record
    for conv in normalized:
        conv_id = conv.get("conversation_id", str(uuid.uuid4()))
        conv_record = ChatGPTConversationRecord(
            id=conv_id,
            import_session_id=session_id,
            provider=detected_provider,
            title=conv.get("title", "Untitled"),
            message_count=conv.get("message_count", 0),
            summary=conv.get("summary"),
            entities_json=(
                {"entities": list(set(
                    (e["text"], e["type"]) for msg in conv.get("messages", [])
                    for e in msg.get("entities", [])
                ))}
                if body.extract_entities
                else {}
            ),
            source_tag=body.tag_with_source,
            metadata_json={"conversation_id": conv.get("conversation_id", ""), **(conv.get("metadata", {}))},
        )
        # Attach embedding if generated
        if conv_id in embeddings_map:
            conv_record.embedding = embeddings_map[conv_id]
        db.add(conv_record)

    db.commit()
    result["import_session_id"] = session_id

    return result


# ── Endpoints ───────────────────────────────────────────────────────


@router.post("/import")
async def import_chatgpt_export(
    body: ImportRequest,
    db: Session = Depends(get_db_session),
):
    """Import a ChatGPT conversations.json export file.

    Processes and persists conversations in the database.
    Delegates to the MCP tool helpers for parsing and normalization.
    """
    path = Path(body.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {body.file_path}")

    try:
        return _process_export(body.file_path, body, db)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {body.file_path}")
    except Exception as e:
        logger.exception("ChatGPT import failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    source_tag: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session),
):
    """List imported ChatGPT conversations."""
    query = select(ChatGPTConversationRecord)
    if source_tag:
        query = query.where(ChatGPTConversationRecord.source_tag == source_tag)
    query = query.offset(offset).limit(limit).order_by(ChatGPTConversationRecord.created_at.desc())

    records = db.exec(query).all()
    return {
        "conversations": [
            {
                "id": r.id,
                "title": r.title,
                "message_count": r.message_count,
                "provider": getattr(r, 'provider', 'chatgpt'),
                "source_tag": r.source_tag,
                "summary": r.summary,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
        "total": len(records),
        "limit": limit,
        "offset": offset,
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db_session),
):
    """Get a specific imported conversation by ID."""
    record = db.exec(
        select(ChatGPTConversationRecord).where(
            ChatGPTConversationRecord.id == conversation_id
        )
    ).first()
    if not record:
        return {
            "conversation_id": conversation_id,
            "status": "not_found",
            "message": "Conversation not found or not imported.",
        }
    return {
        "conversation_id": record.id,
        "title": record.title,
        "message_count": record.message_count,
        "summary": record.summary,
        "entities": record.entities_json,
        "provider": getattr(record, 'provider', 'chatgpt'),
        "source_tag": record.source_tag,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@router.post("/search")
async def search_conversations(
    body: SearchRequest,
    db: Session = Depends(get_db_session),
):
    """Search imported ChatGPT conversations with semantic vector search (pgvector).

    Falls back to text matching on title/summary if embeddings are unavailable.
    """
    q = body.query.strip()
    if not q:
        return {"results": [], "query": body.query, "total": 0, "method": "none"}

    # Try vector search first
    try:
        from sqlalchemy import text as sa_text
        from common_lib.modules.memory.memory_storage.embedding_service import EmbeddingService

        svc = EmbeddingService.get_instance("all-MiniLM-L6-v2")
        query_embedding = svc.encode(q)

        sql = sa_text("""
            SELECT id, title, message_count, summary, source_tag, created_at,
                   1 - (embedding <=> :query_vec::vector) AS similarity
            FROM chatgpt_conversations
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :query_vec::vector
            LIMIT :lim
        """)
        params = {"query_vec": str(query_embedding), "lim": body.limit}
        if body.source_tag:
            sql = sa_text("""
                SELECT id, title, message_count, summary, source_tag, created_at,
                       1 - (embedding <=> :query_vec::vector) AS similarity
                FROM chatgpt_conversations
                WHERE embedding IS NOT NULL AND source_tag = :src
                ORDER BY embedding <=> :query_vec::vector
                LIMIT :lim
            """)
            params["src"] = body.source_tag

        rows = db.exec(sql, params).all()
        results = [
            {
                "id": row[0], "title": row[1], "message_count": row[2],
                "summary": row[3], "source_tag": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
                "similarity": round(float(row[6]), 4) if row[6] else None,
            }
            for row in rows
        ]
        return {"results": results, "query": body.query, "total": len(results), "method": "semantic"}

    except Exception as e:
        logger.debug("Vector search unavailable, falling back to text: %s", e)

    # Fallback: text search on title/summary
    query = select(ChatGPTConversationRecord)
    if body.source_tag:
        query = query.where(ChatGPTConversationRecord.source_tag == body.source_tag)
    records = db.exec(query.limit(body.limit * 3)).all()

    ql = q.lower()
    results = [
        {
            "id": r.id, "title": r.title, "message_count": r.message_count,
            "summary": r.summary, "source_tag": r.source_tag,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "similarity": None,
        }
        for r in records
        if ql in (r.title or "").lower() or ql in (r.summary or "").lower()
    ]

    return {"results": results[:body.limit], "query": body.query, "total": len(results), "method": "text"}


@router.post("/summary")
async def get_summary(
    body: SummaryRequest,
    db: Session = Depends(get_db_session),
):
    """Get thematic summary of ChatGPT conversations."""
    query = select(ChatGPTConversationRecord)
    if body.topic:
        records = db.exec(query.limit(50)).all()
        recs = [
            r for r in records
            if r.summary and body.topic.lower() in r.summary.lower()
        ]
    else:
        records = db.exec(query.limit(20)).all()
        recs = records

    return {
        "topic": body.topic or "all",
        "timeframe": body.timeframe or "all_time",
        "conversation_count": len(recs),
        "summary": (
            f"Found {len(recs)} conversations."
            if recs
            else "No imported conversations found."
        ),
        "top_topics": list(set(
            t for r in recs
            if r.summary
            for t in ["project", "feature", "bug", "deploy", "api", "test", "security"]
            if t in r.summary.lower()
        )),
        "key_insights": [],
    }


@router.post("/action-items")
async def get_action_items(
    body: ActionItemsRequest,
    db: Session = Depends(get_db_session),
):
    """Extract action items from imported conversations."""
    records = db.exec(
        select(ChatGPTConversationRecord).limit(body.limit)
    ).all()

    action_items = []
    for r in records:
        if r.summary:
            matches = re.findall(
                r"(?:Action items: )([^;]+(?:; [^;]+)*)",
                r.summary,
            )
            for m in matches:
                for item in m.split("; "):
                    action_items.append({
                        "description": item.strip(),
                        "source_conversation_id": r.id,
                        "confidence": 0.6,
                    })

    return {
        "action_items": action_items[:body.limit],
        "total": len(action_items),
        "message": (
            f"Found {len(action_items)} action items."
            if action_items
            else "No action items found. Import conversations first."
        ),
    }


@router.get("/providers")
async def list_providers():
    """List all supported chat history providers and their capabilities."""
    return {"providers": provider_registry.list_providers()}


@router.get("/entities")
async def get_entities(
    entity: str = Query(..., description="Entity name to search for"),
    provider: Optional[str] = Query(None, description="Filter by provider ID"),
    db: Session = Depends(get_db_session),
):
    """Find entity mentions across imported conversations."""
    query = select(ChatGPTConversationRecord).where(
        ChatGPTConversationRecord.entities_json.isnot(None)
    )
    if provider:
        query = query.where(ChatGPTConversationRecord.provider == provider)
    records = db.exec(query.limit(500)).all()

    mentions = []
    for r in records:
        ents = r.entities_json or {}
        entities_list = ents.get("entities", [])
        for ent_name, ent_type in entities_list:
            if entity.lower() in ent_name.lower():
                mentions.append({
                    "conversation_id": r.id,
                    "title": r.title,
                    "entity": ent_name,
                    "type": ent_type,
                    "provider": getattr(r, 'provider', 'chatgpt'),
                })

    return {
        "entity": entity,
        "mentions": mentions,
        "total": len(mentions),
    }


@router.get("/imports")
async def list_imports(
    db: Session = Depends(get_db_session),
):
    """List all ChatGPT import sessions."""
    records = db.exec(
        select(ChatGPTImportSession).order_by(ChatGPTImportSession.created_at.desc())
    ).all()
    return {
        "imports": [
            {
                "id": r.id,
                "file_path": r.file_path,
                "provider": getattr(r, 'provider', 'chatgpt'),
                "source_tag": r.source_tag,
                "status": r.status,
                "conversations_processed": r.conversations_processed,
                "messages_total": r.messages_total,
                "entities_extracted": r.entities_extracted,
                "processing_time_ms": r.processing_time_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
        "total": len(records),
    }


@router.delete("/imports")
async def delete_imports(
    body: DeleteRequest,
    db: Session = Depends(get_db_session),
):
    """Delete all imported data by source tag."""
    # Delete conversations
    db.exec(
        delete(ChatGPTConversationRecord).where(
            ChatGPTConversationRecord.source_tag == body.source_tag
        )
    )

    # Delete import sessions
    result = db.exec(
        delete(ChatGPTImportSession).where(
            ChatGPTImportSession.source_tag == body.source_tag
        )
    )

    db.commit()
    return {
        "source_tag": body.source_tag,
        "status": "deleted",
        "records_deleted": result.rowcount,
    }
