"""Phase 3 schemas — RAG similar bugs + recurrence detection."""

from typing import List

from pydantic import BaseModel, Field

from app.schemas.phase2 import Phase2AnalyzeResponse


class SimilarBugMatch(BaseModel):
    bug_id: str
    title: str
    similarity: float
    similarity_percent: float
    component: str = ""
    exception_type: str = ""
    root_cause: str = ""
    resolution: str = ""
    status: str = ""
    is_likely_duplicate: bool = False


class RecurrenceAnalysis(BaseModel):
    is_recurring: bool = False
    occurrence_count: int = 0
    similar_match_count: int = 0
    recurring_components: List[str] = Field(default_factory=list)
    recurring_exceptions: List[str] = Field(default_factory=list)
    pattern_summary: str = ""
    confidence: float = 0.0


class Phase3AnalyzeResponse(Phase2AnalyzeResponse):
    phase: int = 3
    similar_bugs: List[SimilarBugMatch] = Field(default_factory=list)
    recurrence: RecurrenceAnalysis = Field(default_factory=RecurrenceAnalysis)
    rag_backend: str = "faiss"
    knowledge_base_size: int = 0
    next_phase: str = (
        "Phase 4 will add explainable root cause, ranked fixes, and risk score."
    )


class KnowledgeBaseListResponse(BaseModel):
    total: int
    backend: str
    items: List[dict]


class KnowledgeBaseAddRequest(BaseModel):
    title: str
    description: str = ""
    component: str = ""
    exception_type: str = ""
    root_cause: str = ""
    resolution: str = ""


class KnowledgeBaseAddResponse(BaseModel):
    success: bool = True
    message: str
    item: dict
