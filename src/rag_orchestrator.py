import time
from typing import List, Dict, Any, Optional
from src.semantic_retriever import SemanticRetriever
from src.context_assembler import ContextAssembler
from src.context_ranker import ContextRanker
from src.token_budget_manager import TokenBudgetManager
from src.prompt_builder import PromptBuilder
from src.llm_adapter import BaseLLMAdapter, MockLLMAdapter

class RAGOrchestrator:
    """
    RAG Orchestrator & End-to-End Pipeline Coordinator:
    - Coordinates Semantic Retrieval -> Context Assembly -> Ranking -> Token Budgeting -> Prompt Building -> LLM Adapter.
    - Applies deterministic short-circuit for insufficient retrieval results before invoking LLM.
    - Generates structured confidence block in response.
    """

    def __init__(
        self,
        retriever: SemanticRetriever,
        llm_adapter: Optional[BaseLLMAdapter] = None,
        max_context_tokens: int = 2048,
        min_similarity_threshold: float = 0.30,
        merge_overlapping_chunks: bool = True,
        group_by_parent_doc: bool = True
    ):
        self.retriever = retriever
        self.llm_adapter = llm_adapter if llm_adapter else MockLLMAdapter()
        self.max_context_tokens = max_context_tokens
        self.min_similarity_threshold = min_similarity_threshold

        self.context_assembler = ContextAssembler(merge_overlapping_chunks=merge_overlapping_chunks)
        self.context_ranker = ContextRanker()
        self.token_budget_manager = TokenBudgetManager(max_context_tokens=max_context_tokens)
        self.prompt_builder = PromptBuilder()

    def run_pipeline(
        self,
        query: str,
        top_k: int = 5,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        pipeline_start_time = time.time()

        # 1. Execute Semantic Retrieval
        retrieval_resp = self.retriever.retrieve(query=query, top_k=top_k, metadata_filters=metadata_filters)
        raw_chunks = retrieval_resp.get("results", [])
        total_retrieved = len(raw_chunks)
        top1_score = raw_chunks[0].get("similarity_score", 0.0) if raw_chunks else 0.0

        # Deterministic Short-Circuit Check for Insufficient Retrieval Results
        if total_retrieved == 0 or top1_score < self.min_similarity_threshold:
            elapsed_ms = round((time.time() - pipeline_start_time) * 1000, 2)
            return {
                "query": query,
                "llm_invoked": False,
                "confidence": {
                    "score": round(max(0.0, float(top1_score)), 4),
                    "level": "INSUFFICIENT",
                    "retrieval_support": "NONE",
                    "context_coverage_pct": 0.0
                },
                "retrieval": {
                    "total_retrieved": total_retrieved,
                    "top1_score": round(float(top1_score), 4)
                },
                "context": {
                    "assembled_blocks_count": 0,
                    "total_context_tokens": 0,
                    "max_token_budget": self.max_context_tokens,
                    "token_utilization_pct": 0.0,
                    "merged_chunks_count": 0,
                    "dropped_chunks_count": 0
                },
                "prompt": {
                    "system_prompt": self.prompt_builder.system_prompt,
                    "total_prompt_tokens": 0
                },
                "llm": {
                    "provider": self.llm_adapter.__class__.__name__,
                    "model_name": self.llm_adapter.get_model_name()
                },
                "answer": "Insufficient context retrieved from the database to answer this query.",
                "citations": [],
                "execution_time_ms": elapsed_ms
            }

        # 2. Context Assembly & Overlapping Merging
        assembled_blocks = self.context_assembler.assemble_context(raw_chunks)

        # 3. Context Ranking & Prioritization
        ranked_blocks = self.context_ranker.rank_context_blocks(assembled_blocks)

        # 4. Enforce Token Budget
        packed_blocks, dropped_blocks, context_tokens, utilization_pct = self.token_budget_manager.fit_to_budget(ranked_blocks)

        # 5. Build LLM Prompt
        full_prompt, sys_prompt, fmt_context = self.prompt_builder.build_prompt(query, packed_blocks)
        prompt_tokens = self.token_budget_manager.token_counter.count_tokens(full_prompt)

        # 6. Model Communication (LLM Adapter Call)
        llm_response = self.llm_adapter.generate(full_prompt)

        # 7. Extract Citations
        citations = []
        for block in packed_blocks:
            citations.append({
                "citation_id": block.get("citation_id"),
                "similarity_score": block.get("similarity_score"),
                "parent_doc_id": block.get("parent_doc_id"),
                "title": block.get("title"),
                "source_type": block.get("metadata", {}).get("source_type") if block.get("metadata") else None
            })

        # 8. Compute Confidence Score Block
        conf_level = "HIGH" if top1_score >= 0.70 else ("MEDIUM" if top1_score >= 0.50 else "LOW")
        conf_score = round(float(top1_score * 0.7 + (utilization_pct / 100.0) * 0.3), 4)

        elapsed_ms = round((time.time() - pipeline_start_time) * 1000, 2)

        return {
            "query": query,
            "llm_invoked": True,
            "confidence": {
                "score": conf_score,
                "level": conf_level,
                "retrieval_support": "STRONG" if conf_level == "HIGH" else "MODERATE",
                "context_coverage_pct": utilization_pct
            },
            "retrieval": {
                "total_retrieved": total_retrieved,
                "top1_score": round(float(top1_score), 4)
            },
            "context": {
                "assembled_blocks_count": len(packed_blocks),
                "total_context_tokens": context_tokens,
                "max_token_budget": self.max_context_tokens,
                "token_utilization_pct": utilization_pct,
                "merged_chunks_count": max(0, total_retrieved - len(assembled_blocks)),
                "dropped_chunks_count": len(dropped_blocks)
            },
            "prompt": {
                "system_prompt": sys_prompt,
                "total_prompt_tokens": prompt_tokens
            },
            "llm": {
                "provider": self.llm_adapter.__class__.__name__,
                "model_name": self.llm_adapter.get_model_name()
            },
            "answer": llm_response.get("text"),
            "citations": citations,
            "execution_time_ms": elapsed_ms
        }
