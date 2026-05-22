"""
Collaboration WebSocket routes for multi-user workflow editing.
Handles: presence tracking, layout conflict resolution, and canvas comments.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── In-memory stores (replace with Redis/DB for production) ─────────────────

# { workflow_id: { user_id: PresenceInfo } }
_presence: Dict[str, Dict[str, dict]] = {}

# { workflow_id: List[CanvasComment] }
_comments: Dict[str, List[dict]] = {}

# { workflow_id: Set[WebSocket] }
_connections: Dict[str, Set[WebSocket]] = {}

# { workflow_id: { node_id: { user_id, timestamp } } }  – who is touching what
_node_locks: Dict[str, Dict[str, dict]] = {}


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _broadcast(workflow_id: str, payload: dict, exclude: Optional[WebSocket] = None):
    """Broadcast a message to all connections in a workflow room."""
    dead: List[WebSocket] = []
    for ws in _connections.get(workflow_id, set()):
        if ws is exclude:
            continue
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connections[workflow_id].discard(ws)


def _get_presence(workflow_id: str) -> List[dict]:
    return list(_presence.get(workflow_id, {}).values())


def _detect_layout_conflict(
    workflow_id: str, node_id: str, user_id: str
) -> Optional[dict]:
    """Return conflict info if another user is currently moving the same node."""
    lock = _node_locks.get(workflow_id, {}).get(node_id)
    if lock and lock["user_id"] != user_id:
        age = time.time() - lock["timestamp"]
        if age < 5.0:  # conflict window = 5 s
            return {"conflictWith": lock["user_id"], "lockedAt": lock["timestamp"]}
    return None


# ─── REST: Comments ───────────────────────────────────────────────────────────

class CommentCreateRequest(BaseModel):
    workflow_id: str
    user_id: str
    username: str
    avatar: Optional[str] = None
    x: float
    y: float
    node_id: Optional[str] = None
    body: str
    parent_id: Optional[str] = None


class CommentReplyRequest(BaseModel):
    user_id: str
    username: str
    avatar: Optional[str] = None
    body: str


@router.get("/comments/{workflow_id}")
async def get_comments(workflow_id: str):
    """Return all canvas comments for a workflow."""
    return {"comments": _comments.get(workflow_id, [])}


@router.post("/comments")
async def create_comment(req: CommentCreateRequest):
    """Create a new canvas comment (or threaded reply)."""
    comment = {
        "id": str(uuid.uuid4()),
        "workflow_id": req.workflow_id,
        "user_id": req.user_id,
        "username": req.username,
        "avatar": req.avatar,
        "x": req.x,
        "y": req.y,
        "node_id": req.node_id,
        "body": req.body,
        "parent_id": req.parent_id,
        "resolved": False,
        "created_at": time.time(),
        "replies": [],
    }
    _comments.setdefault(req.workflow_id, []).append(comment)

    # Notify connected peers
    await _broadcast(req.workflow_id, {"type": "comment.new", "comment": comment})
    return {"comment": comment}


@router.post("/comments/{comment_id}/reply")
async def reply_comment(comment_id: str, req: CommentReplyRequest):
    """Add a threaded reply to an existing comment."""
    for wid, comments in _comments.items():
        for c in comments:
            if c["id"] == comment_id:
                reply = {
                    "id": str(uuid.uuid4()),
                    "user_id": req.user_id,
                    "username": req.username,
                    "avatar": req.avatar,
                    "body": req.body,
                    "created_at": time.time(),
                }
                c["replies"].append(reply)
                await _broadcast(wid, {"type": "comment.reply", "comment_id": comment_id, "reply": reply})
                return {"reply": reply}
    return {"error": "Comment not found"}, 404


@router.patch("/comments/{comment_id}/resolve")
async def resolve_comment(comment_id: str):
    """Mark a comment as resolved."""
    for wid, comments in _comments.items():
        for c in comments:
            if c["id"] == comment_id:
                c["resolved"] = True
                await _broadcast(wid, {"type": "comment.resolved", "comment_id": comment_id})
                return {"ok": True}
    return {"error": "Not found"}, 404


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str):
    """Delete a canvas comment."""
    for wid, comments in _comments.items():
        _comments[wid] = [c for c in comments if c["id"] != comment_id]
        await _broadcast(wid, {"type": "comment.deleted", "comment_id": comment_id})
    return {"ok": True}


# ─── WebSocket: Collaboration Hub ─────────────────────────────────────────────

@router.websocket("/ws/{workflow_id}/{user_id}")
async def collaboration_ws(websocket: WebSocket, workflow_id: str, user_id: str):
    """
    Per-workflow collaboration WebSocket.
    
    Inbound message types from client:
      { type: "presence.update",  cursor: {x,y}, viewport: {x,y,scale}, username, avatar, color }
      { type: "node.move.start",  node_id }
      { type: "node.move.end",    node_id, x, y }
      { type: "node.move",        node_id, x, y }  — optimistic move broadcast
      { type: "viewport.follow",  target_user_id }  — request to receive viewport syncs
      { type: "viewport.unfollow" }
      { type: "ping" }
    
    Outbound message types to client:
      { type: "presence.list",    users: [...] }
      { type: "presence.joined",  user }
      { type: "presence.left",    user_id }
      { type: "cursor.update",    user_id, cursor, viewport }
      { type: "node.conflict",    node_id, conflictWith }
      { type: "node.move",        user_id, node_id, x, y }
      { type: "node.lock",        user_id, node_id }
      { type: "node.unlock",      node_id }
      { type: "viewport.sync",    user_id, viewport }
      { type: "comment.new",      comment }
      { type: "comment.reply",    comment_id, reply }
      { type: "comment.resolved", comment_id }
      { type: "pong" }
    """
    await websocket.accept()

    _connections.setdefault(workflow_id, set()).add(websocket)
    _presence.setdefault(workflow_id, {})
    _node_locks.setdefault(workflow_id, {})

    # Initialize user presence stub
    _presence[workflow_id][user_id] = {
        "user_id": user_id,
        "username": user_id,
        "avatar": None,
        "color": "#6366f1",
        "cursor": {"x": 0, "y": 0},
        "viewport": {"x": 0, "y": 0, "scale": 1},
        "joined_at": time.time(),
    }

    # Send current state to new joiner
    await websocket.send_text(json.dumps({
        "type": "presence.list",
        "users": _get_presence(workflow_id),
        "comments": _comments.get(workflow_id, []),
    }))

    # Notify others
    await _broadcast(workflow_id, {
        "type": "presence.joined",
        "user": _presence[workflow_id][user_id],
    }, exclude=websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            t = msg.get("type", "")

            if t == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif t == "presence.update":
                p = _presence[workflow_id].get(user_id, {})
                p.update({
                    "username": msg.get("username", p.get("username", user_id)),
                    "avatar": msg.get("avatar", p.get("avatar")),
                    "color": msg.get("color", p.get("color", "#6366f1")),
                    "cursor": msg.get("cursor", p.get("cursor", {"x": 0, "y": 0})),
                    "viewport": msg.get("viewport", p.get("viewport", {})),
                })
                _presence[workflow_id][user_id] = p
                await _broadcast(workflow_id, {
                    "type": "cursor.update",
                    "user_id": user_id,
                    "cursor": p["cursor"],
                    "viewport": p["viewport"],
                    "color": p["color"],
                    "username": p["username"],
                }, exclude=websocket)

            elif t == "node.move.start":
                node_id = msg.get("node_id")
                if node_id:
                    conflict = _detect_layout_conflict(workflow_id, node_id, user_id)
                    if conflict:
                        await websocket.send_text(json.dumps({
                            "type": "node.conflict",
                            "node_id": node_id,
                            **conflict,
                        }))
                    else:
                        _node_locks[workflow_id][node_id] = {
                            "user_id": user_id,
                            "timestamp": time.time(),
                        }
                        await _broadcast(workflow_id, {
                            "type": "node.lock",
                            "user_id": user_id,
                            "node_id": node_id,
                        }, exclude=websocket)

            elif t == "node.move":
                node_id = msg.get("node_id")
                x = msg.get("x", 0)
                y = msg.get("y", 0)
                if node_id:
                    # Refresh lock timestamp
                    if node_id in _node_locks[workflow_id]:
                        _node_locks[workflow_id][node_id]["timestamp"] = time.time()
                    await _broadcast(workflow_id, {
                        "type": "node.move",
                        "user_id": user_id,
                        "node_id": node_id,
                        "x": x,
                        "y": y,
                    }, exclude=websocket)

            elif t == "node.move.end":
                node_id = msg.get("node_id")
                if node_id:
                    _node_locks[workflow_id].pop(node_id, None)
                    await _broadcast(workflow_id, {
                        "type": "node.unlock",
                        "node_id": node_id,
                        "user_id": user_id,
                        "x": msg.get("x"),
                        "y": msg.get("y"),
                    })

            elif t == "viewport.follow":
                # Forward viewport syncs from target to follower
                # Follower registers interest, served on next presence.update from target
                pass  # client-side tracking via presence.update / cursor.update

    except WebSocketDisconnect:
        pass
    finally:
        _connections[workflow_id].discard(websocket)
        _presence[workflow_id].pop(user_id, None)

        # Release any locks held by this user
        for node_id, lock in list(_node_locks.get(workflow_id, {}).items()):
            if lock.get("user_id") == user_id:
                _node_locks[workflow_id].pop(node_id, None)

        await _broadcast(workflow_id, {
            "type": "presence.left",
            "user_id": user_id,
        })
        logger.info(f"[Collab] User {user_id} left workflow {workflow_id}")
