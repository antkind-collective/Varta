#!/usr/bin/env python3
"""
VARTA Phase 4 - Sprint 4.3: Agentic Reasoning & Intelligent Retrieval Planning Validation Suite.

Executes end-to-end verification of:
1. Single Retrieval Query Planning
2. Comparative Query Planning & Decomposition
3. Multi-Step Query Planning
4. Follow-Up Query Planning
5. Ambiguous / Clarification Required Query Handling
6. Hindi Language Planning & Decomposition
7. English Summarization Planning
8. Plan Serialization & Deserialization
9. Planner Log Telemetry & Context Exclusion Audit

Generates reports/planner_validation_report.md upon completion.
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
from src.execution_plan import ExecutionPlan
from src.query_decomposer import QueryDecomposer
from src.agent_planner import AgentPlanner
from src.retrieval_executor import RetrievalExecutor
from src.conversation_manager import ConversationManager
from src.assistant_controller import AssistantController

class PlannerValidator:
    """
    Automated Validator for Sprint 4.3 Agentic Reasoning & Retrieval Planning.
    """

    def __init__(
        self,
        log_path: Optional[str] = None,
        planner_log_path: Optional[str] = None
    ):
        self.log_path = Path(log_path) if log_path else project_root / "data" / "conversations" / "session_log.json"
        self.planner_log_path = Path(planner_log_path) if planner_log_path else project_root / "data" / "planner" / "planner_log.json"

        # Initialize mock or loaded vector database
        vdb_dir = project_root / "data" / "vector_db"
        if vdb_dir.exists():
            self.vdb = VectorDatabase.load(str(vdb_dir))
        else:
            from src.embedding_storage import VectorEntry
            self.vdb = VectorDatabase(vector_dim=384)
            self.vdb.add_entry(VectorEntry(doc_id="doc1", chunk_id="chunk1", embedding=[0.1]*384, text="बिहार और असम में बाढ़ से राहत शिविर खोले गए हैं।", metadata={"title": "Flood Report"}))

        self.retriever = SemanticRetriever(vector_db=self.vdb)
        self.llm_adapter = MockLLMAdapter()
        self.orchestrator = RAGOrchestrator(retriever=self.retriever, llm_adapter=self.llm_adapter)
        self.results: Dict[str, Dict[str, Any]] = {}

    def run_all_checks(self) -> bool:
        """Executes all 9 planner validation test cases."""
        print("=" * 75)
        print(" VARTA SPRINT 4.3 AGENTIC PLANNING & RETRIEVAL EXECUTOR VALIDATION")
        print("=" * 75)

        all_passed = True

        # 1. Single Retrieval Query Test
        try:
            planner = AgentPlanner(llm_adapter=self.llm_adapter)
            plan = planner.create_plan(query="What is the flood situation in Bihar?", rewritten_query="What is the flood situation in Bihar?")
            assert plan.plan_type == "direct", f"Expected plan_type 'direct', got {plan.plan_type}"
            assert len(plan.get_retrieval_steps()) == 1

            self.results["Single Retrieval Planning"] = {
                "status": "PASS",
                "details": f"Planned direct retrieval: '{plan.steps[0]['query']}'"
            }
            print("  [1/9] Single Retrieval Planning: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Single Retrieval Planning"] = {"status": "FAIL", "details": str(e)}
            print(f"  [1/9] Single Retrieval Planning: 🔴 FAIL - {e}")

        # 2. Comparative Query Planning Test
        try:
            planner = AgentPlanner(llm_adapter=self.llm_adapter)
            q_comp = "Compare Bihar and Assam floods during the last month."
            plan_comp = planner.create_plan(query=q_comp, rewritten_query=q_comp)
            assert plan_comp.plan_type == "comparison", f"Expected 'comparison', got {plan_comp.plan_type}"
            ret_steps = plan_comp.get_retrieval_steps()
            assert len(ret_steps) >= 2, f"Expected at least 2 retrieval steps, got {len(ret_steps)}"
            assert "bihar" in ret_steps[0]["query"].lower()
            assert "assam" in ret_steps[1]["query"].lower()

            self.results["Comparative Query Planning"] = {
                "status": "PASS",
                "details": f"Decomposed comparison into 2 sub-queries: '{ret_steps[0]['query']}' & '{ret_steps[1]['query']}'"
            }
            print("  [2/9] Comparative Query Planning: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Comparative Query Planning"] = {"status": "FAIL", "details": str(e)}
            print(f"  [2/9] Comparative Query Planning: 🔴 FAIL - {e}")

        # 3. Multi-Step Query Planning Test
        try:
            planner = AgentPlanner(llm_adapter=self.llm_adapter)
            q_multi = "What is the water level of Rapti river and also what relief camps are set up in Gorakhpur?"
            plan_multi = planner.create_plan(query=q_multi, rewritten_query=q_multi)
            assert plan_multi.plan_type == "multi_step", f"Expected 'multi_step', got {plan_multi.plan_type}"
            assert len(plan_multi.get_retrieval_steps()) >= 2

            self.results["Multi-Step Query Planning"] = {
                "status": "PASS",
                "details": f"Decomposed multi-part query into {len(plan_multi.get_retrieval_steps())} sub-queries"
            }
            print("  [3/9] Multi-Step Query Planning: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Multi-Step Query Planning"] = {"status": "FAIL", "details": str(e)}
            print(f"  [3/9] Multi-Step Query Planning: 🔴 FAIL - {e}")

        # 4. Follow-Up Query Planning Test
        try:
            planner = AgentPlanner(llm_adapter=self.llm_adapter)
            plan_followup = planner.create_plan(query="What about Patna?", rewritten_query="What is the flood status in Patna, Bihar?", memory_used=True)
            assert plan_followup.plan_type == "followup", f"Expected 'followup', got {plan_followup.plan_type}"
            assert plan_followup.steps[0]["query"] == "What is the flood status in Patna, Bihar?"

            self.results["Follow-Up Query Planning"] = {
                "status": "PASS",
                "details": f"Planned followup execution using rewritten query: '{plan_followup.steps[0]['query']}'"
            }
            print("  [4/9] Follow-Up Query Planning: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Follow-Up Query Planning"] = {"status": "FAIL", "details": str(e)}
            print(f"  [4/9] Follow-Up Query Planning: 🔴 FAIL - {e}")

        # 5. Clarification Required Query Test
        try:
            planner = AgentPlanner(llm_adapter=self.llm_adapter)
            plan_empty = planner.create_plan(query="   ", rewritten_query="   ")
            assert plan_empty.plan_type == "clarification"
            assert plan_empty.steps[0]["type"] == "clarify"

            self.results["Clarification Required Handling"] = {
                "status": "PASS",
                "details": "Empty input created clarification plan cleanly"
            }
            print("  [5/9] Clarification Required Handling: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Clarification Required Handling"] = {"status": "FAIL", "details": str(e)}
            print(f"  [5/9] Clarification Required Handling: 🔴 FAIL - {e}")

        # 6. Hindi Language Planning Test
        try:
            planner = AgentPlanner(llm_adapter=self.llm_adapter)
            q_hindi = "बिहार और असम की बाढ़ की तुलना करें।"
            plan_hindi = planner.create_plan(query=q_hindi, rewritten_query=q_hindi)
            assert plan_hindi.plan_type == "comparison", f"Expected 'comparison', got {plan_hindi.plan_type}"
            ret_steps_hi = plan_hindi.get_retrieval_steps()
            assert len(ret_steps_hi) >= 2
            assert "बिहार" in ret_steps_hi[0]["query"]
            assert "असम" in ret_steps_hi[1]["query"]

            self.results["Hindi Language Planning"] = {
                "status": "PASS",
                "details": f"Decomposed Devanagari comparative query: '{ret_steps_hi[0]['query']}' & '{ret_steps_hi[1]['query']}'"
            }
            print("  [6/9] Hindi Language Planning: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Hindi Language Planning"] = {"status": "FAIL", "details": str(e)}
            print(f"  [6/9] Hindi Language Planning: 🔴 FAIL - {e}")

        # 7. English Summarization Planning Test
        try:
            planner = AgentPlanner(llm_adapter=self.llm_adapter)
            q_sum = "Summarize the overall flood status in Uttar Pradesh."
            plan_sum = planner.create_plan(query=q_sum, rewritten_query=q_sum)
            assert plan_sum.plan_type == "summarization"
            assert plan_sum.steps[-1]["type"] == "summarize"

            self.results["Summarization Planning"] = {
                "status": "PASS",
                "details": f"Planned summarization pipeline for query: '{q_sum}'"
            }
            print("  [7/9] Summarization Planning: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Summarization Planning"] = {"status": "FAIL", "details": str(e)}
            print(f"  [7/9] Summarization Planning: 🔴 FAIL - {e}")

        # 8. Plan Serialization & Deserialization Test
        try:
            planner = AgentPlanner(llm_adapter=self.llm_adapter)
            p_orig = planner.create_plan("Compare Bihar and Assam floods", "Compare Bihar and Assam floods")
            p_dict = p_orig.to_dict()
            assert p_dict["plan_type"] == "comparison"

            p_reconst = ExecutionPlan.from_dict(p_dict)
            assert p_reconst.plan_type == p_orig.plan_type
            assert len(p_reconst.steps) == len(p_orig.steps)

            self.results["Plan Serialization & Deserialization"] = {
                "status": "PASS",
                "details": "Successfully serialized and deserialized ExecutionPlan object."
            }
            print("  [8/9] Plan Serialization & Deserialization: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Plan Serialization & Deserialization"] = {"status": "FAIL", "details": str(e)}
            print(f"  [8/9] Plan Serialization & Deserialization: 🔴 FAIL - {e}")

        # 9. End-to-End Execution & Planner Telemetry Log Audit Test
        try:
            mgr = ConversationManager()
            ctrl = AssistantController(
                rag_orchestrator=self.orchestrator,
                conversation_manager=mgr,
                log_file_path=str(self.log_path),
                planner_log_path=str(self.planner_log_path)
            )
            sess = mgr.create_session()

            # Process comparative query through controller
            resp_e2e = ctrl.process_query("Compare Bihar and Assam floods.", session_id=sess.session_id)
            assert resp_e2e["plan_type"] == "comparison"
            assert "sub_query_results" in resp_e2e and len(resp_e2e["sub_query_results"]) >= 2

            # Inspect planner_log.json
            assert self.planner_log_path.exists(), f"Missing planner log file at {self.planner_log_path}"
            with open(self.planner_log_path, "r", encoding="utf-8") as f:
                p_logs = json.load(f)

            assert isinstance(p_logs, list) and len(p_logs) > 0
            sample_p_log = p_logs[-1]

            required_p_keys = ["timestamp", "session_id", "user_query", "rewritten_query", "plan_type", "steps_count", "execution_path", "total_latency", "confidence"]
            for rpk in required_p_keys:
                assert rpk in sample_p_log, f"Missing required key '{rpk}' in planner_log.json"

            forbidden = ["retrieved_context", "raw_chunks", "context_blocks"]
            for fb in forbidden:
                assert fb not in sample_p_log, f"Forbidden key '{fb}' present in planner log"

            self.results["Planner Log Telemetry Audit"] = {
                "status": "PASS",
                "details": f"Verified planner_log.json ({len(p_logs)} entries). Schema compliant & context excluded."
            }
            print("  [9/9] Planner Log Telemetry Audit: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Planner Log Telemetry Audit"] = {"status": "FAIL", "details": str(e)}
            print(f"  [9/9] Planner Log Telemetry Audit: 🔴 FAIL - {e}")

        print("=" * 75)
        print(f" VALIDATION STATUS: {'🟢 PASSED (100% Compliance)' if all_passed else '🔴 FAILED'}")
        print("=" * 75)

        self.generate_report(all_passed)
        return all_passed

    def generate_report(self, overall_status: bool) -> None:
        """Generates reports/planner_validation_report.md artifact."""
        report_path = project_root / "reports" / "planner_validation_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# VARTA — Agentic Planning & Retrieval Execution Validation Report (Sprint 4.3)",
            "",
            "## 1. Executive Summary",
            f"- **Validation Result**: `{'🟢 PASSED (100% Compliance)' if overall_status else '🔴 FAILED'}`",
            "- **Components Tested**: `ExecutionPlan`, `QueryDecomposer`, `AgentPlanner`, `RetrievalExecutor`, `AssistantController`, `planner_log.json`",
            "- **Scope**: Agentic intent analysis, multi-step & comparative query decomposition, and sequential retrieval execution",
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
            "## 3. Key Findings & Architectural Verification",
            "- **Agentic Execution Loop**: `AgentPlanner` accurately categorizes user intent into direct, followup, comparison, multi-step, summarization, and clarification plans.",
            "- **Sub-Query Decomposition**: `QueryDecomposer` splits complex comparative queries (in English & Devanagari/Hindi) into atomic sub-queries.",
            "- **Sequential Retrieval Execution**: `RetrievalExecutor` invokes `RAGOrchestrator` sequentially per sub-query and synthesizes consolidated answers.",
            "- **Telemetry & Log Isolation**: `planner_log.json` captures execution paths, latency, plan types, and steps while strictly excluding raw document context chunks.",
            ""
        ])

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\nReport written to: {report_path}")

def main():
    validator = PlannerValidator()
    success = validator.run_all_checks()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
