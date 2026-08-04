#!/usr/bin/env python3
"""
VARTA Phase 4 - Sprint 4.1: Interactive CLI Conversational AI Assistant.

Executes continuous multi-turn interactive session using AssistantController,
ConversationManager, and existing RAGOrchestrator pipeline.
Exits cleanly when user types 'exit' or 'quit'.
"""

import os
import sys
import argparse
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.vector_database import VectorDatabase
from src.semantic_retriever import SemanticRetriever
from src.rag_orchestrator import RAGOrchestrator
from src.llm_adapter import get_llm_adapter
from src.conversation_manager import ConversationManager
from src.assistant_controller import AssistantController

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="VARTA Conversational AI Assistant CLI")
    parser.add_argument("--db-dir", type=str, default=str(project_root / "data" / "vector_db"), help="Path to Vector DB directory")
    parser.add_argument("--max-tokens", type=int, default=2048, help="Context token budget")
    args = parser.parse_args()

    if not os.path.exists(args.db_dir):
        raise FileNotFoundError(f"Vector Database directory not found at: {args.db_dir}")

    # Initialize RAG Pipeline components
    vdb = VectorDatabase.load(args.db_dir)
    retriever = SemanticRetriever(vector_db=vdb)
    llm_adapter = get_llm_adapter()
    orchestrator = RAGOrchestrator(
        retriever=retriever,
        llm_adapter=llm_adapter,
        max_context_tokens=args.max_tokens
    )

    # Initialize Conversational Layer
    conversation_manager = ConversationManager()
    assistant_controller = AssistantController(
        rag_orchestrator=orchestrator,
        conversation_manager=conversation_manager
    )

    # Start a new session
    session = conversation_manager.create_session()

    print("=================================")
    print("VARTA AI Assistant")
    print("=================================")
    print(f"\nSession: {session.session_id}\n")

    try:
        while True:
            try:
                user_input = input("You:\n").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n")
                break

            if user_input.lower() in ["exit", "quit"]:
                break

            if not user_input:
                print("\nAssistant:\nPlease enter a valid question or query.\n")
                continue

            response = assistant_controller.process_query(user_input, session_id=session.session_id)

            if response.get("memory_used") or (response.get("rewritten_query") and response["rewritten_query"].strip() != user_input.strip()):
                print(f"\nResolved Query:\n{response['rewritten_query']}\n")

            if response.get("plan_summary") and response.get("plan_type") != "direct":
                print(f"{response['plan_summary']}\n")

            if response.get("tool_selected"):
                print(f"[Tool Invoked]: {response['tool_selected']}")

            print(f"Assistant:\n{response['assistant_answer']}\n")

            # Transparency Metadata Block
            conf = response.get("confidence", {})
            llm_info = response.get("llm", {})
            exec_time = response.get("execution_time_ms", 0)

            print(f"[CONFIDENCE]: Level={conf.get('level', 'N/A')} | Score={conf.get('score', 0.0)}")
            print(f"[LLM PROVIDER]: {llm_info.get('provider', 'N/A')} ({llm_info.get('model', 'N/A')})")
            print(f"[EXECUTION TIME]: {exec_time} ms\n")

            if response.get("citations"):
                print("Citations:")
                for cit in response["citations"]:
                    print(f"  - [{cit['citation_id']}] {cit['title']} (Score: {cit['similarity_score']})")
                print()

    finally:
        conversation_manager.end_session(session.session_id)
        print("Session closed.")

if __name__ == "__main__":
    main()
