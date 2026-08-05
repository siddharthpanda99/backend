"""PM AI Routes — AI-powered intelligence endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.modules.auth.dependencies import require_permission

router = APIRouter()


def _get_session():
    """Create a database session for AI route handlers."""
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


# ---------------------------------------------------------------------------
# Request/Response Schemas
# ---------------------------------------------------------------------------

class CategorizeRequest(BaseModel):
    title: str
    description: str = ""
    project_type: str = "software_scrum"


class CategorizeResponse(BaseModel):
    issue_type: str
    priority: str
    labels: List[str]
    components: List[str]
    confidence: float
    reasoning: str


class SuggestAssigneeRequest(BaseModel):
    title: str
    description: str = ""
    issue_type: str = "Task"
    priority: str = "medium"
    team_members: List[Dict[str, Any]] = []


class SuggestAssigneeResponse(BaseModel):
    recommended_assignee: Optional[str]
    confidence: float
    reasoning: str
    alternatives: List[Dict[str, Any]]
    workload_balance: str


class SummarizeIssueRequest(BaseModel):
    title: str
    description: str = ""
    status: str = "To Do"
    priority: str = "medium"
    comments: List[Dict[str, Any]] = []


class SummarizeSprintRequest(BaseModel):
    sprint_name: str
    sprint_goal: str = ""
    start_date: str = ""
    end_date: str = ""
    sprint_status: str = "active"
    committed_points: float = 0
    completed_points: float = 0
    issues: List[Dict[str, Any]] = []


class SummaryResponse(BaseModel):
    summary: str
    key_points: List[str]
    action_items: List[str]
    sentiment: str
    urgency: str


class PredictComplexityRequest(BaseModel):
    title: str
    description: str = ""
    issue_type: str = "Task"
    labels: List[str] = []
    past_issues: List[Dict[str, Any]] = []


class ComplexityResponse(BaseModel):
    estimated_points: int
    estimated_hours: float
    confidence: float
    complexity_factors: List[str]
    risks: List[str]
    breakdown: List[Dict[str, Any]]


class VelocityAnalysisRequest(BaseModel):
    project_name: str = ""
    sprint_length_days: int = 14
    sprint_history: List[Dict[str, Any]] = []
    current_sprint: Dict[str, Any] = {}


class VelocityResponse(BaseModel):
    average_velocity: float
    velocity_trend: str
    predicted_velocity: float
    confidence: float
    factors: List[str]
    recommendations: List[str]
    burndown_forecast: List[Dict[str, Any]]
    risks: List[str]


class SemanticSearchRequest(BaseModel):
    query: str
    available_statuses: List[str] = []
    team_members: List[str] = []


class SearchFiltersResponse(BaseModel):
    intent: str
    keywords: List[str]
    filters: Dict[str, Any]
    sort_by: str
    sort_order: str
    confidence: float


class AssistantChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


class AssistantChatResponse(BaseModel):
    response: str
    suggestions: List[str] = []
    actions: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/categorize", response_model=CategorizeResponse)
async def categorize_issue(req: CategorizeRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """AI-powered issue categorization. Suggests type, priority, labels, and components."""
    from common_lib.modules.project_management.issues.ai_service import IssueAIService
    with _get_session() as session:
        svc = IssueAIService(session=session)
        result = svc.categorize_issue(
            title=req.title,
            description=req.description,
            project_type=req.project_type,
        )
        return CategorizeResponse(**result)


@router.post("/suggest-assignee", response_model=SuggestAssigneeResponse)
async def suggest_assignee(req: SuggestAssigneeRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """AI-powered assignee recommendation based on expertise and workload."""
    from common_lib.modules.project_management.issues.ai_service import IssueAIService
    with _get_session() as session:
        svc = IssueAIService(session=session)
        result = svc.suggest_assignee(
            title=req.title,
            description=req.description,
            issue_type=req.issue_type,
            priority=req.priority,
            team_members=req.team_members,
        )
        return SuggestAssigneeResponse(**result)


@router.post("/summarize-issue", response_model=SummaryResponse)
async def summarize_issue(req: SummarizeIssueRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """AI-powered issue summary generation."""
    from common_lib.modules.project_management.issues.ai_service import IssueAIService
    with _get_session() as session:
        svc = IssueAIService(session=session)
        result = svc.summarize_issue(
            title=req.title,
            description=req.description,
            status=req.status,
            priority=req.priority,
            comments=req.comments,
        )
        return SummaryResponse(**result)


@router.post("/summarize-sprint", response_model=SummaryResponse)
async def summarize_sprint(req: SummarizeSprintRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """AI-powered sprint report summary."""
    from common_lib.modules.project_management.agile.ai_service import SprintAIService
    with _get_session() as session:
        svc = SprintAIService(session=session)
        result = svc.summarize_sprint(
            sprint_name=req.sprint_name,
            sprint_goal=req.sprint_goal,
            start_date=req.start_date,
            end_date=req.end_date,
            sprint_status=req.sprint_status,
            committed_points=req.committed_points,
            completed_points=req.completed_points,
            issues=req.issues,
        )
        return SummaryResponse(**result)


@router.post("/predict-complexity", response_model=ComplexityResponse)
async def predict_complexity(req: PredictComplexityRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """AI-powered complexity estimation and story point prediction."""
    from common_lib.modules.project_management.issues.ai_service import IssueAIService
    with _get_session() as session:
        svc = IssueAIService(session=session)
        result = svc.predict_complexity(
            title=req.title,
            description=req.description,
            issue_type=req.issue_type,
            labels=req.labels,
            past_issues=req.past_issues,
        )
        return ComplexityResponse(**result)


@router.post("/velocity-analysis", response_model=VelocityResponse)
async def velocity_analysis(req: VelocityAnalysisRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """AI-powered sprint velocity analysis and prediction."""
    from common_lib.modules.project_management.agile.ai_service import SprintAIService
    with _get_session() as session:
        svc = SprintAIService(session=session)
        result = svc.analyze_velocity(
            project_name=req.project_name,
            sprint_length_days=req.sprint_length_days,
            sprint_history=req.sprint_history,
            current_sprint=req.current_sprint,
        )
        return VelocityResponse(**result)


@router.post("/semantic-search", response_model=SearchFiltersResponse)
async def semantic_search(req: SemanticSearchRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """AI-powered natural language search with filter extraction."""
    from common_lib.modules.project_management.issues.ai_service import IssueAIService
    with _get_session() as session:
        svc = IssueAIService(session=session)
        result = svc.semantic_search(
            query=req.query,
            available_statuses=req.available_statuses,
            team_members=req.team_members,
        )
        return SearchFiltersResponse(**result)


@router.post("/assistant", response_model=AssistantChatResponse)
async def assistant_chat(req: AssistantChatRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """AI assistant for conversational help within PM context."""
    from common_lib.modules.project_management.issues.ai_service import IssueAIService
    with _get_session() as session:
        svc = IssueAIService(session=session)
        result = svc.assistant_chat(
            message=req.message,
            context=req.context,
        )
        return AssistantChatResponse(**result)


# ===========================================================================
# New AI Feature Routes (Domain 18 expansion)
# ===========================================================================

class TaskBreakdownRequest(BaseModel):
    title: str
    description: str = ""
    issue_type: str = "Task"
    priority: str = "medium"
    story_points: Optional[float] = None


class ProjectPlanRequest(BaseModel):
    name: str = ""
    objective: str = ""
    project_type: str = "software_scrum"
    scope: str = "medium"
    constraints: str = ""


class RiskDetectionRequest(BaseModel):
    project_name: str = ""
    status: str = "active"
    overdue_issues: List[Dict[str, Any]] = []
    upcoming_deadlines: List[Dict[str, Any]] = []
    blocked_issues: List[Dict[str, Any]] = []
    completed_pct: float = 0
    total_issues: int = 0
    open_issues: int = 0


class StandupRequest(BaseModel):
    date: str = ""
    sprint_name: str = ""
    activity: List[Dict[str, Any]] = []


class StatusReportRequest(BaseModel):
    project_name: str = ""
    status: str = "active"
    accomplishments: List[str] = []
    current_phase: str = ""
    total_issues: int = 0
    completed: int = 0
    in_progress: int = 0
    blocked: int = 0
    overdue: int = 0
    risks: List[str] = []
    milestones: List[str] = []


class DuplicateDetectionRequest(BaseModel):
    title: str
    description: str = ""
    issue_type: str = "Task"
    existing_issues: List[Dict[str, Any]] = []


class SprintPlanRequest(BaseModel):
    velocity: float = 0
    capacity: float = 0
    backlog_items: List[Dict[str, Any]] = []
    team_size: int = 1
    previous_completed: float = 0
    previous_committed: float = 0


@router.post("/task-breakdown")
async def task_breakdown(req: TaskBreakdownRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """Break down complex work into actionable subtasks."""
    from common_lib.modules.project_management.planning.ai_service import PlanningAIService
    with _get_session() as session:
        svc = PlanningAIService(session=session)
        result = svc.task_breakdown(
            title=req.title, description=req.description,
            issue_type=req.issue_type, priority=req.priority,
            story_points=req.story_points,
        )
        return result


@router.post("/project-planning")
async def project_planning(req: ProjectPlanRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """Generate a project plan with phases, milestones, and dependencies."""
    from common_lib.modules.project_management.planning.ai_service import PlanningAIService
    with _get_session() as session:
        svc = PlanningAIService(session=session)
        result = svc.project_planning(
            name=req.name, objective=req.objective,
            project_type=req.project_type, scope=req.scope,
            constraints=req.constraints,
        )
        return result


@router.post("/risk-detection")
async def risk_detection(req: RiskDetectionRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """Identify risks and suggest mitigations."""
    from common_lib.modules.project_management.risk.ai_service import RiskAIService
    with _get_session() as session:
        svc = RiskAIService(session=session)
        result = svc.risk_detection(
            project_name=req.project_name, status=req.status,
            overdue_issues=req.overdue_issues, upcoming_deadlines=req.upcoming_deadlines,
            blocked_issues=req.blocked_issues, completed_pct=req.completed_pct,
            total_issues=req.total_issues, open_issues=req.open_issues,
        )
        return result


@router.post("/standup-summary")
async def standup_summary(req: StandupRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """Generate standup summaries from team activity."""
    from common_lib.modules.project_management.agile.ai_service import SprintAIService
    with _get_session() as session:
        svc = SprintAIService(session=session)
        result = svc.standup_summary(
            date=req.date, sprint_name=req.sprint_name,
            activity=req.activity,
        )
        return result


@router.post("/status-report")
async def status_report(req: StatusReportRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """Draft a professional project status report."""
    from common_lib.modules.project_management.agile.ai_service import SprintAIService
    with _get_session() as session:
        svc = SprintAIService(session=session)
        result = svc.status_report(
            project_name=req.project_name, status=req.status,
            accomplishments=req.accomplishments, current_phase=req.current_phase,
            total_issues=req.total_issues, completed=req.completed,
            in_progress=req.in_progress, blocked=req.blocked,
            overdue=req.overdue, risks=req.risks, milestones=req.milestones,
        )
        return result


@router.post("/duplicate-detection")
async def duplicate_detection(req: DuplicateDetectionRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """Detect potential duplicate issues based on semantic similarity."""
    from common_lib.modules.project_management.issues.ai_service import IssueAIService
    with _get_session() as session:
        svc = IssueAIService(session=session)
        result = svc.duplicate_detection(
            title=req.title, description=req.description,
            issue_type=req.issue_type, existing_issues=req.existing_issues,
        )
        return result


@router.post("/sprint-planning")
async def sprint_planning(req: SprintPlanRequest, _perm: None = require_permission("ai.execute", "*", "ai")):
    """Suggest optimal sprint scope based on team velocity and backlog."""
    from common_lib.modules.project_management.agile.ai_service import SprintAIService
    with _get_session() as session:
        svc = SprintAIService(session=session)
        result = svc.sprint_planning(
            velocity=req.velocity, capacity=req.capacity,
            backlog_items=req.backlog_items, team_size=req.team_size,
            previous_completed=req.previous_completed,
            previous_committed=req.previous_committed,
        )
        return result
