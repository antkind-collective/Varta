#!/usr/bin/env python3
"""
VARTA Phase 2 - Sprint 2.1: Document Chunking CLI Runner.
Reads standardized documents (data/standardized/standardized_documents.json),
applies recursive character chunking with title preservation and overlap,
and exports data/embeddings/chunks.json and reports/chunking_strategy_report.md.
"""

import os
import sys
import json
import argparse
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.chunk_builder import ChunkBuilder

def generate_chunking_report(filepath: str, stats: dict):
    lines = [
        "# VARTA — Document Chunking Strategy Report (Sprint 2.1)",
        "",
        "## 1. Executive Summary",
        f"- **Input Corpus Documents**: `{stats['total_documents']:,}`",
        f"- **Generated Chunks**: `{stats['total_chunks']:,}`",
        f"- **Average Chunks per Document**: `{stats['avg_chunks_per_doc']}`",
        f"- **Target Chunk Size**: `{stats['target_chunk_size']} characters` (~250-300 words)",
        f"- **Chunk Overlap**: `{stats['chunk_overlap']} characters` (~40-50 words)",
        f"- **Output File**: `{stats['output_json_path']}`",
        "",
        "## 2. Chunking Strategy Specification",
        "1. **Hierarchical Recursive Splitting**: Text was split using separators `[\"\\n\\n\", \"\\n\", \"। \", \". \", \" \", \"\"]` to preserve natural paragraph and sentence boundaries.",
        "2. **Title Field Preservation**: Every chunk retains `title` as a standalone metadata attribute alongside `content`.",
        "3. **Embedding Context Injection**: Computed `embedding_text` (`\"Title: {title}\\nContent: {content}\"`) specifically for the embedding vector model.",
        "4. **Parent-Child Linkage**: Every chunk inherits parent metadata (`post_id`, `source_type`, `category_taxonomy`, `image_url`, `user_rating`) and references `parent_doc_id`."
    ]
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def main():
    parser = argparse.ArgumentParser(description="VARTA Document Chunking Runner")
    parser.add_argument("--input-json", type=str, default=str(project_root / "data" / "standardized" / "standardized_documents.json"))
    parser.add_argument("--config-path", type=str, default=str(project_root / "config" / "embedding_config.json"))
    parser.add_argument("--output-dir", type=str, default=str(project_root / "data" / "embeddings"))
    parser.add_argument("--reports-dir", type=str, default=str(project_root / "reports"))
    args = parser.parse_args()

    print("=" * 65)
    print(" VARTA - SPRINT 2.1 DOCUMENT CHUNKING RUNNER")
    print("=" * 65)

    if not os.path.exists(args.input_json):
        raise FileNotFoundError(f"Standardized documents not found at: {args.input_json}")

    print(f"\n[1/3] Loading Standardized Documents: {args.input_json}")
    with open(args.input_json, "r", encoding="utf-8") as f:
        documents = json.load(f)
    print(f"      Loaded {len(documents):,} standardized documents")

    # Load Config
    chunk_cfg = {}
    if os.path.exists(args.config_path):
        with open(args.config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            chunk_cfg = cfg.get("chunking", {})

    target_chunk_size = chunk_cfg.get("target_chunk_size", 1200)
    chunk_overlap = chunk_cfg.get("chunk_overlap", 200)
    separators = chunk_cfg.get("separators", ["\n\n", "\n", "। ", ". ", " ", ""])
    inject_title_header = chunk_cfg.get("inject_title_header", True)

    print(f"\n[2/3] Chunking Documents (Size: {target_chunk_size}, Overlap: {chunk_overlap})...")
    builder = ChunkBuilder(
        target_chunk_size=target_chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        inject_title_header=inject_title_header
    )

    all_chunks = []
    for doc in documents:
        chunks = builder.build_chunks_from_document(doc)
        all_chunks.extend(chunks)

    total_docs = len(documents)
    total_chunks = len(all_chunks)
    avg_chunks = round(total_chunks / total_docs, 2) if total_docs > 0 else 0.0

    print(f"      Generated {total_chunks:,} total chunks (Avg {avg_chunks} chunks/doc)")

    # 3. Save chunks.json
    print(f"\n[3/3] Exporting Chunks: {args.output_dir}")
    os.makedirs(args.output_dir, exist_ok=True)
    chunks_path = os.path.join(args.output_dir, "chunks.json")
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    # Generate Report
    stats_dict = {
        "total_documents": total_docs,
        "total_chunks": total_chunks,
        "avg_chunks_per_doc": avg_chunks,
        "target_chunk_size": target_chunk_size,
        "chunk_overlap": chunk_overlap,
        "output_json_path": chunks_path
    }
    os.makedirs(args.reports_dir, exist_ok=True)
    report_path = os.path.join(args.reports_dir, "chunking_strategy_report.md")
    generate_chunking_report(report_path, stats_dict)

    print("\n" + "=" * 65)
    print(" CHUNKING COMPLETE - DELIVERABLES GENERATED:")
    print("=" * 65)
    print(f"  [OK] Chunks JSON Output : {chunks_path}")
    print(f"  [OK] Chunking Report    : {report_path}")
    print("=" * 65)

if __name__ == "__main__":
    main()
