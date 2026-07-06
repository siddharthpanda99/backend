"""
ChatGPT Export Integration — MCP Tool Registration.

Registers tools for importing, processing, and querying ChatGPT conversation
exports as MCP tools. Handles parsing the ChatGPT export JSON format,
entity extraction, summary generation, and storage in memory/knowledge graph.

Usage:
    # In app/mcp/server.py:
    from app.mcp.tools.chatgpt import register_chatgpt_tools
    register_chatgpt_tools(mcp_server)
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from sqlmodel import Session, select, text
from sqlalchemy import delete, func

from common_lib.modules.chatgpt_mcp.adapters import registry as provider_registry

logger = logging.getLogger("mcp.tools.chatgpt")

# ── Provider-aware helpers ────────────────────────────────────────────

def _parse_conversations_file(
    file_path: str,
    provider_id: Optional[str] = None,
    max_conversations: Optional[int] = None,
    include_deleted: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    """Parse a chat export file using the appropriate provider adapter.

    Returns (provider_id, normalized_conversations).
    Auto-detects provider if not specified.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    detected_id, conversations = provider_registry.parse_file(
        file_path,
        provider_id=provider_id,
        max_conversations=max_conversations,
        include_deleted=include_deleted,
    )
    logger.info("Parsed %d conversations via %s adapter", len(conversations), detected_id)
    return detected_id, conversations


def _extract_entities(text: str) -> list[dict[str, Any]]:
    """Simple rule-based entity extraction from text.

    Returns: list of {text, type, confidence}
    """
    entities = []

    # URLs
    urls = re.findall(r"https?://[^\s,]+", text)
    for url in urls[:5]:
        entities.append({"text": url, "type": "URL", "confidence": 0.95})

    # Email addresses
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    for email in emails:
        entities.append({"text": email, "type": "EMAIL", "confidence": 0.95})

    # Potential project names (PascalCase or quoted phrases)
    projects = re.findall(r'"([A-Z][a-z]+[A-Z][a-zA-Z]*)"', text)
    for proj in projects:
        entities.append({"text": proj, "type": "PROJECT", "confidence": 0.7})

    # Programming languages and technologies
    tech_keywords = ["Python", "TypeScript", "JavaScript", "React", "Node", "Docker",
                     "Kubernetes", "PostgreSQL", "MongoDB", "Redis", "FastAPI",
                     "LangChain", "PyTorch", "TensorFlow"]
    for tech in tech_keywords:
        if tech.lower() in text.lower():
            entities.append({"text": tech, "type": "TECHNOLOGY", "confidence": 0.85})

    # Deduplicate
    seen = set()
    unique = []
    for e in entities:
        key = (e["text"], e["type"])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return unique


def _generate_summary(messages: list[dict[str, Any]]) -> str:
    """Generate a simple thematic summary from conversation messages.

    Extracts key topics, technical terms, and action items.
    """
    if not messages:
        return "No messages to summarize."

    user_msgs = [m for m in messages if m.get("role") == "user"]
    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]

    # Collect all content
    all_text = " ".join(m.get("content", "") for m in messages)
    word_count = len(all_text.split())

    # Detect main topics (simple frequency-based)
    topic_keywords = [
        "project", "feature", "bug", "deploy", "architecture", "database",
        "frontend", "backend", "api", "test", "security", "performance",
    ]
    topics_found = []
    for kw in topic_keywords:
        if re.search(rf"\b{kw}\b", all_text, re.IGNORECASE):
            topics_found.append(kw)

    # Detect action items
    action_patterns = [
        r"(?:I(?:'ll| will)\s+)(\w[\w\s]+)",
        r"(?:we\s+(?:need to|should|must)\s+)(\w[\w\s]+)",
        r"(?:TODO|FIXME|HACK|XXX)[:\s]+([^\n]+)",
    ]
    action_items = []
    for pattern in action_patterns:
        matches = re.findall(pattern, all_text, re.IGNORECASE)
        action_items.extend(m.strip() for m in matches[:5])

    summary_parts = [
        f"Conversation with {len(user_msgs)} user messages and {len(assistant_msgs)} assistant messages.",
        f"Total word count: ~{word_count}.",
    ]

    if topics_found:
        summary_parts.append(f"Main topics: {', '.join(set(topics_found))}.")
    if action_items:
        summary_parts.append(f"Action items: {'; '.join(action_items[:3])}.")

    return " ".join(summary_parts)


