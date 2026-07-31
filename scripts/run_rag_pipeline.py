#!/usr/bin/env python3
"""
VARTA Phase 2 - Sprint 2.4: RAG Orchestration CLI Runner.

Executes end-to-end RAG pipeline:
Query -> Retrieval -> Context Assembly -> Token Budgeting -> Prompt Building -> LLM Adapter.
Prints structured JSON response with Confidence block, Prompt details, Answer, and Citations.
"""

import os
import sys
import json
import argparse
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.vector_database import VectorDatabase
from src.semantic_retriever import SemanticRetriever
from src.rag_orchestrator import RAGOrchestrator
from src.llm_adapter import get_llm_adapter

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="VARTA RAG Orchestrator CLI Engine")
    parser.add_argument("--query", type=str, default="गोरखपुर में राप्ती नदी का जलस्तर तटबंध की क्या स्थिति है?", help="User query string")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K retrieval count")
    parser.add_argument("--max-tokens", type=int, default=2048, help="Maximum context token budget")
    parser.add_argument("--db-dir", type=str, default=str(project_root / "data" / "vector_db"))
    args = parser.parse_args()

    print("=" * 65)
    print(" VARTA - SPRINT 2.4 RAG ORCHESTRATION PIPELINE ENGINE")
    print("=" * 65)

    if not os.path.exists(args.db_dir):
        raise FileNotFoundError(f"Vector Database directory not found at: {args.db_dir}")

    # Initialize Pipeline Components & Dynamic LLM Adapter
    vdb = VectorDatabase.load(args.db_dir)
    retriever = SemanticRetriever(vector_db=vdb)
    llm_adapter = get_llm_adapter()

    orchestrator = RAGOrchestrator(
        retriever=retriever,
        llm_adapter=llm_adapter,
        max_context_tokens=args.max_tokens
    )

    # Execute RAG Pipeline
    response = orchestrator.run_pipeline(query=args.query, top_k=args.top_k)

    print(f"\n[QUERY]: '{response['query']}'")
    print(f"[LLM INVOKED]: {response['llm_invoked']}")
    print(f"[LLM PROVIDER]: {response['llm']['provider']} ({response['llm']['model_name']})")
    print(f"[CONFIDENCE BLOCK]: Level={response['confidence']['level']} | Score={response['confidence']['score']} | Coverage={response['confidence']['context_coverage_pct']}%")
    print(f"[CONTEXT SUMMARY]: Assembled {response['context']['assembled_blocks_count']} blocks ({response['context']['total_context_tokens']}/{response['context']['max_token_budget']} tokens, {response['context']['token_utilization_pct']}% utilization)")
    print(f"[EXECUTION TIME]: {response['execution_time_ms']} ms\n")

    print("=" * 65)
    print(" GENERATED GROUNDED ANSWER:")
    print("=" * 65)
    print(response["answer"])

    print("\n" + "=" * 65)
    print(" PRESERVED CITATIONS:")
    print("=" * 65)
    for cit in response["citations"]:
        print(f"  {cit['citation_id']} -> Score: {cit['similarity_score']} | Title: '{cit['title']}'")

    print("\n" + "=" * 65)
    print(" RAG PIPELINE EXECUTION COMPLETE")
    print("=" * 65)

if __name__ == "__main__":
    main()
