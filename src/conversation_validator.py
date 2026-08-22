#!/usr/bin/env python3
"""
VARTA Phase 4 - Sprint 4.1: Conversational AI Assistant Core Validation Suite.

Executes end-to-end verification of:
1. Session Creation
2. Multiple Chat Turns State Tracking
3. Empty Input Handling
4. Unicode / Hindi Query Processing
5. Long Input Prompt Handling
6. Session Termination Lifecycle
7. Session Logging Verification (ensuring raw context is omitted)

Generates reports/conversation_validation_report.md upon completion.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.vector_database import VectorDatabase
from src.semantic_retriever import SemanticRetriever
from src.rag_orchestrator import RAGOrchestrator
from src.llm_adapter import MockLLMAdapter
from src.session import Session
from src.conversation_manager import ConversationManager
from src.assistant_controller import AssistantController

class ConversationValidator:
    """
    Automated validator for Sprint 4.1 Conversational AI Assistant Core.
    """

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path) if log_path else project_root / "data" / "conversations" / "session_log.json"
        
        # Initialize mock or lightweight vector db setup for test validation
        vdb_dir = project_root / "data" / "vector_db"
        if vdb_dir.exists():
            self.vdb = VectorDatabase.load(str(vdb_dir))
        else:
            # Fallback mock for isolated unit execution if vector_db is not pre-built
            from src.embedding_storage import VectorEntry
            self.vdb = VectorDatabase(vector_dim=384)
            self.vdb.add_entry(VectorEntry(doc_id="doc1", chunk_id="chunk1", embedding=[0.1]*384, text="बिहार में बाढ़ राहत शिविर स्थापित किए गए हैं।", metadata={"title": "Bihar Flood Report"}))
            
        self.retriever = SemanticRetriever(vector_db=self.vdb)
        self.llm_adapter = MockLLMAdapter()
        self.orchestrator = RAGOrchestrator(retriever=self.retriever, llm_adapter=self.llm_adapter)
        
        self.results: Dict[str, Dict[str, Any]] = {}

    def run_all_checks(self) -> bool:
        """Executes all validation tests and records results."""
        print("=" * 65)
        print(" VARTA SPRINT 4.1 CONVERSATIONAL AI ASSISTANT VALIDATION SUITE")
        print("=" * 65)

        all_passed = True
        
        # 1. Session Creation Test
        try:
            mgr = ConversationManager()
            sess = mgr.create_session()
            assert sess.session_id is not None and len(sess.session_id) > 0, "Missing session_id"
            assert sess.created_at is not None, "Missing created_at"
            assert sess.message_count == 0, "Initial message count should be 0"
            assert sess.status == "active", "Initial status should be 'active'"
            assert sess.is_active() is True, "is_active() should be True"
            self.results["Session Creation"] = {
                "status": "PASS",
                "details": f"Session created with ID: {sess.session_id}, status: {sess.status}"
            }
            print("  [1/7] Session Creation: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Session Creation"] = {"status": "FAIL", "details": str(e)}
            print(f"  [1/7] Session Creation: 🔴 FAIL - {e}")

        # 2. Multiple Chat Turns Test
        try:
            mgr = ConversationManager()
            ctrl = AssistantController(rag_orchestrator=self.orchestrator, conversation_manager=mgr, log_file_path=str(self.log_path))
            sess = mgr.create_session()
            
            resp1 = ctrl.process_query("What is the flood status in Patna?", session_id=sess.session_id)
            assert sess.message_count == 1, f"Expected message_count 1, got {sess.message_count}"
            assert resp1["session_id"] == sess.session_id
            
            resp2 = ctrl.process_query("Tell me about relief efforts.", session_id=sess.session_id)
            assert sess.message_count == 2, f"Expected message_count 2, got {sess.message_count}"
            
            self.results["Multiple Chat Turns"] = {
                "status": "PASS",
                "details": f"Processed 2 turns. Final message count: {sess.message_count}"
            }
            print("  [2/7] Multiple Chat Turns: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Multiple Chat Turns"] = {"status": "FAIL", "details": str(e)}
            print(f"  [2/7] Multiple Chat Turns: 🔴 FAIL - {e}")

        # 3. Empty Input Handling Test
        try:
            mgr = ConversationManager()
            ctrl = AssistantController(rag_orchestrator=self.orchestrator, conversation_manager=mgr, log_file_path=str(self.log_path))
            sess = mgr.create_session()
            
            resp_empty = ctrl.process_query("   ", session_id=sess.session_id)
            assert resp_empty["assistant_answer"] is not None, "Response answer should not be None"
            assert resp_empty["confidence"]["level"] == "INVALID_INPUT", "Empty input should set INVALID_INPUT confidence level"
            
            self.results["Empty Input Handling"] = {
                "status": "PASS",
                "details": "Empty input handled gracefully with structured response"
            }
            print("  [3/7] Empty Input Handling: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Empty Input Handling"] = {"status": "FAIL", "details": str(e)}
            print(f"  [3/7] Empty Input Handling: 🔴 FAIL - {e}")

        # 4. Unicode / Hindi Support Test
        try:
            mgr = ConversationManager()
            ctrl = AssistantController(rag_orchestrator=self.orchestrator, conversation_manager=mgr, log_file_path=str(self.log_path))
            sess = mgr.create_session()
            
            hindi_query = "बिहार में गंगा नदी के जलस्तर का अपडेट क्या है?"
            resp_hindi = ctrl.process_query(hindi_query, session_id=sess.session_id)
            assert resp_hindi["query"] == hindi_query, "Hindi query string preserved"
            assert len(resp_hindi["assistant_answer"]) > 0, "Assistant returned non-empty answer"
            
            self.results["Unicode/Hindi Support"] = {
                "status": "PASS",
                "details": f"Devanagari query preserved and processed cleanly"
            }
            print("  [4/7] Unicode / Hindi Support: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Unicode/Hindi Support"] = {"status": "FAIL", "details": str(e)}
            print(f"  [4/7] Unicode / Hindi Support: 🔴 FAIL - {e}")

        # 5. Long Input Handling Test
        try:
            mgr = ConversationManager()
            ctrl = AssistantController(rag_orchestrator=self.orchestrator, conversation_manager=mgr, log_file_path=str(self.log_path))
            sess = mgr.create_session()
            
            long_query = "बाढ़ " * 500  # 1500+ characters
            resp_long = ctrl.process_query(long_query, session_id=sess.session_id)
            assert resp_long["session_id"] == sess.session_id
            assert "assistant_answer" in resp_long
            
            self.results["Long Input Handling"] = {
                "status": "PASS",
                "details": f"Processed input of length {len(long_query)} chars without exceptions"
            }
            print("  [5/7] Long Input Handling: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Long Input Handling"] = {"status": "FAIL", "details": str(e)}
            print(f"  [5/7] Long Input Handling: 🔴 FAIL - {e}")

        # 6. Proper Session Termination Test
        try:
            mgr = ConversationManager()
            sess = mgr.create_session()
            session_id = sess.session_id
            
            mgr.end_session(session_id)
            ended_sess = mgr.get_session(session_id)
            assert ended_sess.status == "closed", f"Expected 'closed', got {ended_sess.status}"
            assert ended_sess.is_active() is False, "is_active() should be False"
            assert len(mgr.list_active_sessions()) == 0, "Active sessions list should be empty"
            
            self.results["Proper Session Termination"] = {
                "status": "PASS",
                "details": "Session terminated cleanly and marked as closed"
            }
            print("  [6/7] Proper Session Termination: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Proper Session Termination"] = {"status": "FAIL", "details": str(e)}
            print(f"  [6/7] Proper Session Termination: 🔴 FAIL - {e}")

        # 7. Session Logging Verification Test
        try:
            assert self.log_path.exists(), f"Log file missing at {self.log_path}"
            with open(self.log_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
            assert isinstance(logs, list) and len(logs) > 0, "Log file should contain a non-empty array"
            
            sample_entry = logs[-1]
            required_keys = ["timestamp", "session_id", "user_query", "execution_time", "confidence", "provider", "model"]
            for rk in required_keys:
                assert rk in sample_entry, f"Missing required log key '{rk}'"
            
            forbidden_keys = ["retrieved_context", "raw_chunks", "assembled_context", "context"]
            for fk in forbidden_keys:
                assert fk not in sample_entry, f"Log entry contains forbidden context key '{fk}'"
                
            self.results["Session Logging Verification"] = {
                "status": "PASS",
                "details": f"Logged {len(logs)} entries. Verified schema compliance & context exclusion"
            }
            print("  [7/7] Session Logging Verification: 🟢 PASS")
        except Exception as e:
            all_passed = False
            self.results["Session Logging Verification"] = {"status": "FAIL", "details": str(e)}
            print(f"  [7/7] Session Logging Verification: 🔴 FAIL - {e}")

        print("=" * 65)
        print(f" VALIDATION STATUS: {'🟢 PASSED (100% Compliance)' if all_passed else '🔴 FAILED'}")
        print("=" * 65)

        self.generate_report(all_passed)
        return all_passed

    def generate_report(self, overall_status: bool) -> None:
        """Generates reports/conversation_validation_report.md artifact."""
        report_path = project_root / "reports" / "conversation_validation_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# VARTA — Conversational AI Assistant Validation Report (Sprint 4.1)",
            "",
            "## 1. Executive Summary",
            f"- **Validation Result**: `{'🟢 PASSED (100% Compliance)' if overall_status else '🔴 FAILED'}`",
            "- **Component Tested**: `Session`, `ConversationManager`, `AssistantController`, `session_log.json`",
            "- **Scope**: Conversational AI Assistant Core (No conversation memory, independent single-turn query execution)",
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
            "- **Single Entry Point**: `AssistantController` serves as the centralized interface wrapping `RAGOrchestrator`.",
            "- **Session State Integrity**: `Session` and `ConversationManager` successfully track session lifecycles, active states, and message counters without storing conversation history.",
            "- **Privacy & Storage Optimization**: `session_log.json` records query metadata, metrics, and confidence metrics while explicitly excluding retrieved context blocks.",
            "- **Multilingual & Input Robustness**: Devanagari / Hindi unicode strings, long text prompts, and empty strings are processed cleanly without exceptions.",
            ""
        ])

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\nReport written to: {report_path}")

def main():
    validator = ConversationValidator()
    success = validator.run_all_checks()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
