"""History retrieval service."""

from app.models import HistoryEntry
from app.schemas import HistoryItem, HistoryResponse
from app.services.store import store
from app.utils.exceptions import NotFoundError


class HistoryService:
    def list_history(self, limit: int = 50, offset: int = 0) -> HistoryResponse:
        entries = store.list_history(limit=limit, offset=offset)
        items = [
            HistoryItem(
                id=e.id,
                bug_id=e.bug_id,
                analysis_id=e.analysis_id,
                title=e.title,
                priority=e.priority,
                component=e.component,
                status=e.status,
                summary=e.summary,
                created_at=e.created_at,
            )
            for e in entries
        ]
        return HistoryResponse(total=store.history_count, items=items)

    def get_entry(self, entry_id: str) -> HistoryEntry | None:
        entries = store.list_history(limit=1000)
        return next((entry for entry in entries if entry.id == entry_id), None)

    def delete_entry(self, entry_id: str) -> None:
        deleted = store.delete_history(entry_id)
        if not deleted:
            raise NotFoundError(f"History entry {entry_id} not found.")
