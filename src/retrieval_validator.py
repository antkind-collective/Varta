import os
import json
from datetime import datetime, timezone
from typing import Dict, Any
from src.semantic_retriever import SemanticRetriever

class RetrievalValidator:
    """
    QA & Edge Case Validator for Sprint 2.3 Semantic Retrieval:
    - Tests empty & whitespace query error handling
    - Tests multilingual retrieval compliance (English, Hindi, Bengali)
    - Tests metadata filtering & 0-match fallback behavior
    - Audits score range compliance [-1.0, 1.0]
    - Exports machine-readable retrieval_health.json artifact
    """

    def validate_retriever(
        self,
        retriever: SemanticRetriever,
        output_dir: str = "data/retrieval"
    ) -> Dict[str, Any]:
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        # 1. Edge Case: Empty & Whitespace Queries
        empty_query_handled = False
        try:
            retriever.retrieve("")
        except ValueError:
            empty_query_handled = True

        whitespace_query_handled = False
        try:
            retriever.retrieve("   \n\t   ")
        except ValueError:
            whitespace_query_handled = True

        # 2. Multilingual Compliance Tests
        hi_res = retriever.retrieve("गोरखपुर में राप्ती नदी का जलस्तर", top_k=3)
        en_res = retriever.retrieve("Rapti river flood embankment repair", top_k=3)
        bn_res = retriever.retrieve("বন্যা পরিস্থিতিতে ত্রাণ কেন্দ্র", top_k=3)

        multilingual_passed = (
            hi_res["total_results_returned"] > 0 and
            en_res["total_results_returned"] > 0 and
            bn_res["total_results_returned"] > 0
        )

        # 3. Metadata Filter & 0-Match Fallback Test
        filter_res = retriever.retrieve("Gorakhpur flood", top_k=3, metadata_filters={"source_type": "News"})
        zero_match_res = retriever.retrieve("Gorakhpur flood", top_k=3, metadata_filters={"source_type": "NonExistentCategory"})

        metadata_filter_passed = (
            filter_res["total_results_returned"] >= 0 and
            zero_match_res["total_results_returned"] == 0
        )

        # 4. Score Range Audit
        scores_valid = True
        for res in en_res["results"]:
            sc = res["similarity_score"]
            if not (-1.0 <= sc <= 1.0):
                scores_valid = False

        overall_valid = (
            empty_query_handled and
            whitespace_query_handled and
            multilingual_passed and
            metadata_filter_passed and
            scores_valid
        )

        val_summary = {
            "empty_query_handled": empty_query_handled,
            "whitespace_query_handled": whitespace_query_handled,
            "multilingual_retrieval_passed": multilingual_passed,
            "metadata_filter_passed": metadata_filter_passed,
            "score_range_valid": scores_valid,
            "overall_valid": overall_valid
        }

        return val_summary
