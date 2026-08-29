"""Phase 1 request/response schemas (scaffold only)."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Phase1TestResponse(BaseModel):
    ok: bool = True
    phase: int = 1
    message: str
    service: str = "Smart Bug Analyzer API"


class Phase1AnalyzeRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Bug title")
    description: Optional[str] = ""
    error_logs: Optional[str] = ""
    stack_trace: Optional[str] = ""


class Phase1AnalyzeResponse(BaseModel):
    success: bool = True
    phase: int = 1
    message: str
    received: Dict[str, Any]
    pipeline_status: str = "scaffolded"
    agents: List[str] = Field(
        default_factory=lambda: [
            "triage",
            "log_analysis",
            "duplicate_detection",
            "root_cause",
            "remediation",
        ]
    )
    next_phase: str = "Full multi-agent analysis will be implemented in Phase 2+"
