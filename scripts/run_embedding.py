#!/usr/bin/env python3
"""
VARTA Phase 2 - Sprint 2.1: Embedding Generation CLI Runner.
Reads data/embeddings/chunks.json, uses provider-agnostic embedding interface,
generates dense vector matrix stored in data/embeddings/embeddings.npy,
and produces data/embeddings/embedding_statistics.json and reports/embedding_pipeline_report.md.
"""

import os
import sys
import json
import argparse
import numpy as np
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.embedding_providers import get_embedding_provider
from src.embedding_generator import EmbeddingGenerator
from src.embedding_storage import EmbeddingStorage

def generate_pipeline_report(filepath: str, gen_stats: dict, npy_path: str, stats_path: str):
    lines = [
        "# VARTA — Embedding Pipeline Report (Sprint 2.1)",
        "",
        "## 1. Executive Summary",
        f"- **Embedding Model**: `{gen_stats['model_name']}`",
        f"- **Vector Dimension**: `{gen_stats['vector_dimension']} dims`",
        f"- **Total Vector Embeddings**: `{gen_stats['num_chunks']:,}`",
        f"- **Embedding Generation Time**: `{gen_stats['duration_sec']} seconds`",
        f"- **Throughput Rate**: `{gen_stats['throughput_chunks_per_sec']} chunks/sec`",
        f"- **Binary Vector Output**: `{npy_path}`",
        f"- **Corpus Statistics Output**: `{stats_path}`",
        "",
        "## 2. Technical Architecture Highlights",
        "1. **Provider-Agnostic Engine**: Supports swapping local SentenceTransformers models, cloud APIs, or fallback models via `config/embedding_config.json`.",
        "2. **FAISS & ChromaDB Optimized Matrix Storage**: Dense embeddings stored as a 2D float32 C-contiguous NumPy binary matrix (`embeddings.npy`) for microsecond zero-copy loading.",
        "3. **Contextual Title Header Integration**: Embeddings generated on title-injected payload text (`\"Title: {title}\\nContent: {content}\"`).",
        "4. **Corpus-Level Statistics**: Metadata manifest exported to `embedding_statistics.json`."
    ]
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def main():
    parser = argparse.ArgumentParser(description="VARTA Embedding Generation Runner")
    parser.add_argument("--chunks-json", type=str, default=str(project_root / "data" / "embeddings" / "chunks.json"))
    parser.add_argument("--docs-json", type=str, default=str(project_root / "data" / "standardized" / "standardized_documents.json"))
    parser.add_argument("--config-path", type=str, default=str(project_root / "config" / "embedding_config.json"))
    parser.add_argument("--output-dir", type=str, default=str(project_root / "data" / "embeddings"))
    parser.add_argument("--reports-dir", type=str, default=str(project_root / "reports"))
    args = parser.parse_args()

    print("=" * 65)
    print(" VARTA - SPRINT 2.1 EMBEDDING GENERATION RUNNER")
    print("=" * 65)

    if not os.path.exists(args.chunks_json):
        raise FileNotFoundError(f"Chunks JSON file not found at: {args.chunks_json}")

    print(f"\n[1/4] Loading Chunks Dataset: {args.chunks_json}")
    with open(args.chunks_json, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"      Loaded {len(chunks):,} chunks")

    doc_count = 33975
    if os.path.exists(args.docs_json):
        with open(args.docs_json, "r", encoding="utf-8") as f:
            docs = json.load(f)
            doc_count = len(docs)

    # Load Configuration
    config = {}
    if os.path.exists(args.config_path):
        with open(args.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    emb_cfg = config.get("embedding", {})
    batch_size = emb_cfg.get("batch_size", 64)

    # 2. Instantiate Provider & Engine
    print("\n[2/4] Initializing Embedding Model Provider...")
    provider = get_embedding_provider(config)
    print(f"      Active Model Provider : {provider.get_model_name()}")
    print(f"      Vector Dimension     : {provider.get_dimension()} dims")

    # 3. Generate Embeddings
    print(f"\n[3/4] Generating Vectors for {len(chunks):,} Chunks...")
    generator = EmbeddingGenerator(provider=provider, batch_size=batch_size)
    embeddings_matrix, gen_stats = generator.generate_embeddings(chunks)

    # 4. Storage Exports
    print(f"\n[4/4] Exporting Vector Matrix and Statistics to: {args.output_dir}")
    storage = EmbeddingStorage(args.output_dir)
    npy_path = storage.save_embeddings_npy(embeddings_matrix, "embeddings.npy")
    stats_path = storage.save_embedding_statistics(
        gen_stats=gen_stats,
        doc_count=doc_count,
        chunks_json_path=args.chunks_json,
        embeddings_npy_path=npy_path,
        filename="embedding_statistics.json"
    )

    npy_mb = round(os.path.getsize(npy_path) / (1024 * 1024), 2)
    print(f"      [OK] Saved Dense Vector Matrix : {npy_path} ({npy_mb} MB)")
    print(f"      [OK] Saved Corpus Statistics    : {stats_path}")

    # Generate Report
    os.makedirs(args.reports_dir, exist_ok=True)
    report_path = os.path.join(args.reports_dir, "embedding_pipeline_report.md")
    generate_pipeline_report(report_path, gen_stats, npy_path, stats_path)

    print("\n" + "=" * 65)
    print(" EMBEDDING GENERATION COMPLETE - DELIVERABLES GENERATED:")
    print("=" * 65)
    print(f"  [OK] Vector Matrix (.npy): {npy_path}")
    print(f"  [OK] Statistics Artifact : {stats_path}")
    print(f"  [OK] Pipeline Report     : {report_path}")
    print("=" * 65)

if __name__ == "__main__":
    main()
