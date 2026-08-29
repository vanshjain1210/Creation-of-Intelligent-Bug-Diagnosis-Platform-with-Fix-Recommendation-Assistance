"""Analysis orchestration service."""

from datetime import datetime
from typing import Optional

from app.models import Analysis, AnalysisStatus, Bug, BugPriority, BugStatus, HistoryEntry
from app.services.bug_service import BugService
from app.services.store import store
from app.utils.exceptions import NotFoundError
from app.utils.logger import get_logger

logger = get_logger("services.analysis")


class AnalysisService:
    def __init__(self) -> None:
        self.bug_service = BugService()
        self._orchestrator = None

    @property
    def orchestrator(self):
        if self._orchestrator is None:
            from app.agents.workflow import WorkflowOrchestrator

            self._orchestrator = WorkflowOrchestrator()
        return self._orchestrator

    def create_analysis(self, bug: Bug) -> Analysis:
        analysis = Analysis(bug_id=bug.id, status=AnalysisStatus.PENDING)
        store.save_analysis(analysis)
        return analysis

    def run_analysis(
        self,
        bug_id: str,
        use_mmr: bool = True,
        retrieval_top_k: int | None = None,
    ) -> Analysis:
        bug = self.bug_service.get_bug(bug_id)
        bug.status = BugStatus.PROCESSING
        store.save_bug(bug)

        analysis = store.get_analysis_by_bug(bug_id)
        if not analysis:
            analysis = self.create_analysis(bug)

        self.bug_service.preprocess(bug)

        try:
            analysis = self.orchestrator.run(
                bug=bug,
                analysis=analysis,
                use_mmr=use_mmr,
                retrieval_top_k=retrieval_top_k,
            )
            bug.status = BugStatus.ANALYZED
            if analysis.triage:
                raw_priority = str(analysis.triage.get("priority") or "unknown").lower()
                try:
                    bug.metadata.priority = BugPriority(raw_priority)
                except ValueError:
                    bug.metadata.priority = BugPriority.UNKNOWN
                bug.metadata.component = analysis.triage.get("component", bug.metadata.component)
                bug.metadata.tags = analysis.triage.get("tags", bug.metadata.tags)
        except Exception as exc:
            logger.error("Analysis failed for bug %s: %s", bug_id, exc)
            analysis.status = AnalysisStatus.FAILED
            bug.status = BugStatus.FAILED
            raise
        finally:
            bug.updated_at = datetime.utcnow()
            store.save_bug(bug)
            store.save_analysis(analysis)

        self._record_history(bug, analysis)
        return analysis

    def get_analysis(self, analysis_id: str) -> Analysis:
        analysis = store.get_analysis(analysis_id)
        if not analysis:
            raise NotFoundError(f"Analysis {analysis_id} not found.")
        return analysis

    def get_analysis_by_bug(self, bug_id: str) -> Analysis:
        analysis = store.get_analysis_by_bug(bug_id)
        if not analysis:
            raise NotFoundError(f"No analysis found for bug {bug_id}.")
        return analysis

    @staticmethod
    def _record_history(bug: Bug, analysis: Analysis) -> None:
        entry = HistoryEntry(
            bug_id=bug.id,
            analysis_id=analysis.id,
            title=bug.title,
            priority=bug.metadata.priority,
            component=bug.metadata.component or "",
            status=analysis.status,
            summary=analysis.summary,
        )
        store.save_history(entry)
