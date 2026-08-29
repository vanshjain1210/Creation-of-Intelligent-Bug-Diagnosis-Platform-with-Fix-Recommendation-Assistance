"""Bug submission and file handling service."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import aiofiles

from app.config.settings import get_settings
from app.models import Bug, BugMetadata, BugStatus
from app.services.store import store
from app.utils.exceptions import ValidationError
from app.utils.logger import get_logger

logger = get_logger("services.bug")

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".log", ".json", ".xml"}


class BugService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def validate_extension(self, filename: str) -> None:
        ext = Path(filename).suffix.lower()
        if ext not in self.settings.allowed_extension_list:
            raise ValidationError(
                f"Unsupported file type '{ext}'. Allowed: {self.settings.allowed_extension_list}",
                details={"extension": ext},
            )

    def validate_size(self, size_bytes: int) -> None:
        if size_bytes > self.settings.max_upload_bytes:
            raise ValidationError(
                f"File exceeds maximum size of {self.settings.max_upload_size_mb} MB.",
                details={"max_mb": self.settings.max_upload_size_mb},
            )

    async def save_upload(self, filename: str, content: bytes) -> Path:
        self.validate_extension(filename)
        self.validate_size(len(content))
        # Strip directories to prevent path traversal
        clean_filename = Path(filename).name
        safe_name = f"{uuid.uuid4()}_{clean_filename}"
        dest = self.settings.upload_path / safe_name
        async with aiofiles.open(dest, "wb") as f:
            await f.write(content)
        logger.info("Saved upload: %s", dest)
        return dest

    async def read_file_content(self, path: Path) -> str:
        from app.utils.file_parser import FileParsingEngine
        
        # Read file as bytes and pass to file parsing engine
        async with aiofiles.open(path, "rb") as f:
            content_bytes = await f.read()
            
        return FileParsingEngine.parse(path.name, content_bytes)

    def create_bug_from_text(
        self,
        content: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        component: Optional[str] = None,
        tags: Optional[list] = None,
        file_path: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> Bug:
        if not content.strip():
            raise ValidationError("Bug report content cannot be empty.")

        metadata = BugMetadata(
            component=component or "",
            tags=tags or [],
        )
        bug = Bug(
            title=title or "Untitled Bug Report",
            description=description or content[:500],
            raw_content=content,
            file_path=file_path,
            file_name=file_name,
            metadata=metadata,
            status=BugStatus.SUBMITTED,
        )
        bug.metadata.bug_id = bug.id
        if not title:
            bug.title = f"Bug Report {bug.id[:8]}"
        return store.save_bug(bug)

    async def submit_from_file(
        self,
        filename: str,
        content: bytes,
        title: Optional[str] = None,
        component: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> Bug:
        path = await self.save_upload(filename, content)
        text = await self.read_file_content(path)
        return self.create_bug_from_text(
            content=text,
            title=title,
            component=component,
            tags=tags,
            file_path=str(path),
            file_name=filename,
        )

    def get_bug(self, bug_id: str) -> Bug:
        bug = store.get_bug(bug_id)
        if not bug:
            from app.utils.exceptions import NotFoundError

            raise NotFoundError(f"Bug {bug_id} not found.")
        return bug

    def list_bugs(self, limit: int = 100, offset: int = 0, search: str = "", status: str = "", category: str = ""):
        return store.list_bugs(limit=limit, offset=offset, search=search, status=status, category=category)

    def update_knowledge_entry(
        self,
        bug_id: str,
        confirmed_root_cause: Optional[str] = None,
        applied_fix: Optional[str] = None,
        resolution_notes: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Bug:
        bug = self.get_bug(bug_id)
        if confirmed_root_cause is not None:
            bug.metadata.root_cause = confirmed_root_cause
        if applied_fix is not None:
            bug.metadata.resolution = applied_fix
        elif resolution_notes is not None:
            bug.metadata.resolution = resolution_notes
        if status:
            bug.status = BugStatus(status)
        bug.updated_at = datetime.utcnow()
        return store.save_bug(bug)

    def preprocess(self, bug: Bug) -> str:
        """Clean and normalize bug content."""
        content = bug.raw_content or bug.description
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        cleaned = "\n".join(lines)
        bug.raw_content = cleaned
        bug.updated_at = datetime.utcnow()
        store.save_bug(bug)
        return cleaned
