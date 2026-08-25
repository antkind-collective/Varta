#!/usr/bin/env python3
"""
VARTA Phase 5 - Sprint 5.2: Performance Profiling & Optimization Suite.

Measures and profiles:
1. Cold-start vs Warm-request latencies.
2. End-to-end and component-level execution breakdown across 5 benchmark queries:
   - Simple RAG Query: "What is the flood situation in Bihar?"
   - Follow-up Query: "What about Patna?"
   - Tool Query: "25 * 19"
   - Comparison Query: "Compare Bihar and Assam floods."
   - Out-of-Domain Query: "Who won the FIFA World Cup 2022?"
3. Detailed metrics:
   - Query Rewriting Time
   - Planner Time
   - Tool Routing Time
   - Retrieval Time (Embedding + FAISS Search + Metadata Lookup)
   - Context Assembly & Ranking Time
   - Token Budget & Prompt Build Time
   - LLM Invocation Time
   - Telemetry Logging Time
   - LLM Call Count
   - Retrieved Document Count
   - Context Tokens, Input Tokens, Output Tokens, Total Tokens
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.vector_database import VectorDatabase
from src.semantic_retriever import SemanticRetriever
from src.rag_orchestrator import RAGOrchestrator
from src.llm_adapter import get_llm_adapter, BaseLLMAdapter, MockLLMAdapter
from src.conversation_manager import ConversationManager
from src.assistant_controller import AssistantController
from src.query_rewriter import QueryRewriter
from src.agent_planner import AgentPlanner
from src.retrieval_executor import RetrievalExecutor
from src.tool_router import ToolRouter

class InstrumentedOrchestrator(RAGOrchestrator):
    """
    Subclasses RAGOrchestrator to measure internal sub-component latencies.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_pipeline_metrics: Dict[str, Any] = {}

    def run_pipeline(self, query: str, top_k: int = 5, metadata_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pipeline_start_time = time.perf_counter()
        breakdown = {}

        # 1. Semantic Retrieval
        t0 = time.perf_counter()
        retrieval_resp = self.retriever.retrieve(query=query, top_k=top_k, metadata_filters=metadata_filters)
        breakdown["retrieval_ms"] = round((time.perf_counter() - t0) * 1000, 3)

        raw_chunks = retrieval_resp.get("results", [])
        total_retrieved = len(raw_chunks)
        top1_score = raw_chunks[0].get("similarity_score", 0.0) if raw_chunks else 0.0

        # Short-circuit check
        if total_retrieved == 0 or top1_score < self.min_similarity_threshold:
            elapsed_ms = round((time.perf_counter() - pipeline_start_time) * 1000, 3)
            breakdown["context_assembly_ms"] = 0.0
            breakdown["ranking_ms"] = 0.0
            breakdown["token_budget_ms"] = 0.0
            breakdown["prompt_build_ms"] = 0.0
            breakdown["llm_generation_ms"] = 0.0
            breakdown["pipeline_total_ms"] = elapsed_ms
            self.last_pipeline_metrics = breakdown

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
                "execution_time_ms": elapsed_ms,
                "_breakdown": breakdown
            }

        # 2. Context Assembly
        t0 = time.perf_counter()
        assembled_blocks = self.context_assembler.assemble_context(raw_chunks)
        breakdown["context_assembly_ms"] = round((time.perf_counter() - t0) * 1000, 3)

        # 3. Context Ranking
        t0 = time.perf_counter()
        ranked_blocks = self.context_ranker.rank_context_blocks(assembled_blocks)
        breakdown["ranking_ms"] = round((time.perf_counter() - t0) * 1000, 3)

        # 4. Token Budget
        t0 = time.perf_counter()
        packed_blocks, dropped_blocks, context_tokens, utilization_pct = self.token_budget_manager.fit_to_budget(ranked_blocks)
        breakdown["token_budget_ms"] = round((time.perf_counter() - t0) * 1000, 3)

        # 5. Prompt Build
        t0 = time.perf_counter()
        full_prompt, sys_prompt, fmt_context = self.prompt_builder.build_prompt(query, packed_blocks)
        prompt_tokens = self.token_budget_manager.token_counter.count_tokens(full_prompt)
        breakdown["prompt_build_ms"] = round((time.perf_counter() - t0) * 1000, 3)

        # 6. LLM Invocation
        t0 = time.perf_counter()
        llm_response = self.llm_adapter.generate(full_prompt)
        breakdown["llm_generation_ms"] = round((time.perf_counter() - t0) * 1000, 3)

        # 7. Citations & Confidence
        citations = []
        for block in packed_blocks:
            citations.append({
                "citation_id": block.get("citation_id"),
                "similarity_score": block.get("similarity_score"),
                "parent_doc_id": block.get("parent_doc_id"),
                "title": block.get("title"),
                "source_type": block.get("metadata", {}).get("source_type") if block.get("metadata") else None
            })

        conf_level = "HIGH" if top1_score >= 0.70 else ("MEDIUM" if top1_score >= 0.50 else "LOW")
        conf_score = round(float(top1_score * 0.7 + (utilization_pct / 100.0) * 0.3), 4)

        elapsed_ms = round((time.perf_counter() - pipeline_start_time) * 1000, 3)
        breakdown["pipeline_total_ms"] = elapsed_ms
        self.last_pipeline_metrics = breakdown

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
                "model_name": self.llm_adapter.get_model_name(),
                "input_tokens": llm_response.get("input_tokens", prompt_tokens),
                "output_tokens": llm_response.get("output_tokens", max(1, len(llm_response.get("text", "")) // 4)),
                "total_tokens": llm_response.get("total_tokens", prompt_tokens + max(1, len(llm_response.get("text", "")) // 4))
            },
            "answer": llm_response.get("text"),
            "citations": citations,
            "execution_time_ms": elapsed_ms,
            "_breakdown": breakdown
        }


class InstrumentedController:
    """
    Wraps AssistantController components with high-resolution performance timers
    without modifying underlying business logic.
    """

    def __init__(self, controller: AssistantController):
        self.controller = controller

    def process_query_instrumented(self, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        metrics = {
            "query": query,
            "session_id": session_id,
            "timings_ms": {},
            "tokens": {},
            "counts": {},
            "details": {},
            "internal_breakdowns": []
        }

        t_total_start = time.perf_counter()

        # 1. Session Retrieval
        t0 = time.perf_counter()
        session = None
        if session_id:
            session = self.controller.conversation_manager.get_session(session_id)
        if not session:
            session = self.controller.conversation_manager.create_session(session_id=session_id)
        session.increment_message_count()
        clean_query = query.strip() if query else ""
        metrics["timings_ms"]["session_lookup_ms"] = round((time.perf_counter() - t0) * 1000, 3)

        # 2. Context Resolution & Query Rewriting
        t0 = time.perf_counter()
        history = session.memory.get_history()
        rewrite_res = self.controller.query_rewriter.rewrite_query(clean_query, history)
        metrics["timings_ms"]["query_rewriting_ms"] = round((time.perf_counter() - t0) * 1000, 3)

        rewritten_query = rewrite_res["rewritten_query"]
        memory_used = rewrite_res["memory_used"]
        resolution_method = rewrite_res["resolution_method"]
        metrics["details"]["rewritten_query"] = rewritten_query
        metrics["details"]["memory_used"] = memory_used
        metrics["details"]["resolution_method"] = resolution_method

        # 3. Agentic Planner & Intent Analysis
        t0 = time.perf_counter()
        execution_plan = self.controller.agent_planner.create_plan(
            query=clean_query,
            rewritten_query=rewritten_query,
            memory_used=memory_used,
            history_count=len(history)
        )
        metrics["timings_ms"]["planner_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        metrics["details"]["plan_type"] = execution_plan.plan_type
        metrics["counts"]["plan_steps"] = len(execution_plan.steps)

        # 4. Tool Routing & Execution
        context_data = {
            "session_id": session.session_id,
            "memory": session.memory,
            "provider": getattr(self.controller.rag_orchestrator.llm_adapter, "__class__", type(self.controller.rag_orchestrator.llm_adapter)).__name__,
            "model": self.controller.rag_orchestrator.llm_adapter.get_model_name() if hasattr(self.controller.rag_orchestrator.llm_adapter, "get_model_name") else "unknown"
        }

        t0 = time.perf_counter()
        tool_result = self.controller.tool_router.route_and_execute(execution_plan, context_data)
        metrics["timings_ms"]["tool_routing_and_execution_ms"] = round((time.perf_counter() - t0) * 1000, 3)

        tool_selected = tool_result.get("tool_selected", "rag_search")
        metrics["details"]["tool_selected"] = tool_selected

        # 5. Record Turn in Conversation Memory
        t0 = time.perf_counter()
        assistant_answer = tool_result.get("assistant_answer") or tool_result.get("answer", "")
        if not assistant_answer:
            assistant_answer = "Retrieved information successfully from knowledge repository."

        turn_data = session.memory.add_turn(
            user_query=clean_query,
            assistant_response=assistant_answer
        )
        metrics["timings_ms"]["memory_update_ms"] = round((time.perf_counter() - t0) * 1000, 3)

        # 6. Response Construction & Telemetry Logging
        t0 = time.perf_counter()
        llm_meta = tool_result.get("llm", {})
        provider = llm_meta.get("provider", context_data["provider"])
        model = llm_meta.get("model_name") or llm_meta.get("model", context_data["model"])

        response = {
            "session_id": session.session_id,
            "query": clean_query,
            "rewritten_query": rewritten_query,
            "memory_used": memory_used,
            "resolution_method": resolution_method,
            "turn_number": turn_data["turn_number"],
            "execution_plan": execution_plan.to_dict(),
            "plan_type": execution_plan.plan_type,
            "plan_summary": execution_plan.summary_str(),
            "tool_selected": tool_selected,
            "assistant_answer": assistant_answer,
            "confidence": tool_result.get("confidence", {}),
            "citations": tool_result.get("citations", []),
            "execution_time_ms": round((time.perf_counter() - t_total_start) * 1000, 3),
            "llm": {"provider": provider, "model": model},
            "sub_query_results": tool_result.get("sub_query_results", [])
        }

        # Measure Logging Time
        t_log = time.perf_counter()
        self.controller._log_session_event(response)
        self.controller._log_planner_event(response, execution_plan)
        self.controller._log_tool_event(response, tool_result, execution_plan)
        metrics["timings_ms"]["telemetry_logging_ms"] = round((time.perf_counter() - t_log) * 1000, 3)

        total_elapsed_ms = round((time.perf_counter() - t_total_start) * 1000, 3)
        metrics["timings_ms"]["total_latency_ms"] = total_elapsed_ms

        # Extract tokens and retrieval counts
        context_block = tool_result.get("context", {})
        prompt_block = tool_result.get("prompt", {})
        retrieval_block = tool_result.get("retrieval", {})

        metrics["counts"]["retrieved_docs"] = retrieval_block.get("total_retrieved", len(tool_result.get("citations", [])))
        metrics["counts"]["citations_count"] = len(tool_result.get("citations", []))
        metrics["tokens"]["context_tokens"] = context_block.get("total_context_tokens", 0)
        
        # Token metrics
        if tool_result.get("_breakdown"):
            metrics["internal_breakdowns"].append(tool_result["_breakdown"])

        # Check LLM sub-results for token breakdowns
        if "sub_query_results" in tool_result and len(tool_result["sub_query_results"]) > 1:
            metrics["counts"]["llm_calls"] = len(tool_result["sub_query_results"])
        elif tool_result.get("llm_invoked", False) or (tool_selected == "rag_search" and tool_result.get("confidence", {}).get("level") != "INSUFFICIENT"):
            metrics["counts"]["llm_calls"] = 1
        else:
            metrics["counts"]["llm_calls"] = 0

        in_tokens = llm_meta.get("input_tokens", prompt_block.get("total_prompt_tokens", 0))
        out_tokens = llm_meta.get("output_tokens", max(1, len(assistant_answer) // 4) if assistant_answer else 0)
        tot_tokens = llm_meta.get("total_tokens", in_tokens + out_tokens)

        if in_tokens == 0 and tool_selected == "rag_search" and metrics["counts"]["llm_calls"] > 0:
            in_tokens = max(1, (len(clean_query) + context_block.get("total_context_tokens", 0) * 4) // 4)
            tot_tokens = in_tokens + out_tokens

        metrics["tokens"]["input_tokens"] = in_tokens
        metrics["tokens"]["output_tokens"] = out_tokens
        metrics["tokens"]["total_tokens"] = tot_tokens

        metrics["response"] = response
        return metrics


class ProfilerRunner:
    """Orchestrates comprehensive profiling suite."""

    def __init__(self, mode: str = "baseline"):
        self.mode = mode
        self.results: Dict[str, Any] = {}

    def run_profiling(self) -> Dict[str, Any]:
        print("=" * 80)
        print(f" VARTA PERFORMANCE PROFILER [{self.mode.upper()}]")
        print("=" * 80)

        # 1. Measure Cold-Start Initialization
        print("\n[1/3] Measuring Cold-Start Overhead...")
        t_cold_start = time.perf_counter()

        project_root = Path(__file__).resolve().parent.parent
        vdb_dir = project_root / "data" / "vector_db"

        t_vdb_start = time.perf_counter()
        if vdb_dir.exists():
            vdb = VectorDatabase.load(str(vdb_dir))
        else:
            from src.embedding_storage import VectorEntry
            vdb = VectorDatabase(vector_dim=1536)
            vdb.add_entry(VectorEntry(doc_id="doc1", chunk_id="chunk1", embedding=[0.1]*1536, text="Sample text", metadata={"title": "Test"}))
        vdb_init_ms = round((time.perf_counter() - t_vdb_start) * 1000, 3)

        t_ret_start = time.perf_counter()
        retriever = SemanticRetriever(vector_db=vdb)
        retriever_init_ms = round((time.perf_counter() - t_ret_start) * 1000, 3)

        t_llm_start = time.perf_counter()
        llm_adapter = get_llm_adapter()
        llm_init_ms = round((time.perf_counter() - t_llm_start) * 1000, 3)

        orchestrator = InstrumentedOrchestrator(
            retriever=retriever,
            llm_adapter=llm_adapter,
            max_context_tokens=2048
        )
        conv_manager = ConversationManager()
        controller = AssistantController(
            rag_orchestrator=orchestrator,
            conversation_manager=conv_manager
        )

        cold_start_total_ms = round((time.perf_counter() - t_cold_start) * 1000, 3)
        print(f"  - Vector DB Load:     {vdb_init_ms:.2f} ms")
        print(f"  - Retriever Init:     {retriever_init_ms:.2f} ms")
        print(f"  - LLM Adapter Init:   {llm_init_ms:.2f} ms")
        print(f"  - Total Cold Start:   {cold_start_total_ms:.2f} ms")

        cold_start_metrics = {
            "vdb_init_ms": vdb_init_ms,
            "retriever_init_ms": retriever_init_ms,
            "llm_init_ms": llm_init_ms,
            "cold_start_total_ms": cold_start_total_ms
        }

        # 2. Warm Request Profiling Across 5 Benchmark Queries
        print("\n[2/3] Executing 5 Representative Benchmark Queries...")
        instrumented = InstrumentedController(controller)
        
        benchmarks = [
            ("Simple RAG Query", "What is the flood situation in Bihar?", None, False),
            ("Follow-up Query", "What about Patna?", None, True),
            ("Tool Query", "25 * 19", None, False),
            ("Comparison Query", "Compare Bihar and Assam floods.", None, False),
            ("Out-of-Domain Query", "Who won the FIFA World Cup 2022?", None, False)
        ]

        query_metrics: List[Dict[str, Any]] = []
        active_session_id: Optional[str] = None

        for name, q, sess_id, is_followup in benchmarks:
            target_sess_id = active_session_id if is_followup else None
            print(f"\n  -> Profiling: '{name}' ('{q}') [Session: {target_sess_id or 'New'}]")

            res = instrumented.process_query_instrumented(query=q, session_id=target_sess_id)
            res["benchmark_name"] = name
            query_metrics.append(res)

            if not is_followup:
                active_session_id = res["response"]["session_id"]

            t_ms = res["timings_ms"]["total_latency_ms"]
            plan = res["details"]["plan_type"]
            tool = res["details"]["tool_selected"]
            llm_calls = res["counts"]["llm_calls"]
            tot_tok = res["tokens"]["total_tokens"]
            print(f"     Status: Latency={t_ms:.2f}ms | Plan={plan} | Tool={tool} | LLM Calls={llm_calls} | Tokens={tot_tok}")

        # 3. Aggregated Summary
        print("\n[3/3] Profiling Complete. Aggregating Results...")
        summary = {
            "mode": self.mode,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "llm_provider": getattr(llm_adapter, "__class__", type(llm_adapter)).__name__,
            "llm_model": llm_adapter.get_model_name() if hasattr(llm_adapter, "get_model_name") else "unknown",
            "cold_start": cold_start_metrics,
            "queries": query_metrics
        }

        self.results = summary
        return summary


def main():
    mode = "baseline"
    if len(sys.argv) > 1 and "--after" in sys.argv:
        mode = "after_optimization"

    runner = ProfilerRunner(mode=mode)
    results = runner.run_profiling()

    output_dir = project_root / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"profile_{mode}.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nProfile data written to: {out_file}")

if __name__ == "__main__":
    main()
