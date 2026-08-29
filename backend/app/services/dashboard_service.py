"""Dashboard aggregation from stored bugs and analyses."""

from collections import Counter
from typing import Any, Dict, List

from app.models import BugPriority, BugStatus
from app.services.store import store


OPEN_STATUSES = {
    BugStatus.OPEN.value,
    BugStatus.SUBMITTED.value,
    BugStatus.PROCESSING.value,
    BugStatus.IN_PROGRESS.value,
    BugStatus.FAILED.value,
}

RESOLVED_STATUSES = {
    BugStatus.ANALYZED.value,
    BugStatus.RESOLVED.value,
    BugStatus.CLOSED.value,
}

HIGH_RISK_PRIORITIES = {BugPriority.HIGH.value, BugPriority.CRITICAL.value}


class DashboardService:
    def get_overview(self) -> Dict[str, Any]:
        bugs = store.list_bugs(limit=500)
        analyses = store.list_analyses(limit=500)
        history = store.list_history(limit=10)

        severity_distribution = Counter()
        component_counts = Counter()
        open_bugs = 0
        resolved_bugs = 0
        high_risk_bugs = 0

        for bug in bugs:
            priority = bug.metadata.priority.value if bug.metadata.priority else "unknown"
            severity_distribution[priority] += 1
            if bug.metadata.component:
                component_counts[bug.metadata.component] += 1
            if bug.status.value in OPEN_STATUSES:
                open_bugs += 1
            if bug.status.value in RESOLVED_STATUSES:
                resolved_bugs += 1
            if priority in HIGH_RISK_PRIORITIES:
                high_risk_bugs += 1

        duplicate_bugs = 0
        for analysis in analyses:
            duplicates = analysis.duplicate_detection or {}
            matches = duplicates.get("matches") or duplicates.get("similar_bugs") or duplicates.get("duplicates")
            if matches:
                duplicate_bugs += 1
            elif duplicates.get("is_duplicate"):
                duplicate_bugs += 1

        recent_analyses: List[Dict[str, Any]] = [
            {
                "id": item.id,
                "bug_id": item.bug_id,
                "analysis_id": item.analysis_id,
                "title": item.title,
                "priority": item.priority.value if item.priority else "unknown",
                "component": item.component,
                "status": item.status.value if item.status else "pending",
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in history
        ]

        return {
            "total_bugs": store.bug_count,
            "open_bugs": open_bugs,
            "resolved_bugs": resolved_bugs,
            "high_risk_bugs": high_risk_bugs,
            "recurring_bugs": 0,
            "duplicate_bugs": duplicate_bugs,
            "severity_distribution": dict(severity_distribution),
            "component_counts": dict(component_counts.most_common(8)),
            "recent_analyses": recent_analyses,
        }
