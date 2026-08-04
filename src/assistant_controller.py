import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from src.conversation_manager import ConversationManager
from src.rag_orchestrator import RAGOrchestrator
from src.query_rewriter import QueryRewriter
from src.agent_planner import AgentPlanner
from src.retrieval_executor import RetrievalExecutor
from src.execution_plan import ExecutionPlan
from src.tool_registry import ToolRegistry
from src.tool_router import ToolRouter
from src.tools.rag_search_tool import RAGSearchTool
from src.tools.document_search_tool import DocumentSearchTool
from src.tools.conversation_memory_tool import ConversationMemoryTool
from src.tools.calculator_tool import CalculatorTool
from src.tools.system_info_tool import SystemInfoTool

class AssistantController:
    """
    Single Entry Point to the VARTA Conversational AI Assistant.
    Integrates Conversation Memory, Context Resolution & Query Rewriting, Agentic Retrieval Planning,
    Tool Registry & Router, and Retrieval Execution via RAG Orchestration.
    Formats standardized responses and logs execution telemetry to session_log.json, planner_log.json, and tool_log.json.
    """

    def __init__(
        self,
        rag_orchestrator: RAGOrchestrator,
        conversation_manager: Optional[ConversationManager] = None,
        query_rewriter: Optional[QueryRewriter] = None,
        agent_planner: Optional[AgentPlanner] = None,
        retrieval_executor: Optional[RetrievalExecutor] = None,
        tool_registry: Optional[ToolRegistry] = None,
        tool_router: Optional[ToolRouter] = None,
        log_file_path: Optional[str] = None,
        planner_log_path: Optional[str] = None,
        tool_log_path: Optional[str] = None
    ):
        self.rag_orchestrator = rag_orchestrator
        self.conversation_manager = conversation_manager if conversation_manager else ConversationManager()
        self.query_rewriter = query_rewriter if query_rewriter else QueryRewriter(llm_adapter=self.rag_orchestrator.llm_adapter)
        self.agent_planner = agent_planner if agent_planner else AgentPlanner(llm_adapter=self.rag_orchestrator.llm_adapter)
        self.retrieval_executor = retrieval_executor if retrieval_executor else RetrievalExecutor(rag_orchestrator=self.rag_orchestrator)

        # Initialize Tool Registry & Register Built-in Tools
        self.tool_registry = tool_registry if tool_registry else ToolRegistry()
        self._register_default_tools()

        # Initialize Tool Router
        self.tool_router = tool_router if tool_router else ToolRouter(
            tool_registry=self.tool_registry,
            retrieval_executor=self.retrieval_executor
        )

        project_root = Path(__file__).resolve().parent.parent
        self.log_file_path = Path(log_file_path) if log_file_path else project_root / "data" / "conversations" / "session_log.json"
        self.planner_log_path = Path(planner_log_path) if planner_log_path else project_root / "data" / "planner" / "planner_log.json"
        self.tool_log_path = Path(tool_log_path) if tool_log_path else project_root / "data" / "tools" / "tool_log.json"

    def _register_default_tools(self) -> None:
        """Registers built-in tools into self.tool_registry if not already registered."""
        if not self.tool_registry.has_tool("rag_search"):
            self.tool_registry.register_tool(RAGSearchTool(rag_orchestrator=self.rag_orchestrator))
        if not self.tool_registry.has_tool("document_search"):
            self.tool_registry.register_tool(DocumentSearchTool(vector_db=getattr(self.rag_orchestrator.retriever, "vector_db", None)))
        if not self.tool_registry.has_tool("conversation_memory"):
            self.tool_registry.register_tool(ConversationMemoryTool())
        if not self.tool_registry.has_tool("calculator"):
            self.tool_registry.register_tool(CalculatorTool())
        if not self.tool_registry.has_tool("system_info"):
            provider_name = getattr(self.rag_orchestrator.llm_adapter, "__class__", type(self.rag_orchestrator.llm_adapter)).__name__
            model_name = self.rag_orchestrator.llm_adapter.get_model_name() if hasattr(self.rag_orchestrator.llm_adapter, "get_model_name") else "unknown"
            self.tool_registry.register_tool(SystemInfoTool(
                provider=provider_name,
                model=model_name,
                max_context_tokens=self.rag_orchestrator.max_context_tokens
            ))

    def process_query(self, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes user query through the full tool-enabled agentic conversational pipeline:
        1. Conversation Memory & Session Retrieval
        2. Context Resolver & Query Rewriter
        3. Agentic Planner -> Execution Plan
        4. Tool Router -> Selected Tool / Retrieval Execution
        5. Record turn in Conversation Memory
        6. Format standardized response & write session, planner, and tool logs.
        """
        start_time = time.time()

        # 1. Session & Memory retrieval
        session = None
        if session_id:
            session = self.conversation_manager.get_session(session_id)
        if not session:
            session = self.conversation_manager.create_session(session_id=session_id)

        session.increment_message_count()
        clean_query = query.strip() if query else ""

        # 2. Context Resolution & Query Rewriting
        history = session.memory.get_history()
        rewrite_res = self.query_rewriter.rewrite_query(clean_query, history)

        rewritten_query = rewrite_res["rewritten_query"]
        memory_used = rewrite_res["memory_used"]
        resolution_method = rewrite_res["resolution_method"]

        # 3. Agentic Intent Analysis & Execution Planning
        execution_plan = self.agent_planner.create_plan(
            query=clean_query,
            rewritten_query=rewritten_query,
            memory_used=memory_used,
            history_count=len(history)
        )

        # 4. Tool Routing & Execution
        context_data = {
            "session_id": session.session_id,
            "memory": session.memory,
            "provider": getattr(self.rag_orchestrator.llm_adapter, "__class__", type(self.rag_orchestrator.llm_adapter)).__name__,
            "model": self.rag_orchestrator.llm_adapter.get_model_name() if hasattr(self.rag_orchestrator.llm_adapter, "get_model_name") else "unknown"
        }
        tool_result = self.tool_router.route_and_execute(execution_plan, context_data)

        # 5. Record Turn in Conversation Memory
        assistant_answer = tool_result.get("answer", "")
        turn_data = session.memory.add_turn(
            user_query=clean_query,
            assistant_response=assistant_answer
        )

        # 6. Extract Metadata & Build Standardized Response Schema
        llm_meta = tool_result.get("llm", {})
        provider = llm_meta.get("provider", context_data["provider"])
        model = llm_meta.get("model_name") or llm_meta.get("model", context_data["model"])

        total_latency_ms = round((time.time() - start_time) * 1000, 2)
        tool_selected = tool_result.get("tool_selected", "rag_search")

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
            "confidence": tool_result.get("confidence", {
                "score": 1.0 if tool_selected != "rag_search" else 0.5,
                "level": "HIGH" if tool_selected != "rag_search" else "MEDIUM",
                "retrieval_support": "EXACT_TOOL_EXECUTION",
                "context_coverage_pct": 100.0
            }),
            "citations": tool_result.get("citations", []),
            "execution_time_ms": total_latency_ms,
            "llm": {
                "provider": provider,
                "model": model
            },
            "sub_query_results": tool_result.get("sub_query_results", [])
        }

        # 7. Write Telemetry Logs
        self._log_session_event(response)
        self._log_planner_event(response, execution_plan)
        self._log_tool_event(response, tool_result, execution_plan)

        return response

    def _log_session_event(self, response: Dict[str, Any]) -> None:
        """Logs extended query execution metadata to data/conversations/session_log.json."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": response["session_id"],
            "user_query": response["query"],
            "rewritten_query": response.get("rewritten_query", response["query"]),
            "memory_used": response.get("memory_used", False),
            "turn_number": response.get("turn_number", 0),
            "plan_type": response.get("plan_type", "direct"),
            "tool_selected": response.get("tool_selected", "rag_search"),
            "execution_time": response["execution_time_ms"],
            "confidence": response["confidence"],
            "provider": response["llm"]["provider"],
            "model": response["llm"]["model"]
        }

        try:
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
            logs = []
            if self.log_file_path.exists():
                try:
                    with open(self.log_file_path, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                        if not isinstance(logs, list):
                            logs = []
                except Exception:
                    logs = []

            logs.append(log_entry)

            with open(self.log_file_path, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to write session log entry: {e}")

    def _log_planner_event(self, response: Dict[str, Any], plan: ExecutionPlan) -> None:
        """Logs planner execution telemetry to data/planner/planner_log.json."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": response["session_id"],
            "user_query": response["query"],
            "rewritten_query": response["rewritten_query"],
            "plan_type": plan.plan_type,
            "steps_count": len(plan.steps),
            "execution_path": [step.get("type") for step in plan.steps],
            "total_latency": response["execution_time_ms"],
            "confidence": response["confidence"]
        }

        try:
            self.planner_log_path.parent.mkdir(parents=True, exist_ok=True)
            logs = []
            if self.planner_log_path.exists():
                try:
                    with open(self.planner_log_path, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                        if not isinstance(logs, list):
                            logs = []
                except Exception:
                    logs = []

            logs.append(log_entry)

            with open(self.planner_log_path, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to write planner log entry: {e}")

    def _log_tool_event(self, response: Dict[str, Any], tool_result: Dict[str, Any], plan: ExecutionPlan) -> None:
        """Logs tool execution telemetry to data/tools/tool_log.json."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": response["session_id"],
            "user_query": response["query"],
            "tool_selected": response.get("tool_selected", "rag_search"),
            "execution_time_ms": response["execution_time_ms"],
            "status": "success" if tool_result.get("success", True) else "failure",
            "planner_decision": plan.plan_type
        }

        try:
            self.tool_log_path.parent.mkdir(parents=True, exist_ok=True)
            logs = []
            if self.tool_log_path.exists():
                try:
                    with open(self.tool_log_path, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                        if not isinstance(logs, list):
                            logs = []
                except Exception:
                    logs = []

            logs.append(log_entry)

            with open(self.tool_log_path, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to write tool log entry: {e}")
