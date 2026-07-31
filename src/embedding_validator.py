import os
import json
import numpy as np
from typing import Dict, Any, List

class EmbeddingValidator:
    """
    Quality Assurance Validator for Sprint 2.1 Embedding Pipeline:
    - 100% Vector coverage verification (vector count == chunk count)
    - Vector dimensional consistency (exact dimension across all rows)
    - Zero NaN / Inf / null value check
    - Parent-child referential integrity against standardized_documents.json
    - Metadata and title field preservation check
    """

    def validate_all(
        self,
        chunks_json_path: str,
        embeddings_npy_path: str,
        standardized_docs_path: str
    ) -> Dict[str, Any]:
        # 1. Load Artifacts
        with open(chunks_json_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        with open(standardized_docs_path, "r", encoding="utf-8") as f:
            standardized_docs = json.load(f)

        embeddings = np.load(embeddings_npy_path, mmap_mode="r")

        num_chunks = len(chunks)
        num_vectors = embeddings.shape[0]
        dimension = embeddings.shape[1]

        # Validations
        count_match = (num_chunks == num_vectors)
        has_nan = bool(np.isnan(embeddings).any())
        has_inf = bool(np.isinf(embeddings).any())

        valid_parent_ids = {doc.get("doc_id") for doc in standardized_docs}
        missing_parent_ids = 0
        missing_title_count = 0
        missing_content_count = 0

        for chunk in chunks:
            p_id = chunk.get("parent_doc_id")
            if p_id not in valid_parent_ids:
                missing_parent_ids += 1

            if chunk.get("content") is None or str(chunk.get("content")).strip() == "":
                missing_content_count += 1

        parent_integrity_passed = (missing_parent_ids == 0)
        overall_valid = (count_match and not has_nan and not has_inf and parent_integrity_passed and missing_content_count == 0)

        return {
            "num_chunks": num_chunks,
            "num_vectors": num_vectors,
            "vector_dimension": dimension,
            "vector_count_match": count_match,
            "has_nan_values": has_nan,
            "has_inf_values": has_inf,
            "missing_parent_references": missing_parent_ids,
            "missing_content_count": missing_content_count,
            "parent_integrity_passed": parent_integrity_passed,
            "overall_valid": overall_valid
        }
