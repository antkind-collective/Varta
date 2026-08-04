import time
from typing import Dict, Any, List
from src.execution_plan import ExecutionPlan
from src.rag_orchestrator import RAGOrchestrator

class RetrievalExecutor:
    """
    Retrieval Executor for VARTA Agentic Assistant.
    Executes one or more RAG retrieval operations sequentially according to an ExecutionPlan,
    combines multi-step or comparative search results, and synthesizes a unified answer.
    """

    def __init__(self, rag_orchestrator: RAGOrchestrator):
        self.rag_orchestrator = rag_orchestrator

    def execute_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """
        Executes plan steps sequentially and synthesizes final response.
        """
        start_time = time.time()

        # Handle Clarification Plan
        if plan.plan_type == "clarification":
            return {
                "query": plan.original_query,
                "rewritten_query": plan.rewritten_query,
                "plan_type": plan.plan_type,
                "plan_summary": plan.summary_str(),
                "assistant_answer": "Please provide a specific query or topic to search.",
                "confidence": {
                    "score": 0.0,
                    "level": "INVALID_INPUT",
                    "retrieval_support": "NONE",
                    "context_coverage_pct": 0.0
                },
                "citations": [],
                "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                "llm": {
                    "provider": getattr(self.rag_orchestrator.llm_adapter, "__class__", type(self.rag_orchestrator.llm_adapter)).__name__,
                    "model": self.rag_orchestrator.llm_adapter.get_model_name() if hasattr(self.rag_orchestrator.llm_adapter, "get_model_name") else "unknown"
                },
                "sub_query_results": []
            }

        retrieval_steps = plan.get_retrieval_steps()
        
        # Single Retrieval Execution (direct, followup, summarization)
        if len(retrieval_steps) == 1:
            step_query = retrieval_steps[0]["query"]
            rag_output = self.rag_orchestrator.run_pipeline(query=step_query)
            
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            rag_output["plan_type"] = plan.plan_type
            rag_output["plan_summary"] = plan.summary_str()
            rag_output["execution_time_ms"] = elapsed_ms
            rag_output["sub_query_results"] = [
                {
                    "step": 1,
                    "sub_query": step_query,
                    "answer": rag_output.get("answer", ""),
                    "confidence": rag_output.get("confidence", {})
                }
            ]
            return rag_output

        # Multi-Step or Comparative Sequential Retrieval Execution
        sub_results = []
        all_citations = []
        confidence_scores = []
        answers_blocks = []
        total_retrieval_ms = 0.0

        for idx, step in enumerate(retrieval_steps, 1):
            sub_q = step["query"]
            sub_res = self.rag_orchestrator.run_pipeline(query=sub_q)
            
            sub_results.append({
                "step": idx,
                "sub_query": sub_q,
                "target": step.get("target"),
                "answer": sub_res.get("answer", ""),
                "confidence": sub_res.get("confidence", {})
            })

            if sub_res.get("citations"):
                all_citations.extend(sub_res["citations"])
            if sub_res.get("confidence", {}).get("score") is not None:
                confidence_scores.append(sub_res["confidence"]["score"])
            
            answers_blocks.append(f"### Sub-Query {idx}: {sub_q}\n{sub_res.get('answer', '')}")
            total_retrieval_ms += sub_res.get("execution_time_ms", 0.0)

        # Synthesize Combined Multi-Step / Comparative Answer
        synthesized_answer = self._synthesize_multi_step_answer(plan, sub_results)

        # Deduplicate citations by citation_id
        unique_citations = []
        seen_ids = set()
        for cit in all_citations:
            cid = cit.get("citation_id")
            if cid not in seen_ids:
                seen_ids.add(cid)
                unique_citations.append(cit)

        avg_conf_score = round(sum(confidence_scores) / len(confidence_scores), 4) if confidence_scores else 0.5000
        conf_level = "HIGH" if avg_conf_score >= 0.65 else ("MEDIUM" if avg_conf_score >= 0.45 else "LOW")

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        first_llm = sub_results[0] if sub_results else {}
        llm_info = {
            "provider": getattr(self.rag_orchestrator.llm_adapter, "__class__", type(self.rag_orchestrator.llm_adapter)).__name__,
            "model": self.rag_orchestrator.llm_adapter.get_model_name() if hasattr(self.rag_orchestrator.llm_adapter, "get_model_name") else "unknown"
        }

        return {
            "query": plan.original_query,
            "rewritten_query": plan.rewritten_query,
            "plan_type": plan.plan_type,
            "plan_summary": plan.summary_str(),
            "assistant_answer": synthesized_answer,
            "confidence": {
                "score": avg_conf_score,
                "level": conf_level,
                "retrieval_support": "STRONG" if conf_level == "HIGH" else "MODERATE",
                "context_coverage_pct": 50.0
            },
            "citations": unique_citations,
            "execution_time_ms": elapsed_ms,
            "llm": llm_info,
            "sub_query_results": sub_results
        }

    def _synthesize_multi_step_answer(self, plan: ExecutionPlan, sub_results: List[Dict[str, Any]]) -> str:
        """
        Synthesizes answers from multiple sub-query retrievals into a coherent response.
        """
        if plan.plan_type == "comparison":
            header = f"**Comparative Analysis: {plan.original_query}**\n\n"
            blocks = []
            for res in sub_results:
                target = res.get("target") or res.get("sub_query")
                blocks.append(f"#### {target.title() if target else 'Retrieval'}\n{res['answer']}\n")
            
            comparison_footer = "\n**Summary Comparison**:\nBoth regions/entities demonstrate key differences in flood severity and response as detailed in the retrieved documentation above."
            return header + "\n".join(blocks) + comparison_footer

        else:
            # Multi-step synthesis
            header = f"**Multi-Step Analysis Summary**\n\n"
            blocks = []
            for res in sub_results:
                blocks.append(f"**Section {res['step']}: {res['sub_query']}**\n{res['answer']}\n")
            return header + "\n".join(blocks)
