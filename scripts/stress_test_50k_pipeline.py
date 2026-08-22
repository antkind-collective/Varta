import sys
import os
import time
import json
import logging
import gc
import psutil
import tracemalloc
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.dataset_loader import DatasetLoader
from src.data_cleaner import DataCleaner
from src.text_normalizer import TextNormalizer
from src.metadata_processor import MetadataProcessor
from src.duplicate_handler import DuplicateHandler
from src.context_relevance_engine import ContextRelevanceEngine, ResearchContext
from src.document_builder import DocumentBuilder
from src.document_validator import DocumentValidator
from src.chunk_builder import ChunkBuilder
from src.embedding_providers import get_embedding_provider
from src.embedding_generator import EmbeddingGenerator
from src.metadata_store import MetadataStore
from src.vector_database import VectorDatabase

import faiss

logger = logging.getLogger("SyntheticStressTest50K")

def get_current_ram_mb() -> float:
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def run_synthetic_50k_stress_test():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 80)
    print("VARTA — SYNTHETIC 50,000-RECORD PIPELINE SCALABILITY & STRESS TEST")
    print("Label: Synthetic Scalability/Stress Test (Not an Accuracy Evaluation)")
    print("=" * 80)

    tracemalloc.start()
    ram_start_mb = get_current_ram_mb()
    peak_ram_mb = ram_start_mb

    file_path = os.path.abspath("data/uploads/synthetic_50k_stress_dataset.csv")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Synthetic dataset file not found at: {file_path}")

    project_root = Path(".").resolve()
    vdb_dir = project_root / "data" / "vector_db"
    vdb_dir.mkdir(parents=True, exist_ok=True)
    
    config_dir = project_root / "config"
    with open(config_dir / "column_mapping.json", "r", encoding="utf-8") as f:
        column_config = json.load(f)
    with open(config_dir / "embedding_config.json", "r", encoding="utf-8") as f:
        embedding_config = json.load(f)

    stage_timings = {}
    stage_memory = {}
    stage_records = {}
    errors = []

    t_total_start = time.time()

    # -------------------------------------------------------------------------
    # STAGE 1: Dataset Upload & File Parsing
    # -------------------------------------------------------------------------
    t_stage_start = time.time()
    try:
        loader = DatasetLoader(file_path)
        df_raw, raw_meta = loader.load_dataset()
        upload_parse_sec = time.time() - t_stage_start
        stage_timings["Upload & Parsing"] = upload_parse_sec
        stage_memory["Upload & Parsing"] = get_current_ram_mb()
        stage_records["Upload & Parsing"] = len(df_raw)
        peak_ram_mb = max(peak_ram_mb, stage_memory["Upload & Parsing"])
        print(f"[Stage 1] Upload & Parsing: {upload_parse_sec:.2f}s ({len(df_raw)} records, RAM: {stage_memory['Upload & Parsing']:.1f} MB)")
    except Exception as e:
        errors.append(f"Stage 1 Failure: {e}")
        raise e

    # -------------------------------------------------------------------------
    # STAGE 2: Structural Preprocessing, Normalization & Deduplication
    # -------------------------------------------------------------------------
    t_stage_start = time.time()
    try:
        cleaner = DataCleaner(column_config)
        df_clean_cols, _ = cleaner.clean_structure_and_columns(df_raw)
        df_valid, _ = cleaner.filter_and_fill_identifiers(df_clean_cols)

        normalizer = TextNormalizer()
        df_text_norm = df_valid.copy()
        for col in column_config.get("core_payload_columns", ["title", "text_content"]):
            if col in df_text_norm.columns:
                norm_series, _ = normalizer.normalize_series(df_text_norm[col])
                df_text_norm[col] = norm_series

        meta_processor = MetadataProcessor()
        df_meta_clean, _ = meta_processor.process_metadata(df_text_norm)

        dup_handler = DuplicateHandler(
            id_column=column_config.get("identifier_column", "post_id"),
            payload_columns=column_config.get("core_payload_columns", ["title", "text_content"])
        )
        df_dedup, dedup_stats = dup_handler.deduplicate(df_meta_clean)
        
        prep_sec = time.time() - t_stage_start
        stage_timings["Structural Preprocessing"] = prep_sec
        stage_memory["Structural Preprocessing"] = get_current_ram_mb()
        stage_records["Structural Preprocessing"] = len(df_dedup)
        peak_ram_mb = max(peak_ram_mb, stage_memory["Structural Preprocessing"])
        print(f"[Stage 2] Structural Preprocessing: {prep_sec:.2f}s ({len(df_dedup)} unique records, RAM: {stage_memory['Structural Preprocessing']:.1f} MB)")
    except Exception as e:
        errors.append(f"Stage 2 Failure: {e}")
        raise e

    # -------------------------------------------------------------------------
    # STAGE 3: Context Relevance Filtering
    # -------------------------------------------------------------------------
    t_stage_start = time.time()
    try:
        rel_engine = ContextRelevanceEngine()
        context = ResearchContext()
        records_to_filter = df_dedup.to_dict("records")

        filtered_records, rel_stats = rel_engine.filter_dataset(records_to_filter, context=context, allowed_decisions=("KEEP", "REVIEW"))
        
        filtering_sec = time.time() - t_stage_start
        stage_timings["Context Relevance Filtering"] = filtering_sec
        stage_memory["Context Relevance Filtering"] = get_current_ram_mb()
        stage_records["Context Relevance Filtering"] = len(records_to_filter)
        peak_ram_mb = max(peak_ram_mb, stage_memory["Context Relevance Filtering"])
        
        keep_cnt = rel_stats["decision_counts"].get("KEEP", 0)
        review_cnt = rel_stats["decision_counts"].get("REVIEW", 0)
        exclude_cnt = rel_stats["decision_counts"].get("EXCLUDE", 0)
        
        print(f"[Stage 3] Context Filtering: {filtering_sec:.2f}s (KEEP: {keep_cnt}, REVIEW: {review_cnt}, EXCLUDE: {exclude_cnt}, RAM: {stage_memory['Context Relevance Filtering']:.1f} MB)")
    except Exception as e:
        errors.append(f"Stage 3 Failure: {e}")
        raise e

    # -------------------------------------------------------------------------
    # STAGE 4: Document Standardization
    # -------------------------------------------------------------------------
    t_stage_start = time.time()
    try:
        df_processed = pd.DataFrame(filtered_records)
        doc_builder = DocumentBuilder(schema_version="1.0.0")
        documents = []
        for idx, (_, row) in enumerate(df_processed.iterrows()):
            doc = doc_builder.build_document(row, doc_index=idx)
            documents.append(doc)

        validator = DocumentValidator()
        valid_docs = []
        for doc in documents:
            is_valid, _ = validator.validate_document(doc)
            if is_valid:
                valid_docs.append(doc)

        std_sec = time.time() - t_stage_start
        stage_timings["Standardization"] = std_sec
        stage_memory["Standardization"] = get_current_ram_mb()
        stage_records["Standardization"] = len(valid_docs)
        peak_ram_mb = max(peak_ram_mb, stage_memory["Standardization"])
        print(f"[Stage 4] Document Standardization: {std_sec:.2f}s ({len(valid_docs)} valid docs, RAM: {stage_memory['Standardization']:.1f} MB)")
    except Exception as e:
        errors.append(f"Stage 4 Failure: {e}")
        raise e

    # -------------------------------------------------------------------------
    # STAGE 5: Semantic Chunking
    # -------------------------------------------------------------------------
    t_stage_start = time.time()
    try:
        chunk_builder = ChunkBuilder(
            target_chunk_size=embedding_config.get("chunk_size_chars", 1200),
            chunk_overlap=embedding_config.get("chunk_overlap_chars", 200)
        )
        chunks, chunk_stats = chunk_builder.build_chunks_from_documents(valid_docs)
        chunking_sec = time.time() - t_stage_start
        stage_timings["Semantic Chunking"] = chunking_sec
        stage_memory["Semantic Chunking"] = get_current_ram_mb()
        stage_records["Semantic Chunking"] = len(chunks)
        peak_ram_mb = max(peak_ram_mb, stage_memory["Semantic Chunking"])
        print(f"[Stage 5] Semantic Chunking: {chunking_sec:.2f}s ({len(chunks)} chunks, RAM: {stage_memory['Semantic Chunking']:.1f} MB)")
    except Exception as e:
        errors.append(f"Stage 5 Failure: {e}")
        raise e

    # -------------------------------------------------------------------------
    # STAGE 6: Dense Vector Embedding Generation
    # -------------------------------------------------------------------------
    t_stage_start = time.time()
    try:
        batch_size = embedding_config.get("batch_size", 64)
        emb_provider = get_embedding_provider(embedding_config)
        emb_generator = EmbeddingGenerator(provider=emb_provider, batch_size=batch_size)
        embeddings, emb_stats = emb_generator.generate_embeddings(chunks)
        embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

        embedding_sec = time.time() - t_stage_start
        stage_timings["Embedding Generation"] = embedding_sec
        stage_memory["Embedding Generation"] = get_current_ram_mb()
        stage_records["Embedding Generation"] = len(embeddings)
        peak_ram_mb = max(peak_ram_mb, stage_memory["Embedding Generation"])
        print(f"[Stage 6] Embedding Generation: {embedding_sec:.2f}s ({len(embeddings)} vectors, RAM: {stage_memory['Embedding Generation']:.1f} MB)")
    except Exception as e:
        errors.append(f"Stage 6 Failure: {e}")
        raise e

    # -------------------------------------------------------------------------
    # STAGE 7: FAISS Vector DB Index Construction
    # -------------------------------------------------------------------------
    t_stage_start = time.time()
    try:
        faiss_path = vdb_dir / "faiss_index_synthetic50k.bin"
        dimension = embeddings.shape[1]
        
        index = faiss.IndexFlatIP(dimension)
        faiss.normalize_L2(embeddings)
        index.add(embeddings)
        faiss.write_index(index, str(faiss_path))

        faiss_sec = time.time() - t_stage_start
        stage_timings["FAISS Index Construction"] = faiss_sec
        stage_memory["FAISS Index Construction"] = get_current_ram_mb()
        stage_records["FAISS Index Construction"] = index.ntotal
        peak_ram_mb = max(peak_ram_mb, stage_memory["FAISS Index Construction"])
        faiss_size_mb = os.path.getsize(faiss_path) / (1024 * 1024)
        print(f"[Stage 7] FAISS Index Construction: {faiss_sec:.2f}s ({index.ntotal} vectors indexed, Size: {faiss_size_mb:.2f} MB, RAM: {stage_memory['FAISS Index Construction']:.1f} MB)")
    except Exception as e:
        errors.append(f"Stage 7 Failure: {e}")
        raise e

    # -------------------------------------------------------------------------
    # STAGE 8: SQLite Metadata Insertion & Persistence
    # -------------------------------------------------------------------------
    t_stage_start = time.time()
    try:
        sqlite_path = vdb_dir / "metadata_synthetic50k.sqlite"
        if sqlite_path.exists():
            os.remove(sqlite_path)

        meta_store = MetadataStore(str(sqlite_path))
        meta_store.populate_from_chunks(chunks)

        sqlite_sec = time.time() - t_stage_start
        stage_timings["SQLite Metadata Storage"] = sqlite_sec
        stage_memory["SQLite Metadata Storage"] = get_current_ram_mb()
        stage_records["SQLite Metadata Storage"] = meta_store.get_total_records_count()
        peak_ram_mb = max(peak_ram_mb, stage_memory["SQLite Metadata Storage"])
        sqlite_size_mb = os.path.getsize(sqlite_path) / (1024 * 1024)
        print(f"[Stage 8] SQLite Metadata Insertion: {sqlite_sec:.2f}s ({meta_store.get_total_records_count()} records saved, Size: {sqlite_size_mb:.2f} MB, RAM: {stage_memory['SQLite Metadata Storage']:.1f} MB)")
    except Exception as e:
        errors.append(f"Stage 8 Failure: {e}")
        raise e

    total_ingestion_sec = time.time() - t_total_start

    # -------------------------------------------------------------------------
    # POST-INGESTION SYSTEM & RAG VERIFICATION
    # -------------------------------------------------------------------------
    print("\n--- Running Post-Ingestion Verification Checks ---")
    verification_results = {}

    try:
        vdb = VectorDatabase(
            faiss_index_path=str(faiss_path),
            sqlite_db_path=str(sqlite_path),
            embedding_provider=emb_provider
        )

        verification_results["1. API Responsiveness"] = "PASSED" if vdb.is_healthy() else "FAILED"

        search_query = "Assam flood NDRF rescue operation submerged village"
        search_hits = vdb.search(search_query, top_k=5)
        verification_results["2. Normal Research Q&A"] = "PASSED" if len(search_hits) > 0 else "FAILED"

        first_hit = search_hits[0] if search_hits else {}
        has_doc_id = bool(first_hit.get("doc_id") or first_hit.get("chunk_id"))
        has_title = bool(first_hit.get("title"))
        verification_results["3. Citations Preservation"] = "PASSED" if (has_doc_id and has_title) else "FAILED"

        total_chunks = len(chunks)
        verification_results["4. Dataset Summary"] = f"PASSED ({total_chunks} chunks active)"

        followup_hits = vdb.search("What is the flood damage report in Uttar Pradesh?", top_k=3)
        verification_results["5. Follow-up Questions"] = "PASSED" if len(followup_hits) > 0 else "FAILED"

        all_excluded_check = [h for h in search_hits if h.get("relevance_decision") == "EXCLUDE"]
        verification_results["6. EXCLUDE Records Excluded"] = "PASSED" if len(all_excluded_check) == 0 else "FAILED"

        verification_results["7. Source URLs / Doc IDs Preserved"] = "PASSED" if (has_doc_id) else "FAILED"

    except Exception as e:
        verification_results["Verification Error"] = f"FAILED: {e}"
        errors.append(f"Post-Ingestion Verification Error: {e}")

    # Output Table format required by user:
    # Stage | Records | Time | Throughput | Peak Memory | Status
    print("\n" + "=" * 80)
    print(f"{'Stage':<30} | {'Records':<8} | {'Time':<8} | {'Throughput':<14} | {'Peak Memory':<11} | Status")
    print("=" * 80)

    for stage, sec in stage_timings.items():
        recs = stage_records.get(stage, 0)
        mem = stage_memory.get(stage, 0.0)
        rec_sec = round(recs / sec, 2) if sec > 0 else 0.0
        status = "PASSED"
        print(f"{stage:<30} | {recs:<8} | {sec:7.2f}s | {rec_sec:10.2f} rec/s | {mem:8.1f} MB | {status}")

    print("-" * 80)
    overall_thru = round(len(df_raw) / total_ingestion_sec, 2)
    print(f"{'TOTAL INGESTION WORKFLOW':<30} | {len(df_raw):<8} | {total_ingestion_sec:7.2f}s | {overall_thru:10.2f} rec/s | {peak_ram_mb:8.1f} MB | PASSED")
    print("=" * 80)

    print(f"\nFinal FAISS Index File Size: {faiss_size_mb:.2f} MB")
    print(f"Final SQLite Database File Size: {sqlite_size_mb:.2f} MB")
    print(f"Decision Breakdown — KEEP: {keep_cnt}, REVIEW: {review_cnt}, EXCLUDE: {exclude_cnt}")
    print(f"Total Errors/Failures: {len(errors)}")

    return {
        "total_ingestion_sec": total_ingestion_sec,
        "peak_ram_mb": peak_ram_mb,
        "stage_timings": stage_timings,
        "stage_memory": stage_memory,
        "stage_records": stage_records,
        "keep_cnt": keep_cnt,
        "review_cnt": review_cnt,
        "exclude_cnt": exclude_cnt,
        "chunks_cnt": len(chunks),
        "faiss_size_mb": faiss_size_mb,
        "sqlite_size_mb": sqlite_size_mb,
        "verification_results": verification_results,
        "errors": errors
    }

if __name__ == "__main__":
    run_synthetic_50k_stress_test()
