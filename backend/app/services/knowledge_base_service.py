"""Knowledge-base seeding and FAISS indexing helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.rag.faiss_store import FaissKnowledgeStore
from app.services.store import store
from app.utils.logger import get_logger

logger = get_logger("services.knowledge_base")

SEED_BUGS: List[Dict[str, Any]] = [
    {
        "id": "kb-seed-001",
        "title": "NullPointerException in CheckoutService.process",
        "component": "backend",
        "exception_type": "NullPointerException",
        "root_cause": "Cart object was null when checkout ran for guest users without a session cart.",
        "resolution": "Initialize an empty cart for guests and add null-checks before process().",
        "status": "resolved",
        "text": (
            "NullPointerException in CheckoutService.process CheckoutService.java:42 "
            "empty cart guest checkout fails NPE backend payment flow"
        ),
    },
    {
        "id": "kb-seed-002",
        "title": "ConnectionPoolTimeoutException under load",
        "component": "database",
        "exception_type": "ConnectionPoolTimeoutException",
        "root_cause": "HikariCP pool size too small for peak traffic; connections held too long.",
        "resolution": "Increased max pool size, added connection leak detection, shortened transaction scope.",
        "status": "resolved",
        "text": (
            "ConnectionPoolTimeoutException database pool exhausted HikariCP timeout "
            "jdbc connection wait backend database"
        ),
    },
    {
        "id": "kb-seed-003",
        "title": "JWT token expired causing 401 on API",
        "component": "authentication",
        "exception_type": "ExpiredJwtException",
        "root_cause": "Access token TTL shorter than SPA session; refresh flow missing on 401.",
        "resolution": "Implemented silent refresh interceptor and extended access token TTL.",
        "status": "resolved",
        "text": (
            "ExpiredJwtException authentication 401 unauthorized token expired "
            "JWT refresh interceptor API auth"
        ),
    },
    {
        "id": "kb-seed-004",
        "title": "React memory leak on dashboard unmount",
        "component": "frontend",
        "exception_type": "MemoryLeakWarning",
        "root_cause": "setInterval and websocket listeners not cleared in useEffect cleanup.",
        "resolution": "Added cleanup handlers returning clearInterval and socket.close().",
        "status": "resolved",
        "text": (
            "React memory leak dashboard useEffect cleanup missing setInterval "
            "websocket frontend UI performance"
        ),
    },
    {
        "id": "kb-seed-005",
        "title": "SSLHandshakeException to payment gateway",
        "component": "network",
        "exception_type": "SSLHandshakeException",
        "root_cause": "Outdated TLS cipher suite and missing intermediate CA on app servers.",
        "resolution": "Updated JVM truststore and forced TLS 1.2+ with modern ciphers.",
        "status": "resolved",
        "text": (
            "SSLHandshakeException payment gateway TLS handshake failure "
            "certificate truststore network infrastructure"
        ),
    },
    {
        "id": "kb-seed-006",
        "title": "Python KeyError on missing request payload field",
        "component": "api",
        "exception_type": "KeyError",
        "root_cause": "API assumed required JSON keys without schema validation.",
        "resolution": "Added Pydantic request model validation and clearer 422 responses.",
        "status": "resolved",
        "text": (
            "KeyError missing field request.json traceback File api/handlers.py "
            "line 88 FastAPI validation backend API"
        ),
    },
    {
        "id": "kb-seed-007",
        "title": "SQLite database is locked",
        "component": "database",
        "exception_type": "OperationalError",
        "root_cause": "Concurrent writes without WAL mode or retry backoff.",
        "resolution": "Enabled WAL journal mode and added retry on locked database.",
        "status": "resolved",
        "text": (
            "sqlite3.OperationalError database is locked places.sqlite write "
            "concurrency database backend"
        ),
    },
    {
        "id": "kb-seed-008",
        "title": "Gateway timeout on payment authorize",
        "component": "api",
        "exception_type": "GatewayTimeoutException",
        "root_cause": "Upstream payment provider latency exceeded API gateway timeout.",
        "resolution": "Raised gateway timeout, added circuit breaker and async authorize callback.",
        "status": "resolved",
        "text": (
            "GatewayTimeoutException pay_timeout payment authorize HTTP 504 "
            "upstream timeout API infrastructure"
        ),
    },
]


class KnowledgeBaseService:
    def __init__(self) -> None:
        self.store = FaissKnowledgeStore()

    @property
    def backend(self) -> str:
        return self.store.backend

    @property
    def size(self) -> int:
        return self.store.size

    def ensure_seeded(self) -> Dict[str, Any]:
        added = 0
        for bug in SEED_BUGS:
            if not self.store.has_id(bug["id"]):
                self.store.add_documents([bug])
                added += 1
        info = {
            "seeded_added": added,
            "total_documents": self.store.size,
            "backend": self.store.backend,
        }
        logger.info("FAISS knowledge base seed: %s", info)
        return info

    def index_bug(
        self,
        *,
        bug_id: str,
        title: str,
        content: str,
        component: str = "",
        exception_type: str = "",
        root_cause: str = "",
        resolution: str = "",
        status: str = "analyzed",
    ) -> None:
        if self.store.has_id(bug_id):
            return
        text = " ".join(
            part
            for part in [title, content[:2000], component, exception_type, root_cause]
            if part
        )
        self.store.add_documents(
            [
                {
                    "id": bug_id,
                    "title": title,
                    "component": component or "unknown",
                    "exception_type": exception_type or "Unknown",
                    "root_cause": root_cause,
                    "resolution": resolution,
                    "status": status,
                    "text": text,
                }
            ]
        )

    def sync_from_sql(self, limit: int = 100) -> int:
        added = 0
        for bug in store.list_bugs(limit=limit):
            if self.store.has_id(bug.id):
                continue
            component = ""
            if bug.metadata:
                component = bug.metadata.component or ""
            self.index_bug(
                bug_id=bug.id,
                title=bug.title,
                content=bug.raw_content or bug.description or "",
                component=component,
                status=str(bug.status.value if hasattr(bug.status, "value") else bug.status),
            )
            added += 1
        return added

    def search_similar(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        self.ensure_seeded()
        return self.store.search(query, top_k=top_k)

    def list_entries(self, limit: int = 100, search: str = "") -> Dict[str, Any]:
        self.ensure_seeded()
        items = self.store.list_documents(limit=limit, search=search)
        return {
            "total": self.store.size if not search else len(items),
            "backend": self.store.backend,
            "items": items,
        }

    def add_entry(
        self,
        *,
        title: str,
        description: str = "",
        component: str = "",
        exception_type: str = "",
        root_cause: str = "",
        resolution: str = "",
        entry_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        import uuid

        doc_id = entry_id or f"kb-{uuid.uuid4().hex[:10]}"
        text = " ".join(
            part
            for part in [title, description, component, exception_type, root_cause, resolution]
            if part
        )
        doc = {
            "id": doc_id,
            "title": title,
            "component": component or "other",
            "exception_type": exception_type or "Unknown",
            "root_cause": root_cause,
            "resolution": resolution,
            "status": "resolved",
            "text": text,
        }
        self.store.add_documents([doc])
        return doc
