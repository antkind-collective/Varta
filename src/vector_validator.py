import os
import json
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any
from src.vector_database import VectorDatabase

class VectorValidator:
    """
    Quality Assurance & Health Validator for Sprint 2.2 Vector Database:
    - Integrity verification: vector count == metadata count == expected chunks count
    - Dimensional consistency check
    - Duplicate chunk_id check
    - Orphan vector & orphan metadata check
    - Self-vector cosine similarity accuracy check
    - Exports machine-readable index_health.json artifact
    """

    def validate_vector_database(
        self,
        db_dir: str,
        embeddings_npy_path: str,
        chunks_json_path: str
    ) -> Dict[str, Any]:
        db_dir = os.path.abspath(db_dir)

        # 1. Reload DB & Measure Load Time
        reload_success = True
        try:
            vdb = VectorDatabase.load(db_dir)
            reload_sec = vdb.load_time_sec
        except Exception as e:
            reload_success = False
            reload_sec = -1.0
            vdb = None

        if not reload_success or vdb is None:
            return {
                "status": "UNHEALTHY",
                "overall_valid": False,
                "reload_successful": False,
                "error": "Failed to reload VectorDatabase from disk"
            }

        # Load input matrices
        embeddings = np.load(embeddings_npy_path, mmap_mode="r")
        with open(chunks_json_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        expected_count = len(chunks)
        faiss_ntotal = vdb.index.ntotal
        meta_count = vdb.metadata_store.get_total_records_count()
        dim = vdb.index.d

        count_match = (faiss_ntotal == meta_count == expected_count == 39172)
        dim_match = (dim == embeddings.shape[1])

        # Check duplicate IDs & Orphan records
        unique_chunk_ids = {c["chunk_id"] for c in chunks}
        duplicate_ids_count = expected_count - len(unique_chunk_ids)

        orphan_vectors_count = max(0, faiss_ntotal - meta_count)
        orphan_metadata_count = max(0, meta_count - faiss_ntotal)

        # 2. Self-Vector Retrieval Test
        test_vec = embeddings[0]
        search_res = vdb.search(test_vec, top_k=1)
        
        self_search_passed = False
        top_score = 0.0
        if search_res:
            top_score = search_res[0].get("similarity_score", 0.0)
            self_search_passed = (top_score >= 0.999)

        # 3. Referential Alignment Test
        first_chunk = chunks[0]
        first_db_chunk = vdb.get_chunk_by_id(first_chunk["chunk_id"])
        alignment_passed = (first_db_chunk is not None and first_db_chunk.get("parent_doc_id") == first_chunk["parent_doc_id"])

        overall_valid = (
            reload_success and
            count_match and
            dim_match and
            self_search_passed and
            alignment_passed and
            duplicate_ids_count == 0 and
            orphan_vectors_count == 0 and
            orphan_metadata_count == 0
        )

        health_data = {
            "project": "VARTA",
            "phase": "Phase 2 - Knowledge Layer",
            "sprint": "Sprint 2.2 - Vector Database Indexing",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "HEALTHY" if overall_valid else "UNHEALTHY",
            "health_score_pct": 100.0 if overall_valid else 0.0,
            "duplicate_ids_count": duplicate_ids_count,
            "orphan_vectors_count": orphan_vectors_count,
            "orphan_metadata_count": orphan_metadata_count,
            "dimensional_consistency": dim_match,
            "reload_successful": reload_success,
            "overall_database_health": overall_valid
        }

        # Export index_health.json
        health_json_path = os.path.join(db_dir, "index_health.json")
        with open(health_json_path, "w", encoding="utf-8") as f:
            json.dump(health_data, f, ensure_ascii=False, indent=4)

        return {
            "expected_chunks_count": expected_count,
            "faiss_indexed_vectors": faiss_ntotal,
            "sqlite_metadata_records": meta_count,
            "vector_dimension": dim,
            "reload_duration_sec": reload_sec,
            "reload_successful": reload_success,
            "count_match_passed": count_match,
            "dimension_match_passed": dim_match,
            "self_similarity_top1_score": top_score,
            "self_similarity_passed": self_search_passed,
            "referential_alignment_passed": alignment_passed,
            "overall_valid": overall_valid,
            "health_data": health_data,
            "health_json_path": health_json_path
        }
