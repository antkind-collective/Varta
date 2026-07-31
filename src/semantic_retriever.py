import time
import numpy as np
from typing import List, Dict, Any, Optional
from src.query_processor import QueryProcessor
from src.retrieval_engine import RetrievalEngine
from src.vector_database import VectorDatabase
from src.embedding_providers import BaseEmbeddingProvider, SentenceTransformersProvider

class SemanticRetriever:
    """
    VARTA SemanticRetriever Facade Class:
    - Backend-Agnostic: Communicates EXCLUSIVELY with the VectorDatabase facade.
    - Zero direct dependencies on FAISS, C++ vector indices, or SQLite internals.
    - Coordinates Query Preprocessing -> Embedding Generation -> VectorDB Search -> Ranking.
    - Returns structured JSON retrieval results with raw Cosine Similarity scores in [-1.0, 1.0].
    """

    def __init__(
        self,
        vector_db: VectorDatabase,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        min_similarity_score: float = -1.0,
        group_by_parent_doc: bool = False
    ):
        self.vector_db = vector_db
        if embedding_provider is None:
            self.embedding_provider = SentenceTransformersProvider()
        else:
            self.embedding_provider = embedding_provider

        self.query_processor = QueryProcessor()
        self.retrieval_engine = RetrievalEngine(
            min_similarity_score=min_similarity_score,
            group_by_parent_doc=group_by_parent_doc
        )

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        start_time = time.time()

        # 1. Process & Validate Query
        processed_query = self.query_processor.process(query)

        # 2. Add model prefix if applicable (e.g. "query: " for E5)
        embed_input = processed_query
        if hasattr(self.embedding_provider, "query_prefix") and self.embedding_provider.query_prefix:
            embed_input = f"{self.embedding_provider.query_prefix}{processed_query}"

        # 3. Generate Query Vector Embedding
        query_vector = self.embedding_provider.embed_query(embed_input)

        # 4. Search VectorDatabase (Backend-Agnostic Facade Call)
        raw_candidates = self.vector_db.search(
            query_vector=query_vector,
            top_k=top_k,
            metadata_filters=metadata_filters
        )

        # 5. Rank and Format Results
        ranked_results = self.retrieval_engine.rank_and_format(raw_candidates, top_k=top_k)

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "query": query,
            "processed_query": processed_query,
            "top_k": top_k,
            "execution_time_ms": elapsed_ms,
            "total_results_returned": len(ranked_results),
            "metadata_filters_applied": metadata_filters,
            "results": ranked_results
        }
