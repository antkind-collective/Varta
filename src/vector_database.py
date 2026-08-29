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

        # Check dimension alignment between index and query vector
        query_dim = query_arr.shape[1]
        index_dim = getattr(self.index, "d", None)
        if index_dim is not None and query_dim != index_dim:
            import logging
            logging.getLogger("VectorDatabase").error(
                f"FAISS index dimension ({index_dim}) does not match query vector dimension ({query_dim})."
            )
            if self.index.ntotal == 0:
                return []
            raise ValueError(
                f"FAISS index dimension ({index_dim}) does not match query vector dimension ({query_dim})."
            )

        if self.index.ntotal == 0:
            return []

        # Auto-resolve allowed_vector_ids if source_dataset filter is provided
        if metadata_filters and "allowed_vector_ids" not in metadata_filters and metadata_filters.get("source_dataset"):
            metadata_filters["allowed_vector_ids"] = self.get_scoped_vector_ids(source_dataset=metadata_filters.get("source_dataset"), limit=10000)

        # Fast exact scoring for small scoped subsets (e.g. specific datasets < 500 vectors)
        if metadata_filters and metadata_filters.get("allowed_vector_ids"):
            allowed_vids = set(metadata_filters["allowed_vector_ids"])
            if len(allowed_vids) <= 500 and hasattr(self.index, "reconstruct"):
                direct_scores = []
                for vid in allowed_vids:
                    if 0 <= vid < self.index.ntotal:
                        v_emb = self.index.reconstruct(vid)
                        sim = float(np.dot(query_arr[0], v_emb))
                        direct_scores.append((vid, sim))
                direct_scores.sort(key=lambda x: x[1], reverse=True)
                top_vids = [vid for vid, _ in direct_scores[:top_k]]
                score_map = {vid: sim for vid, sim in direct_scores[:top_k]}
                raw_results = self.metadata_store.get_metadata_by_vector_ids(top_vids)
                results = []
                for res in raw_results:
                    vid = res["vector_id"]
                    res["similarity_score"] = round(score_map.get(vid, 0.0), 4)
                    results.append(res)
                return results

        # Fetch extra items if filtering is requested
        if metadata_filters:
            if metadata_filters.get("allowed_vector_ids"):
                allowed_set_len = len(metadata_filters["allowed_vector_ids"])
                fetch_k = min(self.index.ntotal, max(top_k * 50, min(2000, allowed_set_len)))
            else:
                fetch_k = min(self.index.ntotal, top_k * 20)
        else:
            fetch_k = top_k * 5

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

            # Support dynamic context-filtered corpus via allowed_vector_ids / excluded_vector_ids / excluded_post_ids
            if metadata_filters:
                allowed_vids = metadata_filters.get("allowed_vector_ids")
                if allowed_vids is not None and vid not in allowed_vids:
                    continue
                excluded_vids = metadata_filters.get("excluded_vector_ids")
                if excluded_vids is not None and vid in excluded_vids:
                    continue

                excluded_pids = metadata_filters.get("excluded_post_ids")
                if excluded_pids is not None:
                    pid = str(res.get("post_id") or res.get("parent_doc_id") or (res.get("metadata", {}).get("post_id")) or "")
                    parent_id = str(res.get("parent_doc_id") or (res.get("metadata", {}).get("parent_doc_id")) or "")
                    if pid in excluded_pids or parent_id in excluded_pids:
                        continue

                # Apply attribute metadata filters
                match = True
                meta = res.get("metadata", {})
                for k, v in metadata_filters.items():
                    if k in ("allowed_vector_ids", "excluded_vector_ids", "excluded_post_ids"):
                        continue
                    if meta.get(k) != v and res.get(k) != v:
                        match = False
                        break
                if not match:
                    continue

            filtered_results.append(res)
            if len(filtered_results) >= top_k:
                break

        return filtered_results

    def get_scoped_vector_ids(
        self,
        geography: Optional[List[str]] = None,
        specific_location: Optional[str] = None,
        domain: str = "disaster",
        disaster_types: Optional[List[str]] = None,
        source_dataset: Optional[str] = None,
        limit: int = 5000
    ) -> List[int]:
        """Retrieves scoped vector IDs satisfying geography, disaster domain, and source_dataset from metadata store."""
        if hasattr(self, "metadata_store") and self.metadata_store and hasattr(self.metadata_store, "get_scoped_vector_ids"):
            return self.metadata_store.get_scoped_vector_ids(
                geography=geography,
                specific_location=specific_location,
                domain=domain,
                disaster_types=disaster_types,
                source_dataset=source_dataset,
                limit=limit
            )
        return []

    def get_candidate_parent_records(self, limit: int = 500, search_terms: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Retrieves candidate parent documents from underlying metadata store for relevance filtering."""
        if hasattr(self, "metadata_store") and self.metadata_store and hasattr(self.metadata_store, "get_candidate_parent_records"):
            return self.metadata_store.get_candidate_parent_records(limit=limit, search_terms=search_terms)
        return []

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        return self.metadata_store.get_chunk_by_id(chunk_id)

    def get_chunks_by_parent_id(self, parent_doc_id: str) -> List[Dict[str, Any]]:
        return self.metadata_store.get_chunks_by_parent_id(parent_doc_id)

    def get_index_statistics(self) -> Dict[str, Any]:
        return {
            "total_vectors_indexed": self.index.ntotal if self.index else 0,
            "vector_dimension": self.index.d if self.index else 0,
            "metadata_records_count": self.metadata_store.get_total_records_count() if self.metadata_store else 0,
            "reload_duration_sec": self.load_time_sec,
            "manifest": self.manifest
        }

    def get_dataset_representative_chunks(self, max_documents: int = 15) -> List[Dict[str, Any]]:
        if hasattr(self, "metadata_store") and self.metadata_store:
            return self.metadata_store.get_dataset_representative_chunks(max_documents=max_documents)
        elif hasattr(self, "entries") and self.entries:
            results = []
            seen = set()
            for entry in self.entries.values():
                if entry.doc_id not in seen:
                    seen.add(entry.doc_id)
                    results.append({
                        "chunk_id": entry.chunk_id,
                        "parent_doc_id": entry.doc_id,
                        "title": entry.metadata.get("title", "Untitled") if entry.metadata else "Untitled",
                        "content": entry.text,
                        "similarity_score": 1.0,
                        "metadata": entry.metadata or {}
                    })
                if len(results) >= max_documents:
                    break
            return results
        return []

    def get_dataset_topic_breakdown(self) -> Dict[str, Any]:
        if hasattr(self, "metadata_store") and self.metadata_store:
            return self.metadata_store.get_dataset_topic_breakdown()
        return {
            "total_chunks": len(getattr(self, "entries", {})),
            "total_documents": len(getattr(self, "entries", {})),
            "categories": {},
            "source_types": {}
        }

