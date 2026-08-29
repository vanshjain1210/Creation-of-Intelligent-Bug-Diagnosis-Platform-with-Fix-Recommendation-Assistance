"""Phase 3 service: Phase 2 analysis + FAISS similar bugs + recurrence."""

from __future__ import annotations

from collections import Counter
from typing import List, Optional

from app.schemas.phase2 import Phase2PipelineStage
from app.schemas.phase3 import (
    Phase3AnalyzeResponse,
    RecurrenceAnalysis,
    SimilarBugMatch,
)
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.phase2_service import Phase2Service
from app.utils.logger import get_logger

logger = get_logger("services.phase3")

DUPLICATE_THRESHOLD = 0.78
RECURRENCE_THRESHOLD = 0.55


class Phase3Service:
    def __init__(self) -> None:
        self.phase2 = Phase2Service()
        self.kb = KnowledgeBaseService()

    def analyze(
        self,
        *,
        title: str,
        description: str = "",
        error_logs: str = "",
        stack_trace: str = "",
        file_text: str = "",
        file_name: Optional[str] = None,
        top_k: int = 5,
    ) -> Phase3AnalyzeResponse:
        seed_info = self.kb.ensure_seeded()
        try:
            self.kb.sync_from_sql(limit=50)
        except Exception as exc:
            logger.warning("SQL sync into FAISS skipped: %s", exc)

        phase2_result = self.phase2.analyze(
            title=title,
            description=description,
            error_logs=error_logs,
            stack_trace=stack_trace,
            file_text=file_text,
            file_name=file_name,
        )

        query = " ".join(
            part
            for part in [
                title,
                description,
                error_logs,
                stack_trace,
                phase2_result.log_intelligence.exception_type,
                phase2_result.log_intelligence.file_name,
                phase2_result.triage.category,
            ]
            if part
        )

        raw_matches = self.kb.search_similar(query, top_k=top_k + 3)
        filtered = [m for m in raw_matches if m.get("id") != phase2_result.bug_id][:top_k]

        similar: List[SimilarBugMatch] = []
        for match in filtered:
            sim = float(match.get("similarity") or 0.0)
            similar.append(
                SimilarBugMatch(
                    bug_id=str(match.get("id") or "unknown"),
                    title=str(match.get("title") or "Untitled"),
                    similarity=round(sim, 4),
                    similarity_percent=round(sim * 100, 1),
                    component=str(match.get("component") or ""),
                    exception_type=str(match.get("exception_type") or ""),
                    root_cause=str(match.get("root_cause") or ""),
                    resolution=str(match.get("resolution") or ""),
                    status=str(match.get("status") or ""),
                    is_likely_duplicate=sim >= DUPLICATE_THRESHOLD,
                )
            )

        recurrence = self._build_recurrence(similar, phase2_result)

        try:
            self.kb.index_bug(
                bug_id=phase2_result.bug_id,
                title=phase2_result.title,
                content=self.phase2.compose_content(
                    description=description,
                    error_logs=error_logs,
                    stack_trace=stack_trace,
                    file_text=file_text,
                ),
                component=phase2_result.triage.category,
                exception_type=phase2_result.log_intelligence.exception_type,
                status="analyzed",
            )
        except Exception as exc:
            logger.warning("Failed to index current bug into FAISS: %s", exc)

        pipeline = list(phase2_result.pipeline)
        pipeline.extend(
            [
                Phase2PipelineStage(
                    name="FAISS Retrieval",
                    status="completed",
                    message=f"{len(similar)} similar bugs ({self.kb.backend})",
                ),
                Phase2PipelineStage(
                    name="Recurrence Check",
                    status="completed",
                    message=recurrence.pattern_summary or "No recurrence pattern",
                ),
            ]
        )

        payload = phase2_result.model_dump()
        payload.update(
            {
                "phase": 3,
                "message": "Phase 3 analysis complete (triage + FAISS similar bugs + recurrence).",
                "pipeline": [s.model_dump() if hasattr(s, "model_dump") else s for s in pipeline],
                "similar_bugs": [s.model_dump() for s in similar],
                "recurrence": recurrence.model_dump(),
                "rag_backend": self.kb.backend,
                "knowledge_base_size": self.kb.size,
                "next_phase": (
                    "Phase 4 will add explainable root cause, ranked fixes, and risk score."
                ),
            }
        )
        logger.info(
            "Phase 3 done bug=%s similar=%d recurring=%s seed=%s",
            phase2_result.bug_id,
            len(similar),
            recurrence.is_recurring,
            seed_info,
        )
        return Phase3AnalyzeResponse(**payload)

    def _build_recurrence(self, similar: List[SimilarBugMatch], phase2_result) -> RecurrenceAnalysis:
        recurring = [s for s in similar if s.similarity >= RECURRENCE_THRESHOLD]
        if not recurring:
            return RecurrenceAnalysis(
                is_recurring=False,
                occurrence_count=1,
                similar_match_count=0,
                pattern_summary="No recurring historical pattern above threshold.",
                confidence=0.4,
            )

        components = [c for c in (s.component for s in recurring) if c]
        exceptions = [
            e for e in (s.exception_type for s in recurring) if e and e != "Unknown"
        ]
        top_components = [c for c, _ in Counter(components).most_common(3)]
        top_exceptions = [e for e, _ in Counter(exceptions).most_common(3)]

        current_exc = phase2_result.log_intelligence.exception_type
        current_cat = phase2_result.triage.category
        is_recurring = len(recurring) >= 2 or (
            len(recurring) >= 1 and recurring[0].similarity >= DUPLICATE_THRESHOLD
        )

        parts = [
            f"{len(recurring)} historical match(es) ≥ {int(RECURRENCE_THRESHOLD * 100)}% similar."
        ]
        if top_exceptions:
            parts.append(f"Recurring exception(s): {', '.join(top_exceptions)}.")
        if top_components:
            parts.append(f"Recurring component(s): {', '.join(top_components)}.")
        if current_exc and current_exc in top_exceptions:
            parts.append(f"Current exception `{current_exc}` has appeared before.")
        if current_cat and current_cat.lower() in [c.lower() for c in top_components]:
            parts.append(f"Component `{current_cat}` shows repeated issues.")

        confidence = min(0.95, 0.5 + 0.1 * len(recurring) + 0.15 * recurring[0].similarity)
        return RecurrenceAnalysis(
            is_recurring=is_recurring,
            occurrence_count=len(recurring) + 1,
            similar_match_count=len(recurring),
            recurring_components=top_components,
            recurring_exceptions=top_exceptions,
            pattern_summary=" ".join(parts),
            confidence=round(confidence, 3),
        )
