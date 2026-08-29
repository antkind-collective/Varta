import time
from typing import Dict, Any, Optional
from src.tool_registry import ToolRegistry
from src.execution_plan import ExecutionPlan
from src.retrieval_executor import RetrievalExecutor

class ToolRouter:
    """
    Tool Router for VARTA Agent.
    Receives an ExecutionPlan, determines target tool selection from ToolRegistry,
    dispatches inputs to the selected tool, handles tool failures, and returns execution metrics.
    """

    def __init__(self, tool_registry: ToolRegistry, retrieval_executor: Optional[RetrievalExecutor] = None):
        self.tool_registry = tool_registry
        self.retrieval_executor = retrieval_executor

    def route_and_execute(self, plan: ExecutionPlan, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes an execution plan to the target tool or retrieval executor.
        """
        start_time = time.time()
        session_id = context_data.get("session_id", "unknown")
        user_query = plan.original_query

        # Determine target tool name
        target_tool_name = self._select_target_tool(plan)

        # 1. Dispatch to registered built-in tools (calculator, system_info, conversation_memory, document_search)
        if target_tool_name != "rag_search" and self.tool_registry.has_tool(target_tool_name):
            tool = self.tool_registry.get_tool(target_tool_name)
            input_payload = self._build_tool_payload(target_tool_name, plan, context_data)
            
            try:
                result = tool.execute(input_payload)
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                result["tool_selected"] = target_tool_name
                result["execution_time_ms"] = elapsed_ms
                return result
            except Exception as e:
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                return {
                    "success": False,
                    "tool_selected": target_tool_name,
                    "error": f"Tool execution failed: {e}",
                    "answer": f"Error executing tool '{target_tool_name}': {e}",
                    "execution_time_ms": elapsed_ms,
                    "citations": []
                }

        # 2. Dispatch RAG search or multi-step/comparative plans to RAG Search Tool / RetrievalExecutor
        rev_decisions = context_data.get("review_decisions", {})
        research_context = context_data.get("research_context")
        excluded_pids = [pid for pid, dec in rev_decisions.items() if dec == "EXCLUDE"]
        meta_filters = {"excluded_post_ids": excluded_pids} if excluded_pids else None

        if self.retrieval_executor:
            executor_result = self.retrieval_executor.execute_plan(
                plan,
                metadata_filters=meta_filters,
                research_context=research_context
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            executor_result["tool_selected"] = "rag_search"
            executor_result["execution_time_ms"] = elapsed_ms
            return executor_result

        # Fallback if tool_registry has RAG tool registered
        if self.tool_registry.has_tool("rag_search"):
            rag_tool = self.tool_registry.get_tool("rag_search")
            payload = {
                "query": plan.rewritten_query or user_query,
                "research_context": research_context,
                "review_decisions": rev_decisions
            }
            return rag_tool.execute(payload)
            result = rag_tool.execute({"query": plan.rewritten_query, "metadata_filters": meta_filters})
            result["tool_selected"] = "rag_search"
            return result

        return {
            "success": False,
            "tool_selected": target_tool_name,
            "error": f"Unknown or unregistered tool requested: {target_tool_name}",
            "answer": f"Tool '{target_tool_name}' is not registered.",
            "execution_time_ms": round((time.time() - start_time) * 1000, 2),
            "citations": []
        }

    def _select_target_tool(self, plan: ExecutionPlan) -> str:
        """Determines tool selection based on plan_type and step attributes."""
        # Check if plan steps specify explicit tool
        for step in plan.steps:
            if "tool" in step:
                return step["tool"]

        if plan.plan_type in {"calculator", "system_info", "conversation_memory", "document_search"}:
            return plan.plan_type

        return "rag_search"

    def _build_tool_payload(self, tool_name: str, plan: ExecutionPlan, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Constructs input payload specific to each tool."""
        if tool_name == "calculator":
            return {"expression": plan.original_query, "query": plan.original_query}
        elif tool_name == "system_info":
            return {
                "session_id": context_data.get("session_id", "N/A"),
                "provider": context_data.get("provider", "OpenAIAdapter"),
                "model": context_data.get("model", "gpt-4o-mini"),
                "query": plan.original_query
            }
        elif tool_name == "conversation_memory":
            return {"memory": context_data.get("memory")}
        elif tool_name == "document_search":
            return {"query": plan.original_query, "keyword": plan.original_query}
        else:
            return {"query": plan.rewritten_query}
