import numpy as np
from typing import List, Dict, Any, Optional

class RetrievalEngine:
    """
    Retrieval Engine & Ranking Logic:
    - Ranks candidate results by raw Cosine Similarity score in range [-1.0, 1.0].
    - Applies deduplication / parent document grouping (group_by_parent_doc).
    - Applies minimum similarity score thresholding.
    - Formats 1-based ranks and metadata attributes.
    """

    def __init__(self, min_similarity_score: float = 0.35, group_by_parent_doc: bool = False):
        self.min_similarity_score = min_similarity_score
        self.group_by_parent_doc = group_by_parent_doc

    def rank_and_format(
        self,
        raw_results: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        if not raw_results:
            return []

        # Sort candidate results by similarity_score in descending order
        sorted_results = sorted(raw_results, key=lambda x: x.get("similarity_score", -1.0), reverse=True)

        final_results = []
        seen_parent_docs = set()

        for res in sorted_results:
            score = float(res.get("similarity_score", -1.0))
            if score < self.min_similarity_score:
                continue

            parent_id = res.get("parent_doc_id")

            # Apply parent doc grouping if configured
            if self.group_by_parent_doc and parent_id:
                if parent_id in seen_parent_docs:
                    continue
                seen_parent_docs.add(parent_id)

            formatted = {
                "rank": len(final_results) + 1,
                "similarity_score": round(score, 4),
                "chunk_id": res.get("chunk_id"),
                "parent_doc_id": res.get("parent_doc_id"),
                "chunk_index": res.get("chunk_index", 0),
                "total_chunks": res.get("total_chunks", 1),
                "title": res.get("title"),
                "content": res.get("content"),
                "char_count": res.get("char_count", 0),
                "word_count": res.get("word_count", 0),
                "metadata": res.get("metadata", {})
            }
            final_results.append(formatted)

            if len(final_results) >= top_k:
                break

        return final_results
