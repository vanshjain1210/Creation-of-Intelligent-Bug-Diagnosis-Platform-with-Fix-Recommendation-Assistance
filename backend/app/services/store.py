"""Database-backed repositories and business logic stores."""

import json
from contextlib import contextmanager
from typing import Dict, List, Optional
from datetime import datetime

from app.config.database import SessionLocal
from app.models import (
    Analysis, AnalysisStatus, Bug, BugPriority, BugStatus,
    HistoryEntry, WorkflowStage, AgentResult, BugMetadata
)
from app.models.db_models import DBBug, DBAnalysis, DBAgentResult, DBHistoryEntry
from app.utils.logger import get_logger

logger = get_logger("services.store")


def _parse_json(value, default=None):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default

@contextmanager
def get_db_session():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Database transaction failed: {exc}")
        raise
    finally:
        db.close()


class SQLStore:
    """Thread-safe SQL database store."""

    def _db_to_bug(self, db_bug: DBBug) -> Bug:
        tags_list = []
        if db_bug.tags:
            tags_list = [t.strip() for t in db_bug.tags.split(",") if t.strip()]
        return Bug(
            id=db_bug.id,
            title=db_bug.title,
            description=db_bug.description,
            raw_content=db_bug.raw_content,
            file_path=db_bug.file_path,
            file_name=db_bug.file_name,
            status=_enum_or_default(BugStatus, db_bug.status, BugStatus.OPEN),
            metadata=BugMetadata(
                bug_id=db_bug.id,
                priority=_enum_or_default(BugPriority, db_bug.priority, BugPriority.MEDIUM),
                component=db_bug.component,
                resolution=db_bug.resolution or "",
                root_cause=getattr(db_bug, "root_cause", None) or "",
                source=db_bug.source,
                date=db_bug.date,
                tags=tags_list
            ),
            created_at=db_bug.created_at,
            updated_at=db_bug.updated_at
        )

    def _bug_to_db(self, bug: Bug) -> DBBug:
        tags_str = ""
        if bug.metadata.tags:
            if isinstance(bug.metadata.tags, str):
                tags_str = bug.metadata.tags
            else:
                tags_str = ",".join(bug.metadata.tags)
        return DBBug(
            id=bug.id,
            title=bug.title,
            description=bug.description,
            raw_content=bug.raw_content,
            file_path=bug.file_path,
            file_name=bug.file_name,
            status=bug.status.value,
            priority=bug.metadata.priority.value,
            component=bug.metadata.component,
            resolution=bug.metadata.resolution,
            root_cause=bug.metadata.root_cause or "",
            source=bug.metadata.source,
            date=bug.metadata.date,
            tags=tags_str,
            created_at=bug.created_at or datetime.utcnow(),
            updated_at=bug.updated_at or datetime.utcnow(),
        )

    def _db_to_analysis(self, db_analysis: DBAnalysis) -> Analysis:
        return Analysis(
            id=db_analysis.id,
            bug_id=db_analysis.bug_id,
            status=_enum_or_default(AnalysisStatus, db_analysis.status, AnalysisStatus.PENDING),
            current_stage=_enum_or_default(WorkflowStage, db_analysis.current_stage, WorkflowStage.TRIAGE),
            triage=_parse_json(db_analysis.triage),
            log_analysis=_parse_json(db_analysis.log_analysis),
            duplicate_detection=_parse_json(db_analysis.duplicate_detection),
            root_cause=_parse_json(db_analysis.root_cause),
            remediation=_parse_json(db_analysis.remediation),
            risk_assessment=_parse_json(db_analysis.risk_assessment),
            confidence_scoring=_parse_json(db_analysis.confidence_scoring),
            executive_summary=_parse_json(db_analysis.executive_summary),
            retrieved_context=_parse_json(db_analysis.retrieved_context, []),
            agent_results=[
                AgentResult(
                    agent_name=r.agent_name,
                    stage=_enum_or_default(WorkflowStage, r.stage, WorkflowStage.TRIAGE),
                    output=_parse_json(r.output, {}),
                    confidence=r.confidence,
                    duration_ms=r.duration_ms
                )
                for r in db_analysis.agent_results
            ],
            summary=db_analysis.summary,
            created_at=db_analysis.created_at,
            completed_at=db_analysis.completed_at
        )

    def save_bug(self, bug: Bug) -> Bug:
        with get_db_session() as db:
            existing = db.query(DBBug).filter(DBBug.id == bug.id).first()
            db_bug = self._bug_to_db(bug)
            if existing:
                for key in DBBug.__table__.columns.keys():
                    if key != 'id':
                        setattr(existing, key, getattr(db_bug, key))
                existing.updated_at = datetime.utcnow()
            else:
                db.add(db_bug)
        return bug

    def get_bug(self, bug_id: str) -> Optional[Bug]:
        with get_db_session() as db:
            db_bug = db.query(DBBug).filter(DBBug.id == bug_id).first()
            if not db_bug:
                return None
            return self._db_to_bug(db_bug)

    def save_analysis(self, analysis: Analysis) -> Analysis:
        with get_db_session() as db:
            existing = db.query(DBAnalysis).filter(DBAnalysis.id == analysis.id).first()
            
            triage_str = json.dumps(analysis.triage) if analysis.triage else None
            log_str = json.dumps(analysis.log_analysis) if analysis.log_analysis else None
            dup_str = json.dumps(analysis.duplicate_detection) if analysis.duplicate_detection else None
            rc_str = json.dumps(analysis.root_cause) if analysis.root_cause else None
            rem_str = json.dumps(analysis.remediation) if analysis.remediation else None
            risk_str = json.dumps(analysis.risk_assessment) if analysis.risk_assessment else None
            conf_str = json.dumps(analysis.confidence_scoring) if analysis.confidence_scoring else None
            exec_str = json.dumps(analysis.executive_summary) if analysis.executive_summary else None
            context_str = json.dumps(analysis.retrieved_context) if analysis.retrieved_context else None

            if existing:
                existing.status = analysis.status.value
                existing.current_stage = analysis.current_stage.value
                existing.triage = triage_str
                existing.log_analysis = log_str
                existing.duplicate_detection = dup_str
                existing.root_cause = rc_str
                existing.remediation = rem_str
                existing.risk_assessment = risk_str
                existing.confidence_scoring = conf_str
                existing.executive_summary = exec_str
                existing.retrieved_context = context_str
                existing.summary = analysis.summary
                existing.completed_at = analysis.completed_at
                
                db.query(DBAgentResult).filter(DBAgentResult.analysis_id == analysis.id).delete()
            else:
                existing = DBAnalysis(
                    id=analysis.id,
                    bug_id=analysis.bug_id,
                    status=analysis.status.value,
                    current_stage=analysis.current_stage.value,
                    triage=triage_str,
                    log_analysis=log_str,
                    duplicate_detection=dup_str,
                    root_cause=rc_str,
                    remediation=rem_str,
                    risk_assessment=risk_str,
                    confidence_scoring=conf_str,
                    executive_summary=exec_str,
                    retrieved_context=context_str,
                    summary=analysis.summary,
                    created_at=analysis.created_at,
                    completed_at=analysis.completed_at
                )
                db.add(existing)

            for r in analysis.agent_results:
                db_res = DBAgentResult(
                    analysis_id=analysis.id,
                    agent_name=r.agent_name,
                    stage=r.stage.value,
                    output=json.dumps(r.output),
                    confidence=r.confidence,
                    duration_ms=r.duration_ms
                )
                db.add(db_res)
        return analysis

    def get_analysis(self, analysis_id: str) -> Optional[Analysis]:
        with get_db_session() as db:
            db_analysis = db.query(DBAnalysis).filter(DBAnalysis.id == analysis_id).first()
            if not db_analysis:
                return None
            return self._db_to_analysis(db_analysis)

    def get_analysis_by_bug(self, bug_id: str) -> Optional[Analysis]:
        with get_db_session() as db:
            db_analysis = db.query(DBAnalysis).filter(DBAnalysis.bug_id == bug_id).first()
            if not db_analysis:
                return None
            return self._db_to_analysis(db_analysis)

    def save_history(self, entry: HistoryEntry) -> HistoryEntry:
        with get_db_session() as db:
            existing = db.query(DBHistoryEntry).filter(DBHistoryEntry.id == entry.id).first()
            if existing:
                existing.title = entry.title
                existing.priority = entry.priority.value
                existing.component = entry.component
                existing.status = entry.status.value
                existing.summary = entry.summary
            else:
                db_entry = DBHistoryEntry(
                    id=entry.id,
                    bug_id=entry.bug_id,
                    analysis_id=entry.analysis_id,
                    title=entry.title,
                    priority=entry.priority.value,
                    component=entry.component,
                    status=entry.status.value,
                    summary=entry.summary,
                    created_at=entry.created_at
                )
                db.add(db_entry)
        return entry

    def list_history(self, limit: int = 50, offset: int = 0) -> List[HistoryEntry]:
        with get_db_session() as db:
            db_entries = db.query(DBHistoryEntry).order_by(DBHistoryEntry.created_at.desc()).offset(offset).limit(limit).all()
            return [
                HistoryEntry(
                    id=e.id,
                    bug_id=e.bug_id,
                    analysis_id=e.analysis_id,
                    title=e.title,
                    priority=_enum_or_default(BugPriority, e.priority, BugPriority.MEDIUM),
                    component=e.component,
                    status=_enum_or_default(AnalysisStatus, e.status, AnalysisStatus.PENDING),
                    summary=e.summary,
                    created_at=e.created_at
                )
                for e in db_entries
            ]

    def delete_history(self, entry_id: str) -> bool:
        with get_db_session() as db:
            entry = db.query(DBHistoryEntry).filter(DBHistoryEntry.id == entry_id).first()
            if not entry:
                return False
            db.delete(entry)
            return True

    def list_bugs(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str = "",
        status: str = "",
        category: str = "",
    ) -> List[Bug]:
        with get_db_session() as db:
            query = db.query(DBBug)
            if search:
                like = f"%{search}%"
                query = query.filter(
                    (DBBug.title.ilike(like))
                    | (DBBug.description.ilike(like))
                    | (DBBug.id.ilike(like))
                )
            if status:
                query = query.filter(DBBug.status == status)
            if category:
                query = query.filter(DBBug.component.ilike(f"%{category}%"))
            rows = query.order_by(DBBug.created_at.desc()).offset(offset).limit(limit).all()
            return [self._db_to_bug(row) for row in rows]

    def list_analyses(self, limit: int = 100) -> List[Analysis]:
        with get_db_session() as db:
            rows = db.query(DBAnalysis).order_by(DBAnalysis.created_at.desc()).limit(limit).all()
            return [self._db_to_analysis(row) for row in rows]

    @property
    def bug_count(self) -> int:
        with get_db_session() as db:
            return db.query(DBBug).count()

    @property
    def active_analysis_count(self) -> int:
        with get_db_session() as db:
            return db.query(DBAnalysis).filter(DBAnalysis.status == "in_progress").count()

    @property
    def history_count(self) -> int:
        with get_db_session() as db:
            return db.query(DBHistoryEntry).count()


store = SQLStore()
