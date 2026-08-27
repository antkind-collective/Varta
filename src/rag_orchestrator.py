import time
import re
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
        max_context_tokens: int = 3500,
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

    @staticmethod
    def is_dataset_summary_query(query: str) -> bool:
        """
        Determines whether a user query is asking for an overview or summary of the
        entire uploaded dataset as a whole, rather than querying a specific document or topic.
        """
        clean = query.strip().lower()
        if not clean:
            return False

        has_dataset_term = bool(
            re.search(r"\b(?:data\s*set|dataset|entire\s+data|whole\s+data|all\s+data|uploaded\s+data|corpus|whole\s+collection)\b", clean)
            or re.search(r"(?:डेटासेट|पूरे\s+डेटा|संपूर्ण\s+डेटा)", clean)
        )
        has_whole_scope = bool(
            re.search(r"\b(?:whole|entire|all|complete|uploaded|overall|full|total)\b", clean)
            or re.search(r"(?:पूरे|संपूर्ण|सभी|कुल|समस्त)", clean)
        )
        has_summary_intent = bool(
            re.search(r"\b(?:summary|summarize|overview|outline|brief|what\s+is\s+in|what\s+does\s+.*\s+contain|what\s+is\s+.*\s+about|what\s+do\s+we\s+have)\b", clean)
            or re.search(r"(?:सारांश|संक्षेप|विवरण|ब्योरा|क्या\s+है)", clean)
        )

        if has_dataset_term and (has_whole_scope or has_summary_intent):
            if re.search(r"\b(?:summary|summarize|overview|what\s+is\s+in|what\s+does\s+.*\s+contain|what\s+is\s+this\s+.*about|tell\s+me\s+about)\b", clean) or has_whole_scope:
                return True
            if clean in ["dataset summary", "whole dataset", "entire dataset", "dataset overview"]:
                return True

        if re.search(r"\b(?:summary|overview)\s+of\s+(?:the\s+)?(?:whole\s+|entire\s+|uploaded\s+)?(?:data\s*set|dataset|corpus)\b", clean):
            return True

        if re.search(r"^summarize\s+(?:the\s+|this\s+|our\s+|uploaded\s+)?(?:whole\s+|entire\s+)?(?:data\s*set|dataset|corpus)\b", clean):
            return True

        if re.search(r"(?:डेटासेट|डेटा)\s*(?:का)?\s*(?:सारांश|संक्षेप|विवरण)", clean) or re.search(r"(?:पूरे|संपूर्ण)\s+डेटासेट", clean):
            return True

        return False

    def run_dataset_summary(
        self,
        query: str,
        max_documents: int = 15
    ) -> Dict[str, Any]:
        """
        Executes dataset-level summarization across the entire uploaded corpus.
        Gathers representative opening chunks across diverse topics/categories,
        assembles and budgets context blocks, and synthesizes a fully grounded overview
        preserving citations and source provenance.
        """
        pipeline_start_time = time.time()

        # 1. Retrieve representative chunks across distinct topics & parent documents
        raw_chunks = self.retriever.get_dataset_representative_chunks(max_documents=max_documents)
        total_retrieved = len(raw_chunks)

        # Short-circuit if vector database has 0 records
        if total_retrieved == 0:
            elapsed_ms = round((time.time() - pipeline_start_time) * 1000, 2)
            return {
                "query": query,
                "llm_invoked": False,
                "confidence": {
                    "score": 0.0,
                    "level": "INSUFFICIENT",
                    "retrieval_support": "NONE",
                    "context_coverage_pct": 0.0
                },
                "retrieval": {
                    "total_retrieved": 0,
                    "top1_score": 0.0
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
            parent_id = block.get("parent_doc_id") or ""
            if parent_id and (parent_id.startswith("http://") or parent_id.startswith("https://")):
                parent_id = re.sub(r'\.\d+$', '', parent_id)

            meta = block.get("metadata", {}) if block.get("metadata") else {}
            explicit_url = meta.get("source_url")

            source_url = None
            if explicit_url and (str(explicit_url).startswith("http://") or str(explicit_url).startswith("https://")):
                source_url = re.sub(r'\.\d+$', '', str(explicit_url).strip())
            elif parent_id and (str(parent_id).startswith("http://") or str(parent_id).startswith("https://")):
                source_url = parent_id
            elif meta.get("post_id") and (str(meta.get("post_id")).startswith("http://") or str(meta.get("post_id")).startswith("https://")):
                source_url = re.sub(r'\.\d+$', '', str(meta.get("post_id")).strip())

            doc_id = parent_id if parent_id else (meta.get("post_id") or "N/A")

            citations.append({
                "citation_id": block.get("citation_id"),
                "similarity_score": block.get("similarity_score", 1.0),
                "parent_doc_id": doc_id,
                "doc_id": doc_id,
                "source_url": source_url,
                "title": block.get("title"),
                "source_type": meta.get("source_type")
            })

        conf_score = round(float(0.70 + (utilization_pct / 100.0) * 0.30), 4)
        elapsed_ms = round((time.time() - pipeline_start_time) * 1000, 2)

        return {
            "query": query,
            "llm_invoked": True,
            "confidence": {
                "score": conf_score,
                "level": "HIGH",
                "retrieval_support": "STRONG",
                "context_coverage_pct": utilization_pct
            },
            "retrieval": {
                "total_retrieved": total_retrieved,
                "top1_score": 1.0
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

    def run_pipeline(
        self,
        query: str,
        top_k: int = 5,
        metadata_filters: Optional[Dict[str, Any]] = None,
        is_dataset_summary: Optional[bool] = None,
        research_context: Optional[Any] = None
    ) -> Dict[str, Any]:
        pipeline_start_time = time.time()

        # Check if query requests a dataset-level summary
        if is_dataset_summary is True or (is_dataset_summary is None and not metadata_filters and not research_context and self.is_dataset_summary_query(query)):
            return self.run_dataset_summary(query=query)

        # -------------------------------------------------------------
        # LAYER 1: Scope Candidate Corpus using active ResearchContext
        # -------------------------------------------------------------
        active_filters = dict(metadata_filters) if metadata_filters else {}

        if research_context and hasattr(self.retriever, "vector_db") and self.retriever.vector_db:
            geography = getattr(research_context, "geography", None)
            specific_location = getattr(research_context, "specific_location", None)
            domain = getattr(research_context, "domain", "disaster")
            disaster_types = getattr(research_context, "disaster_types", None)

            if geography or specific_location or domain or disaster_types:
                scoped_vids = self.retriever.vector_db.get_scoped_vector_ids(
                    geography=geography,
                    specific_location=specific_location,
                    domain=domain,
                    disaster_types=disaster_types,
                    limit=5000
                )
                if scoped_vids:
                    active_filters["allowed_vector_ids"] = scoped_vids

        # -------------------------------------------------------------
        # LAYER 2: Execute Semantic Retrieval on Query / Analytical Intent
        # -------------------------------------------------------------
        fetch_limit = max(top_k * 3, 10) if research_context else top_k
        retrieval_resp = self.retriever.retrieve(query=query, top_k=fetch_limit, metadata_filters=active_filters if active_filters else None)
        raw_chunks = retrieval_resp.get("results", [])

        # -------------------------------------------------------------
        # LAYER 3: Final Context Validation Safety Gate
        # -------------------------------------------------------------
        if research_context and raw_chunks:
            try:
                from src.context_relevance_engine import ContextRelevanceEngine
                rel_engine = ContextRelevanceEngine(embedding_provider=self.retriever.embedding_provider)
                validated_chunks = []
                for chunk in raw_chunks:
                    eval_res = rel_engine.evaluate_record(
                        chunk,
                        context=research_context,
                        precomputed_semantic_score=chunk.get("similarity_score")
                    )
                    if eval_res.get("relevance_decision") != "EXCLUDE":
                        chunk["relevance_decision"] = eval_res.get("relevance_decision")
                        chunk["context_relevance_score"] = eval_res.get("context_relevance_score")
                        validated_chunks.append(chunk)
                    if len(validated_chunks) >= top_k:
                        break
                
                if validated_chunks:
                    raw_chunks = validated_chunks
                elif not active_filters.get("allowed_vector_ids"):
                    # If unconstrained search brought only excluded docs, discard them
                    raw_chunks = []
            except Exception as e:
                pass

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
            parent_id = block.get("parent_doc_id") or ""
            if parent_id and (parent_id.startswith("http://") or parent_id.startswith("https://")):
                parent_id = re.sub(r'\.\d+$', '', parent_id)

            meta = block.get("metadata", {}) if block.get("metadata") else {}
            explicit_url = meta.get("source_url")
            
            # Determine canonical source_url (only genuine URLs, never fabricated)
            source_url = None
            if explicit_url and (str(explicit_url).startswith("http://") or str(explicit_url).startswith("https://")):
                source_url = re.sub(r'\.\d+$', '', str(explicit_url).strip())
            elif parent_id and (str(parent_id).startswith("http://") or str(parent_id).startswith("https://")):
                source_url = parent_id
            elif meta.get("post_id") and (str(meta.get("post_id")).startswith("http://") or str(meta.get("post_id")).startswith("https://")):
                source_url = re.sub(r'\.\d+$', '', str(meta.get("post_id")).strip())

            doc_id = parent_id if parent_id else (meta.get("post_id") or "N/A")

            citations.append({
                "citation_id": block.get("citation_id"),
                "similarity_score": block.get("similarity_score"),
                "parent_doc_id": doc_id,
                "doc_id": doc_id,
                "source_url": source_url,
                "title": block.get("title"),
                "source_type": meta.get("source_type")
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

