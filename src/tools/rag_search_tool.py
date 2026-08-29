from typing import Dict, Any, Optional
from src.tools.base_tool import BaseTool
from src.rag_orchestrator import RAGOrchestrator

class RAGSearchTool(BaseTool):
    """
    RAG Search Tool wrapping RAGOrchestrator for semantic retrieval and response synthesis.
    """

    def __init__(self, rag_orchestrator: RAGOrchestrator):
        self.rag_orchestrator = rag_orchestrator

    @property
    def tool_name(self) -> str:
        return "rag_search"

    @property
    def tool_description(self) -> str:
        return "Executes semantic retrieval across vector database and synthesizes grounded answers with citations."

    def validate(self, input_data: Dict[str, Any]) -> bool:
        if not isinstance(input_data, dict):
            return False
        query = input_data.get("query")
        return bool(query and isinstance(query, str) and query.strip())

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate(input_data):
            return {
                "success": False,
                "error": "Invalid query input for RAGSearchTool.",
                "answer": "Invalid query provided for search.",
                "citations": []
            }

        query = input_data["query"].strip()
        top_k = input_data.get("top_k", 5)
        research_context = input_data.get("research_context")
        review_decisions = input_data.get("review_decisions") or {}

        # Collect excluded post IDs from stakeholder review decisions
        excluded_post_ids = [pid for pid, dec in review_decisions.items() if dec == "EXCLUDE"]
        metadata_filters = {}
        if excluded_post_ids:
            metadata_filters["excluded_post_ids"] = excluded_post_ids

        rag_output = self.rag_orchestrator.run_pipeline(
            query=query,
            top_k=top_k,
            metadata_filters=metadata_filters,
            research_context=research_context
        )
        return {
            "success": True,
            "tool_name": self.tool_name,
            "result": rag_output,
            "answer": rag_output.get("answer", ""),
            "confidence": rag_output.get("confidence", {}),
            "citations": rag_output.get("citations", []),
            "execution_time_ms": rag_output.get("execution_time_ms", 0.0)
        }
