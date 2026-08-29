"""Phase 4 schemas — root cause, ranked fixes, risk score."""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.phase3 import Phase3AnalyzeResponse


class RootCauseView(BaseModel):
    probable_cause: str
    confidence: float
    failure_location: str = "unknown"
    evidence: List[str] = Field(default_factory=list)
    explanation: str = ""
    category: str = "unknown"


class RankedFix(BaseModel):
    rank: int
    title: str
    confidence: float
    relevance: float
    difficulty: str = "medium"
    estimated_time: str = "2-4h"
    steps: List[str] = Field(default_factory=list)
    code_suggestion: str = ""
    risks: List[str] = Field(default_factory=list)
    prevention: List[str] = Field(default_factory=list)
    testing: List[str] = Field(default_factory=list)


class RiskScoreView(BaseModel):
    score: int = Field(ge=0, le=100)
    level: str
    factors: List[str] = Field(default_factory=list)
    summary: str = ""


class Phase4AnalyzeResponse(Phase3AnalyzeResponse):
    phase: int = 4
    root_cause: RootCauseView
    ranked_fixes: List[RankedFix] = Field(default_factory=list)
    risk: RiskScoreView
    next_phase: str = "Phase 5: dashboard polish, history filters, PDF report, GitHub import."
