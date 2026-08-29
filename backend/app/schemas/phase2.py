"""Phase 2 analysis schemas — bug submit + log parse + triage."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Phase2PipelineStage(BaseModel):
    name: str
    status: str  # pending | running | completed | failed
    message: str = ""


class Phase2TriageView(BaseModel):
    severity: str
    priority: str
    category: str
    confidence: float
    reasoning: str = ""
    summary: str = ""
    tags: List[str] = Field(default_factory=list)
    severity_score: int = 5
    business_impact: str = ""
    recommended_assignee_team: str = ""


class Phase2LogIntelligence(BaseModel):
    exception_type: str = "UnknownException"
    error_message: str = ""
    language: str = "unknown"
    file_name: str = "unknown"
    file_path: str = "unknown"
    method_name: str = "unknown"
    line_number: Optional[int] = None
    failure_location: str = "unknown"
    has_stack_trace: bool = False
    error_count: int = 0
    log_format: str = "plain_text"
    stack_trace_summary: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class Phase2AnalyzeResponse(BaseModel):
    success: bool = True
    phase: int = 2
    message: str
    bug_id: str
    analysis_id: str
    title: str
    pipeline: List[Phase2PipelineStage] = Field(default_factory=list)
    triage: Phase2TriageView
    log_intelligence: Phase2LogIntelligence
    overall_confidence: float = 0.0
    overall_summary: str = ""
    processed_at: datetime
    next_phase: str = (
        "Phase 3 will add FAISS RAG, duplicate detection, recurrence, "
        "root cause, ranked fixes, and risk score."
    )
    raw_triage: Dict[str, Any] = Field(default_factory=dict)
    raw_log_analysis: Dict[str, Any] = Field(default_factory=dict)
