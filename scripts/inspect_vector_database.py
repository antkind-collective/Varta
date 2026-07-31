#!/usr/bin/env python3
"""
VARTA Phase 2 - Sprint 2.2: Vector Database Inspector CLI Script.
Inspects persistent vector database statistics, FAISS index state,
SQLite metadata store, and sample chunk payloads.
"""

import os
import sys
import json
import argparse
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.vector_database import VectorDatabase

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="VARTA Vector Database Inspector")
    parser.add_argument("--db-dir", type=str, default=str(project_root / "data" / "vector_db"))
    args = parser.parse_args()

    print("=" * 65)
    print(" VARTA - SPRINT 2.2 VECTOR DATABASE INSPECTOR")
    print("=" * 65)

    if not os.path.exists(args.db_dir):
        raise FileNotFoundError(f"Vector Database directory not found at: {args.db_dir}")

    vdb = VectorDatabase.load(args.db_dir)
    stats = vdb.get_index_statistics()

    print(f"\n[1/2] Vector Database Overview:")
    print(f"      Vector Engine        : {stats['manifest'].get('vector_engine', 'FAISS')}")
    print(f"      Metadata Engine      : {stats['manifest'].get('metadata_engine', 'SQLite')}")
    print(f"      Total Vectors        : {stats['total_vectors_indexed']:,}")
    print(f"      Metadata Records     : {stats['metadata_records_count']:,}")
    print(f"      Vector Dimension     : {stats['vector_dimension']} dims")
    print(f"      Fast Reload Duration : {stats['reload_duration_sec']} seconds")

    print(f"\n[2/2] Sample Indexed Record (Vector ID 0):")
    sample = vdb.metadata_store.get_metadata_by_vector_ids([0])
    if sample:
        rec = sample[0]
        print(f"      Chunk ID      : {rec.get('chunk_id')}")
        print(f"      Parent Doc ID : {rec.get('parent_doc_id')}")
        print(f"      Title         : {rec.get('title')}")
        print(f"      Content Snippet: {rec.get('content')[:120]}...")
        print(f"      Metadata      : {json.dumps(rec.get('metadata'), ensure_ascii=False)}")

    print("\n" + "=" * 65)
    print(" INSPECTION COMPLETE")
    print("=" * 65)

if __name__ == "__main__":
    main()
