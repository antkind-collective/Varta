#!/usr/bin/env python3
"""
VARTA Phase 2 - Sprint 2.3: Semantic Retrieval CLI Runner.

Executes multilingual semantic retrieval queries against the persistent VectorDatabase.
Formats structured JSON output containing rank, Cosine Similarity score, chunk_id, and metadata.
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

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="VARTA Semantic Retrieval CLI Engine")
    parser.add_argument("--query", type=str, default="गोरखपुर में बाढ़ की क्या स्थिति है?", help="Search query string")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K results count")
    parser.add_argument("--source-type", type=str, default=None, help="Optional source_type filter")
    parser.add_argument("--db-dir", type=str, default=str(project_root / "data" / "vector_db"))
    args = parser.parse_args()

    print("=" * 65)
    print(" VARTA - SPRINT 2.3 SEMANTIC RETRIEVAL ENGINE")
    print("=" * 65)

    if not os.path.exists(args.db_dir):
        raise FileNotFoundError(f"Vector Database directory not found at: {args.db_dir}")

    # Load VectorDatabase Facade
    vdb = VectorDatabase.load(args.db_dir)
    retriever = SemanticRetriever(vector_db=vdb)

    metadata_filters = None
    if args.source_type:
        metadata_filters = {"source_type": args.source_type}

    # Execute Retrieval
    response = retriever.retrieve(query=args.query, top_k=args.top_k, metadata_filters=metadata_filters)

    print(f"\n[QUERY]: '{response['query']}'")
    print(f"[PREPROCESSED]: '{response['processed_query']}'")
    print(f"[EXECUTION TIME]: {response['execution_time_ms']} ms")
    print(f"[RESULTS RETURNED]: {response['total_results_returned']} chunks (Top-{args.top_k})\n")

    print("=" * 65)
    print(" STRUCTURED RETRIEVAL RESULTS:")
    print("=" * 65)
    for res in response["results"]:
        print(f"\nRANK {res['rank']} | Score: {res['similarity_score']} (Cosine Similarity)")
        print(f"  Chunk ID  : {res['chunk_id']}")
        print(f"  Title     : {res['title']}")
        print(f"  Snippet   : {res['content'][:140]}...")
        print(f"  Metadata  : {json.dumps(res['metadata'], ensure_ascii=False)}")

    print("\n" + "=" * 65)
    print(" RETRIEVAL COMPLETE")
    print("=" * 65)

if __name__ == "__main__":
    main()
