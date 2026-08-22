#!/usr/bin/env python3
"""
Diagnostic Script for Live Dataset Upload & 5-Stage Ingestion Pipeline.
Measures exact time, record counts, and bottleneck per stage without modifying core logic.
"""

import sys
import time
import json
import logging
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.dataset_loader import DatasetLoader
from src.data_cleaner import DataCleaner
from src.text_normalizer import TextNormalizer
from src.metadata_processor import MetadataProcessor
from src.duplicate_handler import DuplicateHandler
from src.document_builder import DocumentBuilder
from src.document_validator import DocumentValidator
from src.chunk_builder import ChunkBuilder
from src.embedding_providers import get_embedding_provider
from src.embedding_generator import EmbeddingGenerator

def diagnose_upload():
    print("=" * 80)
    print(" VARTA DATASET UPLOAD LIVE DIAGNOSIS")
    print("=" * 80)

    upload_file = project_root / "data" / "uploads" / "upload_1786774890_Flood Regional News 25-26 - Sheet1.csv"
    if not upload_file.exists():
        print(f"[!] Upload file not found at: {upload_file}")
        # Search data/uploads for latest csv
        uploads = list((project_root / "data" / "uploads").glob("*.csv"))
        if not uploads:
            print("[!] No CSV files found in data/uploads")
            return
        upload_file = max(uploads, key=lambda p: p.stat().st_mtime)

    file_size_mb = upload_file.stat().st_size / (1024 * 1024)
    print(f"Target File: {upload_file.name}")
    print(f"File Size:   {file_size_mb:.2f} MB")

    # Load configs
    with open(project_root / "config" / "column_mapping.json", "r", encoding="utf-8") as f:
        col_cfg = json.load(f)
    with open(project_root / "config" / "embedding_config.json", "r", encoding="utf-8") as f:
        emb_cfg = json.load(f)

    # -------------------------------------------------------------
    # STAGE 1: Preprocessing
    # -------------------------------------------------------------
    print("\n--- STAGE 1: Preprocessing Diagnostics ---")
    t0 = time.time()
    loader = DatasetLoader(str(upload_file))
    df_raw, raw_meta = loader.load_dataset()
    t_load = time.time() - t0
    print(f"[1.1 Load]           {len(df_raw):,} rows, {len(df_raw.columns)} cols loaded in {t_load:.2f}s")
    print(f"       Columns:      {list(df_raw.columns)}")

    t0 = time.time()
    cleaner = DataCleaner(col_cfg)
    df_clean_cols, _ = cleaner.clean_structure_and_columns(df_raw)
    df_valid, _ = cleaner.filter_and_fill_identifiers(df_clean_cols)
    t_clean = time.time() - t0
    print(f"[1.2 Clean/Filter]   {len(df_valid):,} valid rows remaining in {t_clean:.2f}s")

    t0 = time.time()
    normalizer = TextNormalizer()
    df_text_norm = df_valid.copy()
    for col in col_cfg.get("core_payload_columns", ["title", "text_content"]):
        if col in df_text_norm.columns:
            norm_series, _ = normalizer.normalize_series(df_text_norm[col])
            df_text_norm[col] = norm_series
    t_norm = time.time() - t0
    print(f"[1.3 Text Normalize] Normalized in {t_norm:.2f}s")

    t0 = time.time()
    meta_processor = MetadataProcessor()
    df_meta_clean, _ = meta_processor.process_metadata(df_text_norm)
    t_meta = time.time() - t0
    print(f"[1.4 Metadata Proc]  Processed in {t_meta:.2f}s")

    t0 = time.time()
    dup_handler = DuplicateHandler(
        id_column=col_cfg.get("identifier_column", "post_id"),
        payload_columns=col_cfg.get("core_payload_columns", ["title", "text_content"])
    )
    df_processed, dedup_stats = dup_handler.deduplicate(df_meta_clean)
    t_dedup = time.time() - t0
    print(f"[1.5 Deduplication]  {len(df_processed):,} unique rows after dedup in {t_dedup:.2f}s")

    total_stage1 = t_load + t_clean + t_norm + t_meta + t_dedup
    print(f"==> STAGE 1 TOTAL:   {total_stage1:.2f}s (STATUS: {'DONE' if len(df_processed) > 0 else 'EMPTY'})")

    # -------------------------------------------------------------
    # STAGE 2: Document Standardization
    # -------------------------------------------------------------
    print("\n--- STAGE 2: Standardization Diagnostics ---")
    t0 = time.time()
    doc_builder = DocumentBuilder(schema_version="1.0.0")
    documents = []
    for idx, (_, row) in enumerate(df_processed.iterrows()):
        doc = doc_builder.build_document(row, doc_index=idx)
        documents.append(doc)

    validator = DocumentValidator()
    valid_docs = [d for d in documents if validator.validate_document(d)[0]]
    t_stage2 = time.time() - t0
    print(f"==> STAGE 2 TOTAL:   {len(valid_docs):,} valid documents standardized in {t_stage2:.2f}s")

    # -------------------------------------------------------------
    # STAGE 3: Semantic Chunking
    # -------------------------------------------------------------
    print("\n--- STAGE 3: Semantic Chunking Diagnostics ---")
    t0 = time.time()
    chunk_builder = ChunkBuilder(
        target_chunk_size=emb_cfg.get("chunk_size_chars", 1200),
        chunk_overlap=emb_cfg.get("chunk_overlap_chars", 200)
    )
    chunks, chunk_stats = chunk_builder.build_chunks_from_documents(valid_docs)
    t_stage3 = time.time() - t0
    print(f"==> STAGE 3 TOTAL:   {len(chunks):,} chunks generated from {len(valid_docs):,} docs in {t_stage3:.2f}s")

    # -------------------------------------------------------------
    # STAGE 4: Embedding Estimation & Test
    # -------------------------------------------------------------
    print("\n--- STAGE 4: Embedding Generation Diagnostics ---")
    emb_provider = get_embedding_provider(emb_cfg)
    print(f"      Embedding Model: {emb_provider.get_model_name()}")
    print(f"      Total Chunks to Embed: {len(chunks):,}")
    
    # Test small sample embedding to measure throughput
    sample_size = min(64, len(chunks))
    sample_chunks = chunks[:sample_size]
    t0 = time.time()
    emb_generator = EmbeddingGenerator(provider=emb_provider, batch_size=sample_size)
    sample_vecs, sample_stats = emb_generator.generate_embeddings(sample_chunks)
    t_sample = time.time() - t0
    rate = sample_size / t_sample if t_sample > 0 else 1.0
    est_total_time_sec = len(chunks) / rate if rate > 0 else 0
    print(f"      Sample ({sample_size} chunks) speed: {rate:.1f} chunks/sec")
    print(f"      ESTIMATED TOTAL EMBEDDING TIME: {est_total_time_sec:.1f}s ({est_total_time_sec/60:.2f} minutes)")

if __name__ == "__main__":
    diagnose_upload()
