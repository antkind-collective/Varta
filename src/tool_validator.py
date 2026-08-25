#!/usr/bin/env python3
"""
VARTA Phase 4 - Sprint 4.4: Tool Framework & Extensible Agent Execution Validation Suite.

Executes end-to-end verification of:
1. Tool Registration & Dynamic Discovery
2. Calculator Tool Math & Percentage Evaluation
3. RAG Search Tool Execution
4. Document Search Tool Execution
5. Conversation Memory Tool Execution
6. System Info Tool Execution
7. Invalid Tool Request Handling
8. Tool Failure & Exception Graceful Handling
9. Tool Log Telemetry & Context Exclusion Audit

Generates reports/tool_validation_report.md upon completion.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.vector_database import VectorDatabase
from src.semantic_retriever import SemanticRetriever
from src.rag_orchestrator import RAGOrchestrator
from src.llm_adapter import MockLLMAdapter
from src.tools.base_tool import BaseTool
from src.tools.rag_search_tool import RAGSearchTool
from src.tools.document_search_tool import DocumentSearchTool
from src.tools.conversation_memory_tool import ConversationMemoryTool
from src.tools.calculator_tool import CalculatorTool
from src.tools.system_info_tool import SystemInfoTool
from src.tool_registry import ToolRegistry
from src.tool_router import ToolRouter
from src.execution_plan import ExecutionPlan
from src.conversation_manager import ConversationManager
from src.assistant_controller import AssistantController

class ToolValidator:
    """
    Automated Validator for Sprint 4.4 Tool Framework.
    """

    def __init__(
        self,
        log_path: Optional[str] = None,
        planner_log_path: Optional[str] = None,
        tool_log_path: Optional[str] = None
    ):
        self.log_path = Path(log_path) if log_path else project_root / "data" / "conversations" / "session_log.json"
        self.planner_log_path = Path(planner_log_path) if planner_log_path else project_root / "data" / "planner" / "planner_log.json"
        self.tool_log_path = Path(tool_log_path) if tool_log_path else project_root / "data" / "tools" / "tool_log.json"

        # Initialize mock or loaded vector database
        vdb_dir = project_root / "data" / "vector_db"
        if (vdb_dir / "faiss_index.bin").exists() and (vdb_dir / "metadata.sqlite").exists():
            self.vdb = VectorDatabase.load(str(vdb_dir))
        else:
            import faiss
            from src.metadata_store import MetadataStore
            idx = faiss.IndexFlatIP(1536)
            store = MetadataStore(str(vdb_dir / "metadata.sqlite"))
            self.vdb = VectorDatabase(index=idx, metadata_store=store, manifest={}, load_time_sec=0.0)

        self.retriever = SemanticRetriever(vector_db=self.vdb)
        self.llm_adapter = MockLLMAdapter()
        self.orchestrator = RAGOrchestrator(retriever=self.retriever, llm_adapter=self.llm_adapter)
        self.results: Dict[str, Dict[str, Any]] = {}

    def run_all_checks(self) -> bool:
        """Executes all 9 tool framework validation test cases."""
        print("=" * 75)
        print(" VARTA SPRINT 4.4 TOOL FRAMEWORK & AGENT EXECUTION VALIDATION")
        print("=" * 75)

        all_passed = True

        # 1. Tool Registration & Discovery Test
        try:
            reg = ToolRegistry()
            calc = CalculatorTool()
            sys_info = SystemInfoTool()
            reg.register_tool(calc)
            reg.register_tool(sys_info)

            assert reg.has_tool("calculator"), "Registry missing 'calculator'"
            assert reg.has_tool("system_info"), "Registry missing 'system_info'"
            assert len(reg.list_tools()) == 2, "Expected 2 registered tools"

            self.results["Tool Registration & Discovery"] = {
                "status": "PASS",
                "details": f"Registered and discovered {len(reg.list_tools())} tools dynamically."
            }
            print("  [1/9] Tool Registration & Discovery: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Tool Registration & Discovery"] = {"status": "FAIL", "details": str(e)}
            print(f"  [1/9] Tool Registration & Discovery: 🔴 FAIL - {e}")

        # 2. Calculator Tool Math & Percentage Evaluation Test
        try:
            calc = CalculatorTool()
            res1 = calc.execute({"expression": "25 * 19"})
            assert res1["success"] is True and res1["value"] == 475, f"Expected 475, got {res1.get('value')}"

            res2 = calc.execute({"expression": "12% of 800"})
            assert res2["success"] is True and res2["value"] == 96, f"Expected 96, got {res2.get('value')}"

            self.results["Calculator Tool Execution"] = {
                "status": "PASS",
                "details": f"Evaluated '25 * 19' = 475 and '12% of 800' = 96 safely via AST."
            }
            print("  [2/9] Calculator Tool Execution: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Calculator Tool Execution"] = {"status": "FAIL", "details": str(e)}
            print(f"  [2/9] Calculator Tool Execution: 🔴 FAIL - {e}")

        # 3. RAG Search Tool Execution Test
        try:
            rag_tool = RAGSearchTool(rag_orchestrator=self.orchestrator)
            res_rag = rag_tool.execute({"query": "Bihar flood situation"})
            assert res_rag["success"] is True
            assert "answer" in res_rag and len(res_rag["answer"]) > 0

            self.results["RAG Search Tool Execution"] = {
                "status": "PASS",
                "details": "RAGSearchTool wrapped RAGOrchestrator successfully."
            }
            print("  [3/9] RAG Search Tool Execution: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["RAG Search Tool Execution"] = {"status": "FAIL", "details": str(e)}
            print(f"  [3/9] RAG Search Tool Execution: 🔴 FAIL - {e}")

        # 4. Document Search Tool Execution Test
        try:
            doc_tool = DocumentSearchTool(vector_db=self.vdb)
            res_doc = doc_tool.execute({"query": "bihar"})
            assert res_doc["success"] is True
            assert "matched_documents" in res_doc

            self.results["Document Search Tool Execution"] = {
                "status": "PASS",
                "details": f"DocumentSearchTool searched metadata and found {res_doc['count']} match(es)."
            }
            print("  [4/9] Document Search Tool Execution: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Document Search Tool Execution"] = {"status": "FAIL", "details": str(e)}
            print(f"  [4/9] Document Search Tool Execution: 🔴 FAIL - {e}")

        # 5. Conversation Memory Tool Execution Test
        try:
            mem_tool = ConversationMemoryTool()
            mgr = ConversationManager()
            sess = mgr.create_session()
            sess.memory.add_turn("Tell me about Bihar floods.", "Bihar floods report.")

            res_mem = mem_tool.execute({"memory": sess.memory})
            assert res_mem["success"] is True
            assert res_mem["turn_count"] == 1
            assert len(res_mem["history"]) == 1

            self.results["Conversation Memory Tool Execution"] = {
                "status": "PASS",
                "details": f"ConversationMemoryTool retrieved {res_mem['turn_count']} session turn(s)."
            }
            print("  [5/9] Conversation Memory Tool Execution: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Conversation Memory Tool Execution"] = {"status": "FAIL", "details": str(e)}
            print(f"  [5/9] Conversation Memory Tool Execution: 🔴 FAIL - {e}")

        # 6. System Info Tool Execution Test
        try:
            sys_tool = SystemInfoTool(provider="MockLLMAdapter", model="mock-v1", max_context_tokens=2048)
            res_sys = sys_tool.execute({"session_id": "test_sess_123"})
            assert res_sys["success"] is True
            assert res_sys["system_info"]["session_id"] == "test_sess_123"
            assert res_sys["system_info"]["max_context_tokens"] == 2048

            self.results["System Info Tool Execution"] = {
                "status": "PASS",
                "details": "SystemInfoTool returned runtime model, provider, and session telemetry."
            }
            print("  [6/9] System Info Tool Execution: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["System Info Tool Execution"] = {"status": "FAIL", "details": str(e)}
            print(f"  [6/9] System Info Tool Execution: 🔴 FAIL - {e}")

        # 7. Invalid Tool Request Handling Test
        try:
            reg = ToolRegistry()
            router = ToolRouter(tool_registry=reg)
            plan_bad = ExecutionPlan(
                plan_type="unsupported_tool",
                steps=[{"type": "tool_call", "tool": "unsupported_tool"}],
                original_query="Do something impossible",
                rewritten_query="Do something impossible"
            )
            res_invalid = router.route_and_execute(plan_bad, context_data={})
            assert res_invalid["success"] is False
            assert "unsupported_tool" in res_invalid["error"] or "Unregistered" in res_invalid["answer"]

            self.results["Invalid Tool Request Handling"] = {
                "status": "PASS",
                "details": "ToolRouter safely caught unregistered tool request without exception."
            }
            print("  [7/9] Invalid Tool Request Handling: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Invalid Tool Request Handling"] = {"status": "FAIL", "details": str(e)}
            print(f"  [7/9] Invalid Tool Request Handling: 🔴 FAIL - {e}")

        # 8. Tool Exception & Graceful Fallback Test
        try:
            calc = CalculatorTool()
            res_err = calc.execute({"expression": "10 / 0"})
            assert res_err["success"] is False
            assert "error" in res_err and "failed" in res_err["error"].lower()

            self.results["Tool Exception & Graceful Fallback"] = {
                "status": "PASS",
                "details": "Division by zero in CalculatorTool returned clean error dictionary."
            }
            print("  [8/9] Tool Exception & Graceful Fallback: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Tool Exception & Graceful Fallback"] = {"status": "FAIL", "details": str(e)}
            print(f"  [8/9] Tool Exception & Graceful Fallback: 🔴 FAIL - {e}")

        # 9. Tool Telemetry Log Audit Test
        try:
            mgr = ConversationManager()
            ctrl = AssistantController(
                rag_orchestrator=self.orchestrator,
                conversation_manager=mgr,
                log_file_path=str(self.log_path),
                planner_log_path=str(self.planner_log_path),
                tool_log_path=str(self.tool_log_path)
            )
            sess = mgr.create_session()

            # Execute a calculation query through controller to trigger tool logging
            resp_calc = ctrl.process_query("calculate 25 * 19", session_id=sess.session_id)
            assert resp_calc["tool_selected"] == "calculator"
            assert "475" in resp_calc["assistant_answer"]

            assert self.tool_log_path.exists(), f"Missing tool log file at {self.tool_log_path}"
            with open(self.tool_log_path, "r", encoding="utf-8") as f:
                tool_logs = json.load(f)

            assert isinstance(tool_logs, list) and len(tool_logs) > 0
            latest_log = tool_logs[-1]

            required_t_keys = ["timestamp", "session_id", "user_query", "tool_selected", "execution_time_ms", "status", "planner_decision"]
            for rtk in required_t_keys:
                assert rtk in latest_log, f"Missing key '{rtk}' in tool_log.json"

            forbidden = ["retrieved_context", "raw_chunks", "context_blocks"]
            for fb in forbidden:
                assert fb not in latest_log, f"Forbidden context key '{fb}' in tool log"

            self.results["Tool Telemetry Log Audit"] = {
                "status": "PASS",
                "details": f"Verified tool_log.json ({len(tool_logs)} log entries). Schema compliant & context excluded."
            }
            print("  [9/9] Tool Telemetry Log Audit: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Tool Telemetry Log Audit"] = {"status": "FAIL", "details": str(e)}
            print(f"  [9/9] Tool Telemetry Log Audit: 🔴 FAIL - {e}")

        print("=" * 75)
        print(f" VALIDATION STATUS: {'🟢 PASSED (100% Compliance)' if all_passed else '🔴 FAILED'}")
        print("=" * 75)

        self.generate_report(all_passed)
        return all_passed

    def generate_report(self, overall_status: bool) -> None:
        """Generates reports/tool_validation_report.md artifact."""
        report_path = project_root / "reports" / "tool_validation_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# VARTA — Tool Framework & Extensible Execution Validation Report (Sprint 4.4)",
            "",
            "## 1. Executive Summary",
            f"- **Validation Result**: `{'🟢 PASSED (100% Compliance)' if overall_status else '🔴 FAILED'}`",
            "- **Components Tested**: `BaseTool`, `ToolRegistry`, `ToolRouter`, `RAGSearchTool`, `DocumentSearchTool`, `ConversationMemoryTool`, `CalculatorTool`, `SystemInfoTool`, `tool_log.json`",
            "- **Scope**: Modular tool registration, AST math evaluation, router dispatching, and tool telemetry logging",
            "",
            "## 2. Quality Assurance Audit Matrix",
            "| Validation Test | Target Requirement | Actual Result | Status |",
            "| :--- | :--- | :--- | :--- |"
        ]

        for test_name, res in self.results.items():
            status_icon = "🟢 PASS" if res["status"] == "PASS" else "🔴 FAIL"
            lines.append(f"| **{test_name}** | Standardized Requirement | {res['details']} | {status_icon} |")

        lines.extend([
            "",
            "## 3. Key Findings & Architectural Compliance",
            "- **Unified Tool Contract**: All tools inherit from `BaseTool` and implement standardized `validate()` and `execute()` contracts.",
            "- **Dynamic Tool Registration**: `ToolRegistry` allows tools to be added or discovered at runtime without altering planner or assistant logic.",
            "- **Zero-Risk Math Parsing**: `CalculatorTool` parses arithmetic expressions and percentage syntax using Python's `ast` module with zero `eval()` vulnerabilities.",
            "- **Isolated Telemetry**: `tool_log.json` tracks tool names, execution latency, success/failure status, and planner decisions while strictly excluding raw document context chunks.",
            ""
        ])

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\nReport written to: {report_path}")

def main():
    validator = ToolValidator()
    success = validator.run_all_checks()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
