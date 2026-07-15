"""AI Database Copilot API routes.
Thin wrapper — all logic in common_lib.modules.db_studio.ai_copilot.service.
"""

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.db_studio.ai_copilot import (
    AICopilotService,
    ConversationCreate, ConversationUpdate, ConversationOut, ConversationListResponse,
    MessageOut, MessageListResponse,
    ChatRequest, ChatResponse,
    GenerateQueryRequest, GenerateQueryResponse,
    ExplainQueryRequest, ExplainQueryResponse,
    ExplainSchemaRequest, ExplainSchemaResponse,
    OptimizeQueryRequest, OptimizeQueryResponse,
    DocumentSchemaRequest, DocumentSchemaResponse,
    FeedbackCreate, FeedbackOut,
    PromptCreate, PromptUpdate, PromptOut,
    ModelUsageOut,
    ArtifactOut,
)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Database Copilot"])
svc = AICopilotService()


# ── Conversations ─────────────────────────────────────────────────────

@router.post("/conversations", response_model=ConversationOut)
def create_conversation(req: ConversationCreate):
    return svc.create_conversation(req)


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: str):
    c = svc.get_conversation(conversation_id)
    if not c:
        raise HTTPException(404, "Conversation not found")
    return c


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    search: str = None,
    context_type: str = None,
    connection_id: str = None,
    is_pinned: bool = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_conversations(search, context_type, connection_id, is_pinned, offset, limit)


@router.put("/conversations/{conversation_id}", response_model=ConversationOut)
def update_conversation(conversation_id: str, req: ConversationUpdate):
    c = svc.update_conversation(conversation_id, req)
    if not c:
        raise HTTPException(404, "Conversation not found")
    return c


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    if not svc.delete_conversation(conversation_id):
        raise HTTPException(404, "Conversation not found")
    return {"ok": True}


# ── Messages ──────────────────────────────────────────────────────────

@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
def list_messages(
    conversation_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return svc.list_messages(conversation_id, offset, limit)


# ── Chat ──────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return svc.chat(req)


# ── Query Generation ──────────────────────────────────────────────────

@router.post("/generate-query", response_model=GenerateQueryResponse)
def generate_query(req: GenerateQueryRequest):
    return svc.generate_query(req)


# ── Query Explanation ─────────────────────────────────────────────────

@router.post("/explain-query", response_model=ExplainQueryResponse)
def explain_query(req: ExplainQueryRequest):
    return svc.explain_query(req)


# ── Schema Explanation ────────────────────────────────────────────────

@router.post("/explain-schema", response_model=ExplainSchemaResponse)
def explain_schema(req: ExplainSchemaRequest):
    return svc.explain_schema(req)


# ── Query Optimization ────────────────────────────────────────────────

@router.post("/optimize-query", response_model=OptimizeQueryResponse)
def optimize_query(req: OptimizeQueryRequest):
    return svc.optimize_query(req)


# ── Schema Documentation ──────────────────────────────────────────────

@router.post("/document-schema", response_model=DocumentSchemaResponse)
def document_schema(req: DocumentSchemaRequest):
    return svc.document_schema(req)


# ── Feedback ──────────────────────────────────────────────────────────

@router.post("/feedback", response_model=FeedbackOut)
def submit_feedback(req: FeedbackCreate):
    return svc.submit_feedback(req)


@router.get("/feedback", response_model=list[FeedbackOut])
def list_feedback(
    conversation_id: str = None,
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_feedback(conversation_id, limit)


# ── Prompts ───────────────────────────────────────────────────────────

@router.get("/prompts", response_model=list[PromptOut])
def list_prompts(
    category: str = None,
    database_type: str = None,
    is_active: bool = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_prompts(category, database_type, is_active, offset, limit)


@router.post("/prompts", response_model=PromptOut)
def create_prompt(req: PromptCreate):
    return svc.create_prompt(req)


@router.put("/prompts/{prompt_id}", response_model=PromptOut)
def update_prompt(prompt_id: str, req: PromptUpdate):
    p = svc.update_prompt(prompt_id, req)
    if not p:
        raise HTTPException(404, "Prompt not found")
    return p


@router.delete("/prompts/{prompt_id}")
def delete_prompt(prompt_id: str):
    if not svc.delete_prompt(prompt_id):
        raise HTTPException(404, "Prompt not found")
    return {"ok": True}


# ── Model Usage ───────────────────────────────────────────────────────

@router.get("/model-usage", response_model=list[ModelUsageOut])
def list_model_usage(
    conversation_id: str = None,
    model: str = None,
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_model_usage(conversation_id, model, limit)


# ── Generated Artifacts ───────────────────────────────────────────────

@router.get("/artifacts", response_model=list[ArtifactOut])
def list_artifacts(
    conversation_id: str = None,
    artifact_type: str = None,
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_artifacts(conversation_id, artifact_type, limit)
