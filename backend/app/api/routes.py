"""FastAPI route definitions."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.dependencies import (
    get_analysis_service,
    get_bug_service,
    get_history_service,
)
from app.config.settings import get_settings
from app.models import AppSettings
from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import VectorStore
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnalysisResponse,
    AgentOutputSchema,
    BugResponse,
    BugSubmitRequest,
    BugSubmitResponse,
    DashboardResponse,
    HealthResponse,
    HistoryResponse,
    KnowledgeBaseItem,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
    ServiceStatus,
    SettingsResponse,
    StatusResponse,
)
from app.schemas.phase2 import Phase2AnalyzeResponse
from app.schemas.phase4 import Phase4AnalyzeResponse
from app.schemas.phase3 import (
    KnowledgeBaseAddRequest,
    KnowledgeBaseAddResponse,
    KnowledgeBaseListResponse,
    Phase3AnalyzeResponse,
)
from app.schemas.phase1 import (
    Phase1AnalyzeRequest,
    Phase1AnalyzeResponse,
    Phase1TestResponse,
)
from app.services.analysis_service import AnalysisService
from app.services.bug_service import BugService
from app.services.history_service import HistoryService
from app.services.store import store
from app.utils.logger import get_logger

logger = get_logger("api.routes")
router = APIRouter()


def _bug_to_response(bug) -> BugResponse:
    return BugResponse(
        id=bug.id,
        title=bug.title,
        description=bug.description,
        raw_content=bug.raw_content,
        file_name=bug.file_name,
        status=bug.status,
        metadata=bug.metadata.model_dump(),
        created_at=bug.created_at,
    )


def _compose_bug_content(
    content: Optional[str],
    description: Optional[str],
    error_message: Optional[str],
    stack_trace: Optional[str],
) -> Optional[str]:
    """Merge form fields into a single report body for the existing pipeline."""
    parts = []
    if description:
        parts.append(description.strip())
    if error_message:
        parts.append(f"Error message:\n{error_message.strip()}")
    if stack_trace:
        parts.append(f"Stack trace:\n{stack_trace.strip()}")
    if content:
        parts.append(content.strip())
    merged = "\n\n".join(part for part in parts if part)
    return merged or None


def _analysis_to_response(analysis) -> AnalysisResponse:
    return AnalysisResponse(
        id=analysis.id,
        bug_id=analysis.bug_id,
        status=analysis.status,
        current_stage=analysis.current_stage,
        triage=analysis.triage,
        log_analysis=analysis.log_analysis,
        duplicate_detection=analysis.duplicate_detection,
        root_cause=analysis.root_cause,
        remediation=analysis.remediation,
        risk_assessment=analysis.risk_assessment,
        confidence_scoring=analysis.confidence_scoring,
        executive_summary=analysis.executive_summary,
        retrieved_context=analysis.retrieved_context,
        agent_results=[
            AgentOutputSchema(
                agent_name=r.agent_name,
                stage=r.stage,
                output=r.output,
                confidence=r.confidence,
                duration_ms=r.duration_ms,
            )
            for r in analysis.agent_results
        ],
        summary=analysis.summary,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
    )


@router.post("/submit-bug", response_model=BugSubmitResponse)
async def submit_bug(
    bug_service: BugService = Depends(get_bug_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    file: Optional[UploadFile] = File(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    error_message: Optional[str] = Form(None),
    stack_trace: Optional[str] = Form(None),
    component: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
):
    """Submit a bug report via file upload or pasted text."""
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    merged_content = _compose_bug_content(content, description, error_message, stack_trace)

    if file and file.filename:
        file_bytes = await file.read()
        bug = await bug_service.submit_from_file(
            filename=file.filename,
            content=file_bytes,
            title=title,
            component=component,
            tags=tag_list,
        )
        if merged_content:
            prefix = merged_content
            bug.raw_content = f"{prefix}\n\n--- Uploaded file ---\n{bug.raw_content or ''}"
            if description:
                bug.description = description
            from app.services.store import store as bug_store
            bug_store.save_bug(bug)
    elif merged_content:
        bug = bug_service.create_bug_from_text(
            content=merged_content,
            title=title,
            description=description,
            component=component,
            tags=tag_list,
        )
    else:
        from app.utils.exceptions import ValidationError

        raise ValidationError("Provide either a file upload or pasted bug content.")

    analysis = analysis_service.create_analysis(bug)
    logger.info("Bug submitted: %s, analysis: %s", bug.id, analysis.id)

    return BugSubmitResponse(
        message="Bug submitted successfully.",
        bug=_bug_to_response(bug),
        analysis_id=analysis.id,
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_bug(
    request: AnalyzeRequest,
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """Run the full multi-agent analysis pipeline on a submitted bug."""
    analysis = analysis_service.run_analysis(
        bug_id=request.bug_id,
        use_mmr=request.use_mmr,
        retrieval_top_k=request.retrieval_top_k,
    )
    return AnalyzeResponse(
        message="Analysis completed successfully.",
        analysis=_analysis_to_response(analysis),
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    limit: int = 50,
    offset: int = 0,
    history_service: HistoryService = Depends(get_history_service),
):
    """Retrieve analysis history."""
    return history_service.list_history(limit=limit, offset=offset)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness probe."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        environment=settings.environment,
        timestamp=datetime.utcnow(),
    )


@router.get("/test", response_model=Phase1TestResponse)
async def phase1_test():
    """Phase 1 connectivity check used by the Analyze Bug page."""
    return Phase1TestResponse(
        ok=True,
        phase=1,
        message="Backend connected successfully. Phase 1 scaffold is ready.",
        service="Smart Bug Analyzer API",
    )


@router.get("/status", response_model=StatusResponse)
async def system_status():
    """Detailed system and dependency status."""
    settings = get_settings()
    services: list[ServiceStatus] = []

    embedding_svc = EmbeddingService()
    services.append(
        ServiceStatus(
            name="embedding_model",
            status="ready" if embedding_svc.is_available() else "unavailable",
            message=settings.embedding_model,
        )
    )

    try:
        vs = VectorStore()
        chroma_ok = vs.is_available()
        doc_count = vs.document_count
        services.append(
            ServiceStatus(
                name="chromadb",
                status="ready" if chroma_ok else "unavailable",
                message=f"{doc_count} documents indexed",
            )
        )
    except Exception as exc:
        doc_count = 0
        services.append(
            ServiceStatus(
                name="chromadb",
                status="unavailable",
                message=str(exc),
            )
        )

    overall = "ready" if all(s.status == "ready" for s in services) else "degraded"
    
    # Read ChromaDB status metadata if available
    import json
    from pathlib import Path
    status_file = settings.chroma_path / "status.json"
    kb_data = {}
    if status_file.exists():
        try:
            with status_file.open(encoding="utf-8") as f:
                kb_data = json.load(f)
        except Exception:
            pass

    return StatusResponse(
        overall=overall,
        services=services,
        active_analyses=store.active_analysis_count,
        total_bugs=store.bug_count,
        chroma_documents=doc_count,
        last_indexing_time=kb_data.get("last_indexing_time"),
        storage_used=kb_data.get("storage_used", "51.2 KB"),
        model_version=kb_data.get("model_version", "v2.0"),
        embedding_model=kb_data.get("embedding_model", settings.embedding_model),
        category_distribution=kb_data.get("category_distribution", {})
    )


@router.get("/analysis/{analysis_id}/download")
async def download_analysis_report(
    analysis_id: str,
    format: str = "pdf",
    analysis_service: AnalysisService = Depends(get_analysis_service),
    bug_service: BugService = Depends(get_bug_service),
):
    """Generate and download visual TXT, Markdown, or PDF report for target analysis."""
    analysis = analysis_service.get_analysis(analysis_id)
    bug = bug_service.get_bug(analysis.bug_id)
    
    from app.services.report_service import ReportService
    content_bytes, media_type, filename = ReportService.generate_report(analysis, bug, format)
    
    from fastapi import Response
    return Response(
        content=content_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/analysis/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: str,
    analysis_service: AnalysisService = Depends(get_analysis_service)
):
    """Retrieve detailed analysis results for a specific analysis ID."""
    analysis = analysis_service.get_analysis(analysis_id)
    return _analysis_to_response(analysis)


@router.get("/bug/{bug_id}", response_model=BugResponse)
async def get_bug(
    bug_id: str,
    bug_service: BugService = Depends(get_bug_service)
):
    """Retrieve bug report details for a specific bug ID."""
    bug = bug_service.get_bug(bug_id)
    return _bug_to_response(bug)


@router.get("/settings", response_model=SettingsResponse)
async def get_app_settings():
    """Return current application settings."""
    settings = get_settings()
    app_settings = AppSettings(
        embedding_model=settings.embedding_model,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        retrieval_top_k=settings.retrieval_top_k,
        mmr_lambda=settings.mmr_lambda,
        max_upload_size_mb=settings.max_upload_size_mb,
        allowed_extensions=settings.allowed_extension_list,
        llm_model=settings.llm_model,
        enable_mmr=True,
    )
    return SettingsResponse(**app_settings.model_dump())


@router.post("/upload", response_model=BugSubmitResponse)
async def upload_bug(
    bug_service: BugService = Depends(get_bug_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    file: Optional[UploadFile] = File(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    error_message: Optional[str] = Form(None),
    stack_trace: Optional[str] = Form(None),
    component: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
):
    """Alias for submit-bug used by the Analyze Bug form file upload flow."""
    return await submit_bug(
        bug_service=bug_service,
        analysis_service=analysis_service,
        file=file,
        title=title,
        description=description,
        content=content,
        error_message=error_message,
        stack_trace=stack_trace,
        component=component,
        tags=tags,
    )


@router.get("/history/{entry_id}")
async def get_history_entry(
    entry_id: str,
    history_service: HistoryService = Depends(get_history_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """Load one history record and its analysis when available."""
    entry = history_service.get_entry(entry_id)
    if not entry:
        from app.utils.exceptions import NotFoundError

        raise NotFoundError(f"History entry {entry_id} not found.")
    analysis = None
    if entry.analysis_id:
        try:
            analysis = _analysis_to_response(analysis_service.get_analysis(entry.analysis_id))
        except Exception:
            analysis = None
    return {"success": True, "item": entry, "analysis": analysis}


@router.delete("/history/{entry_id}")
async def delete_history_entry(
    entry_id: str,
    history_service: HistoryService = Depends(get_history_service),
):
    history_service.delete_entry(entry_id)
    return {"success": True, "message": f"History entry {entry_id} deleted."}


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard():
    """Live dashboard metrics from stored bugs and analyses."""
    from app.services.dashboard_service import DashboardService

    return DashboardResponse(**DashboardService().get_overview())


@router.get("/knowledge-base", response_model=KnowledgeBaseResponse)
async def list_knowledge_base(
    search: str = "",
    status: str = "",
    category: str = "",
    bug_service: BugService = Depends(get_bug_service),
):
    bugs = bug_service.list_bugs(search=search, status=status, category=category)
    items = [
        KnowledgeBaseItem(
            id=bug.id,
            title=bug.title,
            description=bug.description,
            status=bug.status,
            priority=bug.metadata.priority.value if bug.metadata.priority else None,
            category=bug.metadata.component,
            root_cause=bug.metadata.root_cause,
            resolution=bug.metadata.resolution,
            created_at=bug.created_at,
        )
        for bug in bugs
    ]
    return KnowledgeBaseResponse(total=len(items), items=items)


@router.post("/knowledge-base", response_model=BugResponse)
async def update_knowledge_base(
    request: KnowledgeBaseUpdateRequest,
    bug_service: BugService = Depends(get_bug_service),
):
    """Save confirmed root cause / applied fix for RAG in later phases."""
    bug = bug_service.update_knowledge_entry(
        bug_id=request.bug_id,
        confirmed_root_cause=request.confirmed_root_cause,
        applied_fix=request.applied_fix,
        resolution_notes=request.resolution_notes,
        status=request.status,
    )
    return _bug_to_response(bug)


@router.post("/phase1/analyze", response_model=Phase1AnalyzeResponse)
async def phase1_analyze(payload: Phase1AnalyzeRequest):
    """
    Phase 1 analyze endpoint.

    Accepts bug form fields and confirms frontend ↔ backend wiring.
    Full multi-agent pipeline is intentionally deferred to later phases.
    """
    logger.info("Phase 1 analyze received title=%s", payload.title)
    return Phase1AnalyzeResponse(
        success=True,
        phase=1,
        message="Bug payload received. Multi-agent pipeline is scaffolded for later phases.",
        received={
            "title": payload.title,
            "description": (payload.description or "")[:500],
            "error_logs_chars": len(payload.error_logs or ""),
            "stack_trace_chars": len(payload.stack_trace or ""),
        },
        pipeline_status="scaffolded",
    )


@router.post("/phase2/analyze", response_model=Phase2AnalyzeResponse)
async def phase2_analyze(
    title: Optional[str] = Form(...),
    description: Optional[str] = Form(""),
    error_logs: Optional[str] = Form(""),
    stack_trace: Optional[str] = Form(""),
    file: Optional[UploadFile] = File(None),
):
    """
    Phase 2: ingest bug report, parse logs/stack traces, and run AI triage.

    Accepts multipart form fields and an optional .txt/.log/.json file.
    """
    from app.services.phase2_service import Phase2Service
    from app.utils.file_parser import FileParsingEngine

    file_text = ""
    file_name = None
    if file and file.filename:
        raw = await file.read()
        file_name = file.filename
        try:
            file_text = FileParsingEngine.parse(file.filename, raw)
        except Exception:
            file_text = raw.decode("utf-8", errors="replace")

    service = Phase2Service()
    return service.analyze(
        title=title or "Untitled Bug",
        description=description or "",
        error_logs=error_logs or "",
        stack_trace=stack_trace or "",
        file_text=file_text,
        file_name=file_name,
    )


@router.post("/phase3/analyze", response_model=Phase3AnalyzeResponse)
async def phase3_analyze(
    title: Optional[str] = Form(...),
    description: Optional[str] = Form(""),
    error_logs: Optional[str] = Form(""),
    stack_trace: Optional[str] = Form(""),
    file: Optional[UploadFile] = File(None),
):
    """Phase 3: Phase 2 pipeline + FAISS similar bugs + recurrence analysis."""
    from app.services.phase3_service import Phase3Service
    from app.utils.file_parser import FileParsingEngine

    file_text = ""
    file_name = None
    if file and file.filename:
        raw = await file.read()
        file_name = file.filename
        try:
            file_text = FileParsingEngine.parse(file.filename, raw)
        except Exception:
            file_text = raw.decode("utf-8", errors="replace")

    service = Phase3Service()
    return service.analyze(
        title=title or "Untitled Bug",
        description=description or "",
        error_logs=error_logs or "",
        stack_trace=stack_trace or "",
        file_text=file_text,
        file_name=file_name,
    )


@router.get("/knowledge-base/faiss", response_model=KnowledgeBaseListResponse)
async def list_faiss_knowledge_base(search: str = "", limit: int = 100):
    from app.services.knowledge_base_service import KnowledgeBaseService

    data = KnowledgeBaseService().list_entries(limit=limit, search=search)
    return KnowledgeBaseListResponse(**data)


@router.post("/knowledge-base/faiss", response_model=KnowledgeBaseAddResponse)
async def add_faiss_knowledge_entry(payload: KnowledgeBaseAddRequest):
    from app.services.knowledge_base_service import KnowledgeBaseService

    item = KnowledgeBaseService().add_entry(
        title=payload.title,
        description=payload.description,
        component=payload.component,
        exception_type=payload.exception_type,
        root_cause=payload.root_cause,
        resolution=payload.resolution,
    )
    return KnowledgeBaseAddResponse(
        success=True,
        message="Knowledge entry indexed in FAISS.",
        item=item,
    )


@router.post("/knowledge-base/faiss/seed")
async def seed_faiss_knowledge_base():
    from app.services.knowledge_base_service import KnowledgeBaseService

    return KnowledgeBaseService().ensure_seeded()


@router.post("/phase4/analyze", response_model=Phase4AnalyzeResponse)
async def phase4_analyze(
    title: Optional[str] = Form(...),
    description: Optional[str] = Form(""),
    error_logs: Optional[str] = Form(""),
    stack_trace: Optional[str] = Form(""),
    file: Optional[UploadFile] = File(None),
):
    """Phase 4: Phase 3 + root cause + ranked fixes + risk score."""
    from app.services.phase4_service import Phase4Service
    from app.utils.file_parser import FileParsingEngine

    file_text = ""
    file_name = None
    if file and file.filename:
        raw = await file.read()
        file_name = file.filename
        try:
            file_text = FileParsingEngine.parse(file.filename, raw)
        except Exception:
            file_text = raw.decode("utf-8", errors="replace")

    return Phase4Service().analyze(
        title=title or "Untitled Bug",
        description=description or "",
        error_logs=error_logs or "",
        stack_trace=stack_trace or "",
        file_text=file_text,
        file_name=file_name,
    )