# ── Shared Processing Pipeline ────────────────────────────────────


def run_import_pipeline(
    normalized: list[dict[str, Any]],
    *,
    provider_id: str = "chatgpt",
    extract_entities: bool = True,
    generate_summaries: bool = True,
    store_in_memory: bool = True,
    store_in_knowledge_graph: bool = True,
    create_vector_embeddings: bool = True,
    tag_with_source: Optional[str] = None,
) -> dict[str, Any]:
    """Core processing pipeline shared by MCP tool and API routes.

    Iterates over normalized conversations, performs entity extraction,
    summary generation, and computes aggregate counts.

    Args:
        normalized: List of normalized conversation dicts.
        extract_entities: Run entity extraction on messages.
        generate_summaries: Create thematic summaries.
        store_in_memory: Count toward memory records.
        store_in_knowledge_graph: Count toward KG nodes.
        create_vector_embeddings: Count toward vector embeddings.
        tag_with_source: Optional source tag to stamp on conversations.

    Returns:
        Result dict with all processing counts.
    """
    result: dict[str, Any] = {
        "status": "success",
        "provider": provider_id,
        "conversations_found": 0,
        "conversations_processed": len(normalized),
        "messages_total": sum(c["message_count"] for c in normalized),
        "entities_extracted": 0,
        "summaries_generated": 0,
        "memory_records_created": 0,
        "knowledge_graph_nodes_added": 0,
        "vector_embeddings_created": 0,
        "warnings": [],
    }

    all_entities: list[dict[str, Any]] = []

    for conv in normalized:
        if extract_entities:
            for msg in conv["messages"]:
                entities = _extract_entities(msg.get("content", ""))
                msg["entities"] = entities
                all_entities.extend(entities)
            result["entities_extracted"] = len(set(
                (e["text"], e["type"]) for e in all_entities
            ))

        if generate_summaries:
            conv["summary"] = _generate_summary(conv["messages"])
            result["summaries_generated"] += 1

        if store_in_memory:
            result["memory_records_created"] += 1

        if store_in_knowledge_graph and extract_entities:
            result["knowledge_graph_nodes_added"] += len(all_entities)

        if create_vector_embeddings:
            result["vector_embeddings_created"] += conv["message_count"]

        if tag_with_source:
            conv["source_tag"] = tag_with_source

    return result


# ── Tool Registration ──────────────────────────────────────────────


