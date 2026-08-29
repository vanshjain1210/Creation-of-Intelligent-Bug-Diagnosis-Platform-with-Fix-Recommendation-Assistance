"""Pydantic request/response schemas for API layer."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models import AnalysisStatus, BugPriority, BugStatus, WorkflowStage
from app.schemas.agent_schemas import LogAnalysisResult, TriageResult, UnifiedBugAnalysis

__all__ = [
    "AgentOutputSchema",
    "AnalyzeRequest",
    "AnalyzeResponse",
    "AnalysisResponse",
    "BugResponse",
    "BugSubmitRequest",
    "BugSubmitResponse",
    "DashboardResponse",
    "ErrorResponse",
    "HealthResponse",
    "HistoryItem",
    "HistoryResponse",
    "KnowledgeBaseItem",
    "KnowledgeBaseResponse",
    "KnowledgeBaseUpdateRequest",
    "LogAnalysisResult",
    "ServiceStatus",
    "SettingsResponse",
    "SettingsUpdateRequest",
    "StatusResponse",
    "TriageResult",
    "UnifiedBugAnalysis",
]


# --- Bug schemas ---


class BugSubmitRequest(BaseModel):
    """Submit bug via pasted text."""

    title: Optional[str] = None
    description: Optional[str] = None
    content: str = Field(..., min_length=1, description="Bug report text content")
    component: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class BugResponse(BaseModel):
    id: str
    title: str
    description: str
    raw_content: Optional[str] = None
    file_name: Optional[str] = None
    status: BugStatus
    metadata: Dict[str, Any]
    created_at: datetime


class BugSubmitResponse(BaseModel):
    success: bool = True
    message: str
    bug: BugResponse
    analysis_id: Optional[str] = None


# --- Analysis schemas ---


class AnalyzeRequest(BaseModel):
    bug_id: str
    use_mmr: bool = True
    retrieval_top_k: Optional[int] = None


class AgentOutputSchema(BaseModel):
    agent_name: str
    stage: WorkflowStage
    output: Dict[str, Any]
    confidence: float
    duration_ms: int


class AnalysisResponse(BaseModel):
    id: str
    bug_id: str
    status: AnalysisStatus
    current_stage: WorkflowStage
    triage: Optional[Dict[str, Any]] = None
    log_analysis: Optional[Dict[str, Any]] = None
    duplicate_detection: Optional[Dict[str, Any]] = None
    root_cause: Optional[Dict[str, Any]] = None
    remediation: Optional[Dict[str, Any]] = None
    risk_assessment: Optional[Dict[str, Any]] = None
    confidence_scoring: Optional[Dict[str, Any]] = None
    executive_summary: Optional[Dict[str, Any]] = None
    retrieved_context: List[Dict[str, Any]] = Field(default_factory=list)
    agent_results: List[AgentOutputSchema] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime
    completed_at: Optional[datetime] = None


class AnalyzeResponse(BaseModel):
    success: bool = True
    message: str
    analysis: AnalysisResponse


# --- History schemas ---


class HistoryItem(BaseModel):
    id: str
    bug_id: str
    analysis_id: Optional[str] = None
    title: str
    priority: BugPriority
    component: str
    status: AnalysisStatus
    summary: str
    created_at: datetime


class HistoryResponse(BaseModel):
    success: bool = True
    total: int
    items: List[HistoryItem]


class KnowledgeBaseItem(BaseModel):
    id: str
    title: str
    description: str
    status: BugStatus
    priority: Optional[str] = None
    category: Optional[str] = None
    root_cause: Optional[str] = None
    resolution: Optional[str] = None
    created_at: datetime


class KnowledgeBaseResponse(BaseModel):
    success: bool = True
    total: int
    items: List[KnowledgeBaseItem]


class KnowledgeBaseUpdateRequest(BaseModel):
    bug_id: str
    confirmed_root_cause: Optional[str] = None
    applied_fix: Optional[str] = None
    resolution_notes: Optional[str] = None
    status: Optional[str] = None


class DashboardResponse(BaseModel):
    total_bugs: int = 0
    open_bugs: int = 0
    resolved_bugs: int = 0
    high_risk_bugs: int = 0
    recurring_bugs: int = 0
    duplicate_bugs: int = 0
    severity_distribution: Dict[str, int] = Field(default_factory=dict)
    component_counts: Dict[str, int] = Field(default_factory=dict)
    recent_analyses: List[Dict[str, Any]] = Field(default_factory=list)


# --- Settings schemas ---


class SettingsResponse(BaseModel):
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    retrieval_top_k: int
    mmr_lambda: float
    max_upload_size_mb: int
    allowed_extensions: List[str]
    llm_model: str
    enable_mmr: bool


class SettingsUpdateRequest(BaseModel):
    retrieval_top_k: Optional[int] = Field(None, ge=1, le=20)
    mmr_lambda: Optional[float] = Field(None, ge=0.0, le=1.0)
    enable_mmr: Optional[bool] = None


# --- Health & Status schemas ---


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    timestamp: datetime


class ServiceStatus(BaseModel):
    name: str
    status: str
    message: str


class StatusResponse(BaseModel):
    overall: str
    services: List[ServiceStatus]
    active_analyses: int
    total_bugs: int
    chroma_documents: int
    last_indexing_time: Optional[str] = None
    storage_used: Optional[str] = None
    model_version: Optional[str] = None
    embedding_model: Optional[str] = None
    category_distribution: Dict[str, int] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
