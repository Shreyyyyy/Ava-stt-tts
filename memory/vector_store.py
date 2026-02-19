"""
FAISS vector store for semantic memory lookup.
Uses sentence-transformers (all-MiniLM-L6-v2) for local embeddings.
Index is persisted to disk and reloaded on startup.
"""

import json
import logging
import numpy as np
import faiss
from pathlib import Path
from typing import List, Tuple, Optional
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

VECTOR_DIR = Path(__file__).parent.parent / "memory" / "vectors"
INDEX_PATH = VECTOR_DIR / "faiss.index"
META_PATH  = VECTOR_DIR / "metadata.json"
EMBED_MODEL = "all-MiniLM-L6-v2"
EMBED_DIM   = 384


class VectorStore:
    """Wraps a FAISS flat-L2 index with JSON metadata sidecar."""

    def __init__(self):
        VECTOR_DIR.mkdir(parents=True, exist_ok=True)
        self._model: Optional[SentenceTransformer] = None
        self._index: Optional[faiss.IndexFlatL2] = None
        self._metadata: List[dict] = []
        self._load()

    # ── Private helpers ──────────────────────────────────────────────────────

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(f"Loading embedding model: {EMBED_MODEL}")
            self._model = SentenceTransformer(EMBED_MODEL)
        return self._model

    def _load(self):
        if INDEX_PATH.exists() and META_PATH.exists():
            try:
                self._index = faiss.read_index(str(INDEX_PATH))
                with open(META_PATH, "r") as f:
                    self._metadata = json.load(f)
                logger.info(f"Vector store loaded – {self._index.ntotal} vectors")
                return
            except Exception as e:
                logger.warning(f"Could not load existing index: {e}; creating fresh.")
        self._index = faiss.IndexFlatL2(EMBED_DIM)
        self._metadata = []

    def _save(self):
        faiss.write_index(self._index, str(INDEX_PATH))
        with open(META_PATH, "w") as f:
            json.dump(self._metadata, f, indent=2)

    def _embed(self, texts: List[str]) -> np.ndarray:
        vecs = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vecs.astype("float32")

    # ── Public API ───────────────────────────────────────────────────────────

    def add(self, conversation_id: int, text: str, metadata: Optional[dict] = None) -> int:
        """Add a text embedding and return the FAISS vector index."""
        vec = self._embed([text])
        self._index.add(vec)
        vector_idx = self._index.ntotal - 1
        entry = {
            "vector_idx":      vector_idx,
            "conversation_id": conversation_id,
            "text_snippet":    text[:200],
            **(metadata or {}),
        }
        self._metadata.append(entry)
        self._save()
        return vector_idx

    def search(self, query: str, k: int = 5) -> List[Tuple[float, dict]]:
        """Return top-k (distance, metadata) pairs for a query string."""
        if self._index.ntotal == 0:
            return []
        vec = self._embed([query])
        k   = min(k, self._index.ntotal)
        distances, indices = self._index.search(vec, k)
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            meta = self._metadata[idx] if idx < len(self._metadata) else {}
            results.append((float(dist), meta))
        return results

    def bulk_add(self, entries: List[dict]):
        """Add multiple entries at once. Each entry must have 'conversation_id' and 'text'."""
        if not entries:
            return
        texts = [e["text"] for e in entries]
        vecs  = self._embed(texts)
        start_idx = self._index.ntotal
        self._index.add(vecs)
        for i, entry in enumerate(entries):
            self._metadata.append({
                "vector_idx":      start_idx + i,
                "conversation_id": entry["conversation_id"],
                "text_snippet":    entry["text"][:200],
            })
        self._save()
        logger.info(f"Bulk-added {len(entries)} vectors to FAISS.")

    def count(self) -> int:
        return self._index.ntotal if self._index else 0


# Singleton instance
_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