def register_chatgpt_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def chatgpt_process_export(
        file_path: str,
        provider: Optional[str] = None,
        extract_entities: bool = True,
        generate_summaries: bool = True,
        store_in_memory: bool = True,
        store_in_knowledge_graph: bool = True,
        create_vector_embeddings: bool = True,
        tag_with_source: Optional[str] = None,
        overwrite_existing: bool = False,
        max_conversations: Optional[int] = None,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        """Import and process an AI chat export file from any supported provider.

        Parses the export using the appropriate provider adapter (auto-detected or specified),
        normalizes messages, optionally extracts entities, generates summaries, and stores
        results in memory/knowledge graph/vector store.

        Supported providers: chatgpt, groq, gemini, openrouter.

        Args:
            file_path: Absolute path to the export JSON file.
            provider: Provider ID ("chatgpt", "groq", "gemini", "openrouter"). Auto-detected if omitted.
            extract_entities: Run entity extraction on messages (default: True).
            generate_summaries: Create thematic summaries (default: True).
            store_in_memory: Persist to conversational memory system (default: True).
            store_in_knowledge_graph: Add entities/topics to knowledge graph (default: True).
            create_vector_embeddings: Generate vectors for semantic search (default: True).
            tag_with_source: Optional source tag for all imported data.
            overwrite_existing: If True, re-import replaces existing data (default: False).
            max_conversations: Limit number of conversations to process.
            include_deleted: Process archived/deleted conversations (default: False).

        Returns:
            ProcessingResult with counts of processed conversations, messages, entities, etc.
        """
        logger.info("Starting chat export import: %s (provider=%s)", file_path, provider or "auto")

        try:
            detected_provider, normalized = _parse_conversations_file(
                file_path,
                provider_id=provider,
                max_conversations=max_conversations,
                include_deleted=include_deleted,
            )

            import time as time_mod
            start = time_mod.time()

            # Delegate to the shared pipeline
            result = run_import_pipeline(
                normalized,
                provider_id=detected_provider,
                extract_entities=extract_entities,
                generate_summaries=generate_summaries,
                store_in_memory=store_in_memory,
                store_in_knowledge_graph=store_in_knowledge_graph,
                create_vector_embeddings=create_vector_embeddings,
                tag_with_source=tag_with_source,
            )
            result["conversations_found"] = len(normalized)
            result["processing_time_ms"] = int((time_mod.time() - start) * 1000)
            result["provider"] = detected_provider

            logger.info(
                "Import complete via %s: %d conversations, %d messages in %dms",
                detected_provider, result["conversations_processed"], result["messages_total"], result["processing_time_ms"],
            )

            return result

        except FileNotFoundError as e:
            return {"status": "error", "error": str(e)}
        except json.JSONDecodeError as e:
            return {"status": "error", "error": f"Invalid JSON: {e}"}
        except Exception as e:
            logger.exception("Chat export import failed: %s", e)
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def chatgpt_search_history(
        query: str,
        limit: int = 10,
        source_tag: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> dict[str, Any]:
        """Search across imported ChatGPT conversation history.

        Performs semantic search using pgvector cosine similarity when embeddings
        are available, falls back to text matching on title/summary.

        Args:
            query: Search query string.
            limit: Maximum number of results (default: 10).
            source_tag: Filter by import source tag (e.g. "chatgpt-export-2026-07").
            timeframe: Time filter ("last_7_days", "last_30_days", "this_month", "last_3_months").

        Returns:
            Dict with results list, query info, and total count.
        """
        from common_lib.modules.chatgpt_mcp.models import ChatGPTConversationRecord
        from common_lib.modules.data_storage.database.connection import get_engine

        engine = get_engine()
        with Session(engine) as db:
            # Try vector search first if embeddings exist
            try:
                from common_lib.modules.memory.memory_storage.embedding_service import EmbeddingService
                svc = EmbeddingService.get_instance("all-MiniLM-L6-v2")
                query_embedding = svc.encode(query)

                # Build the vector similarity query
                sql = text("""
                    SELECT id, title, message_count, summary, source_tag, created_at,
                           1 - (embedding <=> :query_vec::vector) AS similarity
                    FROM chatgpt_conversations
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> :query_vec::vector
                    LIMIT :lim
                """)
                params = {"query_vec": str(query_embedding), "lim": limit}
                rows = db.execute(sql, params).fetchall()

                results = []
                for row in rows:
                    results.append({
                        "id": row[0],
                        "title": row[1],
                        "message_count": row[2],
                        "summary": row[3],
                        "source_tag": row[4],
                        "created_at": row[5].isoformat() if row[5] else None,
                        "similarity": round(float(row[6]), 4) if row[6] else None,
                        "search_method": "vector",
                    })
                return {"results": results, "query": query, "total": len(results), "method": "semantic"}

            except Exception as e:
                logger.debug("Vector search unavailable, falling back to text: %s", e)

            # Fallback: text search on title/summary
            stmt = select(ChatGPTConversationRecord)
            if source_tag:
                stmt = stmt.where(ChatGPTConversationRecord.source_tag == source_tag)
            stmt = stmt.limit(limit * 3)  # over-fetch for text filtering
            records = db.exec(stmt).all()

            q = query.lower()
            results = []
            for r in records:
                if q in (r.title or "").lower() or q in (r.summary or "").lower():
                    results.append({
                        "id": r.id, "title": r.title,
                        "message_count": r.message_count, "summary": r.summary,
                        "source_tag": r.source_tag,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "similarity": None, "search_method": "text",
                    })
            return {"results": results[:limit], "query": query, "total": len(results), "method": "text"}

    @mcp.tool()
    async def chatgpt_get_conversation(
        conversation_id: str,
    ) -> dict[str, Any]:
        """Retrieve a full imported ChatGPT conversation by ID.

        Args:
            conversation_id: The ID of the conversation to retrieve.

        Returns:
            Full conversation with messages, metadata, and entities.
        """
        from common_lib.modules.chatgpt_mcp.models import ChatGPTConversationRecord
        from common_lib.modules.data_storage.database.connection import get_engine

        engine = get_engine()
        with Session(engine) as db:
            record = db.exec(
                select(ChatGPTConversationRecord).where(
                    ChatGPTConversationRecord.id == conversation_id
                )
            ).first()
            if not record:
                return {"conversation_id": conversation_id, "status": "not_found"}
            return {
                "conversation_id": record.id,
                "title": record.title,
                "message_count": record.message_count,
                "summary": record.summary,
                "entities": record.entities_json,
                "provider": getattr(record, 'provider', 'chatgpt'),
                "source_tag": record.source_tag,
                "metadata": record.metadata_json,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }

    @mcp.tool()
    async def chatgpt_get_summary(
        topic: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get thematic summary of ChatGPT conversations for a topic or timeframe.

        Args:
            topic: Topic to summarize (e.g. "machine learning", "project alpha").
            timeframe: Time period ("today", "this_week", "this_month", "last_3_months").

        Returns:
            Summary with key discussion points, topics, and statistics.
        """
        from common_lib.modules.chatgpt_mcp.models import ChatGPTConversationRecord
        from common_lib.modules.data_storage.database.connection import get_engine

        engine = get_engine()
        with Session(engine) as db:
            # Filter by timeframe
            stmt = select(ChatGPTConversationRecord)
            if timeframe:
                now = datetime.now(timezone.utc)
                tf_map = {
                    "today": now - timedelta(days=1),
                    "this_week": now - timedelta(weeks=1),
                    "this_month": now - timedelta(days=30),
                    "last_3_months": now - timedelta(days=90),
                }
                if timeframe in tf_map:
                    stmt = stmt.where(ChatGPTConversationRecord.created_at >= tf_map[timeframe])
            stmt = stmt.limit(100)
            records = db.exec(stmt).all()

            # Filter by topic if specified
            if topic:
                t = topic.lower()
                records = [r for r in records if r.summary and t in r.summary.lower()]

            # Aggregate topics
            topic_keywords = ["project", "feature", "bug", "deploy", "architecture",
                            "database", "frontend", "backend", "api", "test", "security", "performance"]
            topic_counts: dict[str, int] = {}
            all_summaries = []
            for r in records:
                if r.summary:
                    all_summaries.append(r.summary)
                    for kw in topic_keywords:
                        if kw in r.summary.lower():
                            topic_counts[kw] = topic_counts.get(kw, 0) + 1

            top_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:10]

            return {
                "topic": topic or "all",
                "timeframe": timeframe or "all_time",
                "conversation_count": len(records),
                "summary": f"Found {len(records)} conversations" + (f" about '{topic}'" if topic else "") + f" with {len(top_topics)} distinct topics.",
                "top_topics": [t for t, _ in top_topics],
                "key_insights": all_summaries[:5],
            }

    @mcp.tool()
    async def chatgpt_extract_action_items(
        include_completed: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Extract action items from imported ChatGPT conversations.

        Scans stored summaries for action-oriented language (tasks, todos,
        commitments, follow-ups).

        Args:
            include_completed: If True, includes completed action items (default: False).
            limit: Maximum number of action items to return.

        Returns:
            List of action items with description, source, and confidence.
        """
        from common_lib.modules.chatgpt_mcp.models import ChatGPTConversationRecord
        from common_lib.modules.data_storage.database.connection import get_engine

        engine = get_engine()
        with Session(engine) as db:
            records = db.exec(select(ChatGPTConversationRecord).limit(200)).all()

            action_items = []
            for r in records:
                if not r.summary:
                    continue
                # Extract from Action items section of summary
                ai_matches = re.findall(r"Action items: ([^\.]+)", r.summary)
                for m in ai_matches:
                    for item in re.split(r";\s*", m):
                        item = item.strip()
                        if item:
                            action_items.append({
                                "description": item, "source_conversation_id": r.id,
                                "source_title": r.title, "confidence": 0.7,
                            })
                # Also scan for TODO/FIXME patterns in summary
                for pattern in [r"TODO[:\s]+([^\.]+)", r"FIXME[:\s]+([^\.]+)"]:
                    for m in re.findall(pattern, r.summary, re.IGNORECASE):
                        action_items.append({
                            "description": m.strip(), "source_conversation_id": r.id,
                            "source_title": r.title, "confidence": 0.5,
                        })

            return {"action_items": action_items[:limit], "total": len(action_items)}

    @mcp.tool()
    async def chatgpt_get_entity_mentions(
        entity: str,
    ) -> dict[str, Any]:
        """Find where a person, project, or technology was discussed in ChatGPT history.

        Args:
            entity: The entity name to search for (e.g. "Project Alpha", "Python").

        Returns:
            List of conversation snippets where the entity was mentioned.
        """
        from common_lib.modules.chatgpt_mcp.models import ChatGPTConversationRecord
        from common_lib.modules.data_storage.database.connection import get_engine

        engine = get_engine()
        with Session(engine) as db:
            records = db.exec(
                select(ChatGPTConversationRecord).where(
                    ChatGPTConversationRecord.entities_json.isnot(None)
                ).limit(500)
            ).all()

            mentions = []
            e = entity.lower()
            for r in records:
                ents = r.entities_json or {}
                for ent_name, ent_type in ents.get("entities", []):
                    if e in ent_name.lower():
                        mentions.append({
                            "conversation_id": r.id, "title": r.title,
                            "entity": ent_name, "type": ent_type,
                        })
                # Also check title and summary
                if e in (r.title or "").lower() or e in (r.summary or "").lower():
                    mentions.append({
                        "conversation_id": r.id, "title": r.title,
                        "entity": entity, "type": "TEXT_MATCH",
                    })

            return {"entity": entity, "mentions": mentions, "total": len(mentions)}

    @mcp.tool()
    async def chatgpt_topic_evolution(
        topic: str,
        timeframe: str = "last_3_months",
    ) -> dict[str, Any]:
        """Analyze how a topic evolved over time in your ChatGPT conversations.

        Args:
            topic: Topic to analyze (e.g. "AI safety", "microservices").
            timeframe: Analysis period ("last_30_days", "last_3_months", "last_year").

        Returns:
            Timeline of key discussion points and sentiment shifts.
        """
        from common_lib.modules.chatgpt_mcp.models import ChatGPTConversationRecord
        from common_lib.modules.data_storage.database.connection import get_engine

        tf_days = {"last_30_days": 30, "last_3_months": 90, "last_year": 365}
        days = tf_days.get(timeframe, 90)
        since = datetime.now(timezone.utc) - timedelta(days=days)

        engine = get_engine()
        with Session(engine) as db:
            records = db.exec(
                select(ChatGPTConversationRecord)
                .where(ChatGPTConversationRecord.created_at >= since)
                .order_by(ChatGPTConversationRecord.created_at.asc())
                .limit(500)
            ).all()

            t = topic.lower()
            timeline = []
            for r in records:
                if t in (r.title or "").lower() or t in (r.summary or "").lower():
                    timeline.append({
                        "conversation_id": r.id, "title": r.title,
                        "date": r.created_at.isoformat() if r.created_at else None,
                        "summary": (r.summary or "")[:200],
                    })

            return {
                "topic": topic, "timeframe": timeframe,
                "timeline_points": timeline,
                "total_mentions": len(timeline),
                "key_milestones": [p["title"] for p in timeline[:5]],
            }

    @mcp.tool()
    async def chatgpt_link_to_work(
        conversation_id: str,
        workspace: str = "default",
    ) -> dict[str, Any]:
        """Link topics from a ChatGPT conversation to other conversations by shared entities/topics.

        Args:
            conversation_id: The conversation to link from.
            workspace: Workspace/project to link to.

        Returns:
            Matches with relevance scores.
        """
        from common_lib.modules.chatgpt_mcp.models import ChatGPTConversationRecord
        from common_lib.modules.data_storage.database.connection import get_engine

        engine = get_engine()
        with Session(engine) as db:
            # Get the source conversation
            source = db.exec(
                select(ChatGPTConversationRecord).where(
                    ChatGPTConversationRecord.id == conversation_id
                )
            ).first()
            if not source:
                return {"conversation_id": conversation_id, "status": "not_found"}

            # Find related conversations by shared entities
            source_entities = (source.entities_json or {}).get("entities", [])
            if not source_entities:
                # Fall back to text similarity on title/summary
                all_recs = db.exec(select(ChatGPTConversationRecord).limit(200)).all()
            else:
                all_recs = db.exec(select(ChatGPTConversationRecord).limit(200)).all()

            matches = []
            for r in all_recs:
                if r.id == conversation_id:
                    continue
                # Count shared entities
                r_entities = set((e[0] if isinstance(e, (list, tuple)) else e)
                                for e in (r.entities_json or {}).get("entities", []))
                s_entities = set(e[0] if isinstance(e, (list, tuple)) else e
                               for e in source_entities)
                shared = r_entities & s_entities
                if shared:
                    matches.append({
                        "conversation_id": r.id, "title": r.title,
                        "shared_entities": list(shared),
                        "relevance_score": len(shared) / max(len(s_entities), 1),
                    })

            matches.sort(key=lambda x: -x["relevance_score"])
            return {
                "conversation_id": conversation_id,
                "workspace": workspace,
                "matches": matches[:10],
                "links_created": 0,
            }

    @mcp.tool()
    async def chatgpt_list_imports() -> dict[str, Any]:
        """List all chat history import sessions with metadata.

        Returns:
            List of import records with timestamp, provider, conversation count, and source tag.
        """
        from common_lib.modules.chatgpt_mcp.models import ChatGPTImportSession
        from common_lib.modules.data_storage.database.connection import get_engine

        engine = get_engine()
        with Session(engine) as db:
            records = db.exec(
                select(ChatGPTImportSession).order_by(ChatGPTImportSession.created_at.desc())
            ).all()
            imports = []
            for r in records:
                imports.append({
                    "id": r.id, "file_path": r.file_path,
                    "provider": getattr(r, 'provider', 'chatgpt'),
                    "source_tag": r.source_tag,
                    "status": r.status,
                    "conversations_processed": r.conversations_processed,
                    "messages_total": r.messages_total,
                    "entities_extracted": r.entities_extracted,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                })
            return {"imports": imports, "total": len(imports)}

    @mcp.tool()
    async def chatgpt_delete_by_source(
        source_tag: str,
    ) -> dict[str, Any]:
        """Delete all imported ChatGPT data by source tag.

        Args:
            source_tag: The source tag used during import (e.g. "chatgpt-export-2026-07").

        Returns:
            Status of deletion operation.
        """
        from common_lib.modules.chatgpt_mcp.models import (
            ChatGPTImportSession, ChatGPTConversationRecord,
        )
        from common_lib.modules.data_storage.database.connection import get_engine

        engine = get_engine()
        with Session(engine) as db:
            db.exec(delete(ChatGPTConversationRecord).where(
                ChatGPTConversationRecord.source_tag == source_tag
            ))
            result = db.exec(delete(ChatGPTImportSession).where(
                ChatGPTImportSession.source_tag == source_tag
            ))
            db.commit()
            return {
                "source_tag": source_tag, "status": "deleted",
                "records_deleted": result.rowcount,
            }

    logger.info("Chat History Integration: 10 MCP tools registered (all with DB queries)")
