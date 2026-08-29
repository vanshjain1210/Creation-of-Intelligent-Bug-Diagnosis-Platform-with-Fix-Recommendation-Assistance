"""FAISS-backed vector store for historical bug RAG (with NumPy fallback)."""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional

import numpy as np

from app.config.settings import PROJECT_ROOT, get_settings
from app.rag.embeddings import EmbeddingService
from app.utils.logger import get_logger

logger = get_logger("rag.faiss_store")

try:
    import faiss  # type: ignore

    _HAS_FAISS = True
except Exception:  # pragma: no cover
    faiss = None
    _HAS_FAISS = False
    logger.warning("faiss not installed — using NumPy cosine search fallback")


class FaissKnowledgeStore:
    """Persisted FAISS / NumPy index of resolved and historical bugs."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        _ = get_settings()
        self._embedding = EmbeddingService()
        self._dir = PROJECT_ROOT / "faiss_db"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "bugs.index"
        self._meta_path = self._dir / "bugs_meta.json"
        self._index = None
        self._metas: List[Dict[str, Any]] = []
        self._dim: Optional[int] = None
        self._load()
        self._initialized = True

    @property
    def backend(self) -> str:
        return "faiss" if _HAS_FAISS else "numpy"

    @property
    def size(self) -> int:
        return len(self._metas)

    def _load(self) -> None:
        if self._meta_path.exists():
            self._metas = json.loads(self._meta_path.read_text(encoding="utf-8"))
        else:
            self._metas = []

        if _HAS_FAISS and self._index_path.exists():
            self._index = faiss.read_index(str(self._index_path))
            self._dim = self._index.d
            logger.info("Loaded FAISS index with %d vectors", self._index.ntotal)
            return

        npy = self._dir / "bugs_vectors.npy"
        if npy.exists():
            vectors = np.load(npy)
            self._dim = int(vectors.shape[1]) if vectors.ndim == 2 else None
            self._index = vectors.astype("float32")
            logger.info("Loaded NumPy vector index with %d vectors", len(self._index))
        else:
            self._index = None
            self._dim = None

    def _persist(self) -> None:
        self._meta_path.write_text(
            json.dumps(self._metas, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if self._index is None:
            return
        if _HAS_FAISS and not isinstance(self._index, np.ndarray):
            faiss.write_index(self._index, str(self._index_path))
        else:
            np.save(self._dir / "bugs_vectors.npy", np.asarray(self._index, dtype="float32"))

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.clip(norms, 1e-12, None)
        return (vectors / norms).astype("float32")

    def add_documents(self, documents: List[Dict[str, Any]]) -> int:
        if not documents:
            return 0

        texts = [d["text"] for d in documents]
        vectors = np.asarray(self._embedding.embed_texts(texts), dtype="float32")
        vectors = self._normalize(vectors)
        dim = vectors.shape[1]

        if self._index is None:
            self._dim = dim
            if _HAS_FAISS:
                self._index = faiss.IndexFlatIP(dim)
                self._index.add(vectors)
            else:
                self._index = vectors
        else:
            if _HAS_FAISS and not isinstance(self._index, np.ndarray):
                self._index.add(vectors)
            else:
                self._index = np.vstack([np.asarray(self._index, dtype="float32"), vectors])

        for doc in documents:
            meta = {k: v for k, v in doc.items() if k != "text"}
            self._metas.append(meta)

        self._persist()
        logger.info(
            "Indexed %d documents (store size=%d, backend=%s)",
            len(documents),
            self.size,
            self.backend,
        )
        return len(documents)

    def has_id(self, doc_id: str) -> bool:
        return any(m.get("id") == doc_id for m in self._metas)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if self._index is None or self.size == 0:
            return []

        q = np.asarray(self._embedding.embed_texts([query]), dtype="float32")
        q = self._normalize(q)
        k = min(top_k, self.size)

        if _HAS_FAISS and not isinstance(self._index, np.ndarray):
            scores, idxs = self._index.search(q, k)
            results = []
            for score, idx in zip(scores[0], idxs[0]):
                if idx < 0 or idx >= len(self._metas):
                    continue
                item = dict(self._metas[idx])
                item["similarity"] = float(max(0.0, min(1.0, score)))
                results.append(item)
            return results

        matrix = np.asarray(self._index, dtype="float32")
        sims = (matrix @ q[0]).astype("float32")
        top_idx = np.argsort(-sims)[:k]
        results = []
        for idx in top_idx:
            item = dict(self._metas[int(idx)])
            item["similarity"] = float(max(0.0, min(1.0, sims[int(idx)])))
            results.append(item)
        return results

    def list_documents(self, limit: int = 100, search: str = "") -> List[Dict[str, Any]]:
        docs = list(self._metas)
        if search:
            q = search.lower()
            docs = [
                d
                for d in docs
                if q in (d.get("title") or "").lower()
                or q in (d.get("component") or "").lower()
                or q in (d.get("exception_type") or "").lower()
                or q in (d.get("id") or "").lower()
            ]
        return docs[:limit]
