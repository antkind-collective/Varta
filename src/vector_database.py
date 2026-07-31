import os
import numpy as np
from typing import List, Dict, Any, Optional
from src.index_loader import IndexLoader
from src.metadata_store import MetadataStore

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

class VectorDatabase:
    """
    VARTA VectorDatabase Facade Interface & Search Engine API:
    - High-level interface providing fast vector similarity search & metadata retrieval.
    - Synchronizes FAISS vector IDs 1-to-1 with SQLite relational metadata records.
    - Supports top-k vector retrieval, similarity score computation, and metadata filtering.
    """

    def __init__(self, index: Any, metadata_store: MetadataStore, manifest: Dict[str, Any], load_time_sec: float = 0.0):
        self.index = index
        self.metadata_store = metadata_store
        self.manifest = manifest
        self.load_time_sec = load_time_sec

    @classmethod
    def load(cls, db_dir: str) -> "VectorDatabase":
        loader = IndexLoader(db_dir)
        index, meta_store, manifest, elapsed = loader.load_database()
        return cls(index=index, metadata_store=meta_store, manifest=manifest, load_time_sec=elapsed)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if not FAISS_AVAILABLE or self.index is None:
            raise RuntimeError("FAISS index is not initialized.")

        # Ensure writeable float32 C-contiguous array
        query_arr = np.array(query_vector, copy=True, dtype=np.float32)
        if query_arr.ndim == 1:
            query_arr = np.expand_dims(query_arr, axis=0)

        # L2-normalize query vector for Cosine Similarity matching
        faiss.normalize_L2(query_arr)

        # Fetch extra items if filtering is requested
        fetch_k = top_k * 5 if metadata_filters else top_k
        fetch_k = min(fetch_k, self.index.ntotal)

        scores, indices = self.index.search(query_arr, fetch_k)

        vector_ids = [int(idx) for idx in indices[0] if idx >= 0]
        score_map = {int(idx): float(score) for idx, score in zip(indices[0], scores[0]) if idx >= 0}

        # Fetch metadata records from SQLite for retrieved vector IDs
        raw_results = self.metadata_store.get_metadata_by_vector_ids(vector_ids)

        filtered_results = []
        for res in raw_results:
            vid = res["vector_id"]
            res["similarity_score"] = round(score_map.get(vid, 0.0), 4)

            # Apply metadata filters if provided
            if metadata_filters:
                match = True
                meta = res.get("metadata", {})
                for k, v in metadata_filters.items():
                    if meta.get(k) != v and res.get(k) != v:
                        match = False
                        break
                if not match:
                    continue

            filtered_results.append(res)
            if len(filtered_results) >= top_k:
                break

        return filtered_results

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        return self.metadata_store.get_chunk_by_id(chunk_id)

    def get_chunks_by_parent_id(self, parent_doc_id: str) -> List[Dict[str, Any]]:
        return self.metadata_store.get_chunks_by_parent_id(parent_doc_id)

    def get_index_statistics(self) -> Dict[str, Any]:
        return {
            "total_vectors_indexed": self.index.ntotal if self.index else 0,
            "vector_dimension": self.index.d if self.index else 0,
            "metadata_records_count": self.metadata_store.get_total_records_count(),
            "reload_duration_sec": self.load_time_sec,
            "manifest": self.manifest
        }
