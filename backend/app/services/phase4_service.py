"""Phase 4: root cause + ranked fixes + risk score on top of Phase 3."""

from __future__ import annotations

from typing import List, Optional

from app.schemas.phase2 import Phase2PipelineStage
from app.schemas.phase4 import (
    Phase4AnalyzeResponse,
    RankedFix,
    RiskScoreView,
    RootCauseView,
)
from app.services.phase3_service import Phase3Service
from app.utils.logger import get_logger

logger = get_logger("services.phase4")

SEVERITY_SCORE = {"Critical": 40, "High": 30, "Medium": 18, "Low": 8}
PRIORITY_SCORE = {"P0": 25, "P1": 18, "P2": 10, "P3": 4}


class Phase4Service:
    def __init__(self) -> None:
        self.phase3 = Phase3Service()

    def analyze(
        self,
        *,
        title: str,
        description: str = "",
        error_logs: str = "",
        stack_trace: str = "",
        file_text: str = "",
        file_name: Optional[str] = None,
    ) -> Phase4AnalyzeResponse:
        p3 = self.phase3.analyze(
            title=title,
            description=description,
            error_logs=error_logs,
            stack_trace=stack_trace,
            file_text=file_text,
            file_name=file_name,
        )

        root = self._root_cause(p3)
        fixes = self._ranked_fixes(p3, root)
        risk = self._risk_score(p3, root)

        pipeline = list(p3.pipeline)
        pipeline.extend(
            [
                Phase2PipelineStage(name="Root Cause", status="completed", message=root.probable_cause[:80]),
                Phase2PipelineStage(name="Fix Ranking", status="completed", message=f"{len(fixes)} ranked fixes"),
                Phase2PipelineStage(name="Risk Score", status="completed", message=f"{risk.score} ({risk.level})"),
            ]
        )

        payload = p3.model_dump()
        payload.update(
            {
                "phase": 4,
                "message": "Phase 4 complete (root cause + ranked fixes + risk score).",
                "pipeline": [s.model_dump() if hasattr(s, "model_dump") else s for s in pipeline],
                "root_cause": root.model_dump(),
                "ranked_fixes": [f.model_dump() for f in fixes],
                "risk": risk.model_dump(),
                "next_phase": "Phase 5: dashboard polish, history filters, PDF report, GitHub import.",
            }
        )
        logger.info("Phase 4 done bug=%s risk=%s", p3.bug_id, risk.score)
        return Phase4AnalyzeResponse(**payload)

    def _root_cause(self, p3) -> RootCauseView:
        log = p3.log_intelligence
        triage = p3.triage
        similar = p3.similar_bugs or []
        top = similar[0] if similar else None

        evidence: List[str] = []
        if log.exception_type and log.exception_type != "UnknownException":
            evidence.append(f"Exception `{log.exception_type}` in logs")
        if log.failure_location and log.failure_location != "unknown":
            evidence.append(f"Failure at `{log.failure_location}`")
        if log.line_number:
            evidence.append(f"Line {log.line_number} in `{log.file_name}`")
        if log.error_message:
            evidence.append(f"Error: {log.error_message[:160]}")
        if top and top.similarity_percent >= 55:
            evidence.append(
                f"Historical match `{top.title}` ({top.similarity_percent}% similar)"
            )
            if top.root_cause:
                evidence.append(f"Prior root cause: {top.root_cause}")

        if top and top.root_cause and top.similarity_percent >= 70:
            cause = top.root_cause
            conf = min(0.95, 0.55 + top.similarity / 2)
            category = top.component or triage.category
            explanation = (
                f"High similarity to a resolved bug suggests the same failure mode. "
                f"Current stack points to {log.failure_location}."
            )
        else:
            exc = log.exception_type or "runtime error"
            loc = log.failure_location if log.failure_location != "unknown" else (
                f"{log.file_name}:{log.line_number}" if log.line_number else triage.category
            )
            cause = f"{exc} likely due to unhandled null/invalid state near {loc}"
            if "timeout" in (log.error_message or "").lower() or "timeout" in exc.lower():
                cause = f"Upstream/timeout failure ({exc}) near {loc}"
            if "pool" in exc.lower() or "database" in triage.category.lower():
                cause = f"Resource/connection exhaustion ({exc}) in {triage.category}"
            if "auth" in triage.category.lower() or "jwt" in exc.lower():
                cause = f"Authentication/session failure ({exc})"
            conf = min(0.9, 0.5 + (log.confidence or 0) * 0.3 + (triage.confidence or 0) * 0.2)
            category = triage.category
            explanation = (
                f"Triage marked this as {triage.severity}/{triage.priority} in {triage.category}. "
                f"Log parsing localized the failure to {loc}."
            )

        if not evidence:
            evidence = ["Insufficient structured log evidence; based on triage heuristics."]

        return RootCauseView(
            probable_cause=cause,
            confidence=round(conf, 3),
            failure_location=log.failure_location or f"{log.file_name}:{log.line_number or '?'}",
            evidence=evidence[:6],
            explanation=explanation,
            category=category or "unknown",
        )

    def _ranked_fixes(self, p3, root: RootCauseView) -> List[RankedFix]:
        similar = p3.similar_bugs or []
        top = similar[0] if similar else None
        log = p3.log_intelligence
        fixes: List[RankedFix] = []

        if top and top.resolution and top.similarity_percent >= 60:
            fixes.append(
                RankedFix(
                    rank=1,
                    title="Apply known resolution from similar bug",
                    confidence=min(0.95, 0.6 + top.similarity / 2),
                    relevance=top.similarity,
                    difficulty="low" if top.similarity_percent >= 80 else "medium",
                    estimated_time="1-2h",
                    steps=[
                        f"Review historical bug: {top.title}",
                        f"Apply: {top.resolution}",
                        "Validate against current stack trace",
                        "Add regression coverage for this path",
                    ],
                    code_suggestion=top.resolution,
                    risks=["Historical fix may not fully match current code paths"],
                    prevention=["Document this pattern in the knowledge base"],
                    testing=["Re-run failing scenario", "Add unit/integration test"],
                )
            )

        loc = root.failure_location
        fixes.append(
            RankedFix(
                rank=len(fixes) + 1,
                title="Hotfix at failure location",
                confidence=0.78,
                relevance=0.85,
                difficulty="medium",
                estimated_time="2-4h",
                steps=[
                    f"Inspect `{loc}` and surrounding null/error handling",
                    f"Guard against `{log.exception_type}` inputs/state",
                    "Log structured context before the failing call",
                    "Deploy hotfix behind feature flag if high risk",
                ],
                code_suggestion=(
                    f"// Near {loc}\n"
                    f"if (value == null) throw new IllegalStateException(\"missing required state\");\n"
                    f"// or return a controlled error instead of {log.exception_type}"
                ),
                risks=["Hotfix may mask deeper design issue"],
                prevention=["Add input validation at API boundary"],
                testing=["Reproduce with same payload/logs", "Null/empty edge-case tests"],
            )
        )

        fixes.append(
            RankedFix(
                rank=len(fixes) + 1,
                title="Hardening & prevention",
                confidence=0.7,
                relevance=0.65,
                difficulty="medium",
                estimated_time="4-8h",
                steps=[
                    "Add monitoring/alerts for this exception signature",
                    "Improve error messages with correlation IDs",
                    "Review similar module paths for the same pattern",
                    "Update runbook with recovery steps",
                ],
                prevention=[
                    "Contract tests for critical APIs",
                    "Circuit breaker / retries for upstream timeouts",
                ],
                testing=["Chaos/timeout simulation if infrastructure-related"],
                risks=["Broader changes need careful rollout"],
            )
        )

        for i, f in enumerate(fixes, start=1):
            f.rank = i
        return fixes

    def _risk_score(self, p3, root: RootCauseView) -> RiskScoreView:
        triage = p3.triage
        recurrence = p3.recurrence
        similar = p3.similar_bugs or []

        score = 0
        factors: List[str] = []

        sev = SEVERITY_SCORE.get(triage.severity, 15)
        score += sev
        factors.append(f"Severity {triage.severity} (+{sev})")

        pri = PRIORITY_SCORE.get(triage.priority, 8)
        score += pri
        factors.append(f"Priority {triage.priority} (+{pri})")

        rc = int(root.confidence * 15)
        score += rc
        factors.append(f"Root-cause confidence {int(root.confidence * 100)}% (+{rc})")

        if p3.log_intelligence.exception_type not in ("", "UnknownException", "Unknown"):
            score += 8
            factors.append("Exception evidence present (+8)")
        if p3.log_intelligence.failure_location not in ("", "unknown"):
            score += 7
            factors.append("Failure localized (+7)")

        if recurrence and recurrence.is_recurring:
            bump = min(15, 5 + recurrence.similar_match_count * 3)
            score += bump
            factors.append(f"Recurring issue (+{bump})")
        elif similar and similar[0].similarity_percent >= 75:
            score += 10
            factors.append(f"Strong duplicate signal {similar[0].similarity_percent}% (+10)")

        score = max(0, min(100, score))
        if score >= 85:
            level = "Critical"
        elif score >= 70:
            level = "High"
        elif score >= 45:
            level = "Medium"
        elif score >= 25:
            level = "Low"
        else:
            level = "Minimal"

        return RiskScoreView(
            score=score,
            level=level,
            factors=factors,
            summary=f"Bug risk {score}/100 ({level}) based on severity, priority, recurrence, and evidence.",
        )
