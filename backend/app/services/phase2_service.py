"""Phase 2 service: bug ingest + log parsing + AI triage."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.agents.orchestrator import BugAnalysisOrchestrator
from app.models import Analysis, AnalysisStatus, BugPriority, BugStatus, HistoryEntry, WorkflowStage
from app.schemas.phase2 import (
    Phase2AnalyzeResponse,
    Phase2LogIntelligence,
    Phase2PipelineStage,
    Phase2TriageView,
)
from app.services.bug_service import BugService
from app.services.store import store
from app.utils.logger import get_logger

logger = get_logger("services.phase2")

PRIORITY_TO_P = {
    BugPriority.CRITICAL: "P0",
    BugPriority.HIGH: "P1",
    BugPriority.MEDIUM: "P2",
    BugPriority.LOW: "P3",
    BugPriority.UNKNOWN: "P3",
}

CATEGORY_MAP = {
    "api": "API",
    "database": "Database",
    "frontend": "Frontend",
    "backend": "Backend",
    "network": "Infrastructure",
    "payment": "API",
    "auth": "Authentication",
    "authentication": "Authentication",
    "security": "Security",
    "performance": "Performance",
    "ui": "Frontend",
    "infra": "Infrastructure",
    "infrastructure": "Infrastructure",
}


class Phase2Service:
    """Runs Phase 2 pipeline without full RAG / duplicate / remediation."""

    def __init__(self) -> None:
        self.bug_service = BugService()
        self.orchestrator = BugAnalysisOrchestrator()

    def compose_content(
        self,
        *,
        description: str = "",
        error_logs: str = "",
        stack_trace: str = "",
        file_text: str = "",
    ) -> str:
        parts: List[str] = []
        if description and description.strip():
            parts.append(description.strip())
        if error_logs and error_logs.strip():
            parts.append(f"Error logs:\n{error_logs.strip()}")
        if stack_trace and stack_trace.strip():
            parts.append(f"Stack trace:\n{stack_trace.strip()}")
        if file_text and file_text.strip():
            parts.append(f"Uploaded file content:\n{file_text.strip()}")
        return "\n\n".join(parts).strip()

    def analyze(
        self,
        *,
        title: str,
        description: str = "",
        error_logs: str = "",
        stack_trace: str = "",
        file_text: str = "",
        file_name: Optional[str] = None,
    ) -> Phase2AnalyzeResponse:
        content = self.compose_content(
            description=description,
            error_logs=error_logs,
            stack_trace=stack_trace,
            file_text=file_text,
        )
        if not content:
            from app.utils.exceptions import ValidationError

            raise ValidationError(
                "Provide a description, error logs, stack trace, or an uploaded file."
            )

        pipeline: List[Phase2PipelineStage] = [
            Phase2PipelineStage(name="Ingest", status="completed", message="Bug report accepted"),
            Phase2PipelineStage(name="Log Analysis", status="running", message="Parsing logs and stack traces"),
            Phase2PipelineStage(name="Triage", status="pending", message="Waiting"),
            Phase2PipelineStage(name="Persist", status="pending", message="Waiting"),
        ]

        bug = self.bug_service.create_bug_from_text(
            content=content,
            title=title.strip() or None,
            description=description or content[:500],
            file_name=file_name,
        )
        analysis = Analysis(bug_id=bug.id, status=AnalysisStatus.IN_PROGRESS)
        store.save_analysis(analysis)
        bug.status = BugStatus.PROCESSING
        store.save_bug(bug)

        try:
            unified = self.orchestrator.run(
                raw_input=content,
                source_file=file_name or "inline",
                title=bug.title,
            )
            pipeline[1] = Phase2PipelineStage(
                name="Log Analysis",
                status="completed",
                message=f"Detected {unified.log_analysis.exception_type}",
            )
            pipeline[2] = Phase2PipelineStage(
                name="Triage",
                status="completed",
                message=f"{unified.triage.priority.value} / score {unified.triage.severity_score}",
            )

            triage_view = self._map_triage(unified.triage, content)
            log_view = self._map_log(unified.log_analysis, content)

            analysis.status = AnalysisStatus.COMPLETED
            analysis.triage = unified.triage.model_dump(mode="json")
            analysis.log_analysis = unified.log_analysis.model_dump(mode="json")
            analysis.summary = unified.overall_summary
            analysis.completed_at = datetime.now(timezone.utc)
            analysis.current_stage = WorkflowStage.COMPLETE

            bug.status = BugStatus.ANALYZED
            try:
                bug.metadata.priority = unified.triage.priority
            except Exception:
                bug.metadata.priority = BugPriority.UNKNOWN
            bug.metadata.component = unified.triage.component
            bug.metadata.tags = list(unified.triage.tags or [])
            bug.updated_at = datetime.utcnow()

            store.save_bug(bug)
            store.save_analysis(analysis)
            store.save_history(
                HistoryEntry(
                    bug_id=bug.id,
                    analysis_id=analysis.id,
                    title=bug.title,
                    priority=bug.metadata.priority,
                    component=bug.metadata.component or "",
                    status=analysis.status,
                    summary=analysis.summary or unified.overall_summary,
                )
            )

            pipeline[3] = Phase2PipelineStage(
                name="Persist",
                status="completed",
                message=f"Saved bug {bug.id[:8]}",
            )

            return Phase2AnalyzeResponse(
                success=True,
                phase=2,
                message="Phase 2 analysis complete (log parsing + triage).",
                bug_id=bug.id,
                analysis_id=analysis.id if hasattr(analysis, "id") else unified.analysis_id,
                title=bug.title,
                pipeline=pipeline,
                triage=triage_view,
                log_intelligence=log_view,
                overall_confidence=unified.overall_confidence,
                overall_summary=unified.overall_summary,
                processed_at=unified.processed_at,
                raw_triage=unified.triage.model_dump(mode="json"),
                raw_log_analysis=unified.log_analysis.model_dump(mode="json"),
            )
        except Exception as exc:
            logger.exception("Phase 2 analysis failed: %s", exc)
            analysis.status = AnalysisStatus.FAILED
            bug.status = BugStatus.FAILED
            store.save_bug(bug)
            store.save_analysis(analysis)
            for stage in pipeline:
                if stage.status in ("running", "pending"):
                    stage.status = "failed"
                    stage.message = str(exc)
            raise

    @staticmethod
    def _severity_label(score: int, priority: BugPriority) -> str:
        if priority == BugPriority.CRITICAL or score >= 9:
            return "Critical"
        if priority == BugPriority.HIGH or score >= 7:
            return "High"
        if priority == BugPriority.LOW or score <= 3:
            return "Low"
        return "Medium"

    @staticmethod
    def _category_label(component: str) -> str:
        key = (component or "other").strip().lower()
        return CATEGORY_MAP.get(key, component.title() if component else "Other")

    def _map_triage(self, triage, content: str = "") -> Phase2TriageView:
        priority = triage.priority if isinstance(triage.priority, BugPriority) else BugPriority.UNKNOWN
        category = self._category_label(triage.component)
        if category in ("Unknown", "Other") or (triage.component or "").lower() in ("", "unknown"):
            category = self._infer_category(content)
        return Phase2TriageView(
            severity=self._severity_label(triage.severity_score, priority),
            priority=PRIORITY_TO_P.get(priority, "P3"),
            category=category,
            confidence=float(triage.confidence or 0.0),
            reasoning=triage.reasoning or "",
            summary=triage.summary or "",
            tags=list(triage.tags or []),
            severity_score=int(triage.severity_score or 5),
            business_impact=triage.business_impact or "",
            recommended_assignee_team=triage.recommended_assignee_team or "",
        )

    @staticmethod
    def _infer_category(content: str) -> str:
        lower = (content or "").lower()
        if any(k in lower for k in ("sql", "database", "jdbc", "mongo", "postgres", "sqlite")):
            return "Database"
        if any(k in lower for k in ("auth", "jwt", "oauth", "login", "token")):
            return "Authentication"
        if any(k in lower for k in ("xss", "csrf", "injection", "vulnerability")):
            return "Security"
        if any(k in lower for k in ("timeout", "latency", "slow", "memory", "cpu")):
            return "Performance"
        if any(k in lower for k in ("react", "dom", "css", "frontend", "ui")):
            return "Frontend"
        if any(k in lower for k in ("http", "api", "rest", "graphql", "endpoint")):
            return "API"
        if any(k in lower for k in ("nullpointer", "exception", "traceback", "stack")):
            return "Backend"
        return "Other"

    def _map_log(self, log, content: str) -> Phase2LogIntelligence:
        file_name = "unknown"
        if log.file_names:
            file_name = log.file_names[0]
        elif log.affected_code_path and log.affected_code_path != "unknown":
            file_name = log.affected_code_path.split("/")[-1].split("\\")[-1]

        line_number = log.line_numbers[0] if log.line_numbers else None
        method_name, parsed_line = self._extract_method_and_line(content)
        if line_number is None and parsed_line is not None:
            line_number = parsed_line

        error_message = ""
        if log.error_samples:
            error_message = log.error_samples[0]
        elif log.detected_errors:
            error_message = log.detected_errors[0]

        failure = log.failure_point or "unknown"
        if failure == "unknown" and method_name != "unknown":
            failure = method_name
            if line_number is not None:
                failure = f"{method_name} (line {line_number})"

        return Phase2LogIntelligence(
            exception_type=log.exception_type or "UnknownException",
            error_message=error_message,
            language=self._detect_language(content, file_name),
            file_name=file_name,
            file_path=log.affected_code_path or file_name,
            method_name=method_name if method_name != "unknown" else (
                failure.split("(")[0].strip() if failure != "unknown" else "unknown"
            ),
            line_number=line_number,
            failure_location=failure,
            has_stack_trace=bool(log.has_stack_trace),
            error_count=int(log.error_count or 0),
            log_format=log.log_format or "plain_text",
            stack_trace_summary=list(log.stack_trace_lines or [])[:8],
            confidence=float(log.confidence or 0.0),
        )

    @staticmethod
    def _detect_language(content: str, file_name: str) -> str:
        name = (file_name or "").lower()
        ext_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".jsx": "JavaScript",
            ".java": "Java",
            ".go": "Go",
            ".rs": "Rust",
            ".c": "C",
            ".cpp": "C++",
            ".cc": "C++",
            ".h": "C/C++",
        }
        for ext, lang in ext_map.items():
            if name.endswith(ext):
                return lang

        lower = content.lower()
        if "traceback (most recent call last)" in lower or "file \"" in content:
            return "Python"
        if "at " in content and ".java:" in content:
            return "Java"
        if "typeerror:" in lower or "referenceerror:" in lower or "node:" in lower:
            return "JavaScript/Node.js"
        if "panic:" in lower or "goroutine" in lower:
            return "Go"
        if "thread '" in lower and "panicked at" in lower:
            return "Rust"
        if "segmentation fault" in lower or "core dumped" in lower:
            return "C/C++"
        return "Generic"

    @staticmethod
    def _extract_method_and_line(content: str) -> Tuple[str, Optional[int]]:
        # Java / JS style: at com.foo.Bar.method(File.java:42)
        m = re.search(r"at\s+([\w.$]+)\.([\w<>]+)\(([^:]+):(\d+)\)", content)
        if m:
            return m.group(2), int(m.group(4))

        # Python style: File "path.py", line 42, in method_name
        m = re.search(r'File\s+"[^"]+",\s+line\s+(\d+),\s+in\s+(\w+)', content)
        if m:
            return m.group(2), int(m.group(1))

        # Go style: path/file.go:42
        m = re.search(r"([\w./\\-]+\.go):(\d+)", content)
        if m:
            return "unknown", int(m.group(2))

        return "unknown", None
