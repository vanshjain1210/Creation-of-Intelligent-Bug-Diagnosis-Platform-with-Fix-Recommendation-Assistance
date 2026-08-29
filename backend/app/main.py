"""AI-Smart-Bug-Analyzer-And-Fix-Advisor FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config.settings import get_settings
from app.utils.exceptions import register_exception_handlers
from app.utils.logger import get_logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    logger = get_logger("main")
    settings = get_settings()
    logger.info("Starting %s v%s [%s]", settings.app_name, settings.app_version, settings.environment)

    # Initialize SQL database tables
    try:
        from app.config.database import engine, Base, ensure_sqlite_columns
        Base.metadata.create_all(bind=engine)
        ensure_sqlite_columns()
        logger.info("SQL Database tables initialized successfully.")
    except Exception as exc:
        logger.error("Failed to initialize database tables: %s", exc)

    try:
        from app.rag.embeddings import EmbeddingService

        EmbeddingService()
        logger.info("Embedding model initialized: %s", settings.embedding_model)
    except Exception as exc:
        logger.warning("Embedding model not loaded at startup: %s", exc)

    try:
        from app.rag.vector_store import VectorStore

        vs = VectorStore()
        logger.info("ChromaDB initialized with %d documents", vs.document_count)
    except Exception as exc:
        logger.warning("ChromaDB not available at startup: %s", exc)

    yield
    logger.info("Shutting down AI-Smart-Bug-Analyzer-And-Fix-Advisor")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        description="AI Smart Bug Analyzer and Fix Advisor",
        version=settings.app_version,
        lifespan=lifespan,
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(router, prefix=settings.api_prefix, tags=["AI-Smart-Bug-Analyzer-And-Fix-Advisor"])
    if settings.api_prefix != "/api":
        app.include_router(router, prefix="/api", tags=["api-aliases"])

    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    return app


app = create_app()
