import os
import sys

# Limit OpenMP/BLAS thread pool allocations to prevent PyTorch C++ memory spikes
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

try:
    import torch
    torch.set_num_threads(1)
except Exception:
    pass

import re
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone
import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

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

logger = logging.getLogger("DatasetIngestor")

# Global thread-safe ingestion status tracker
_INGESTION_STATUS: Dict[str, Any] = {
    "status": "idle",
    "filename": None,
    "current_batch": 0,
    "total_batches": 0,
    "documents_ingested": 0,
    "chunks_indexed": 0,
    "total_vectors_available": 0,
    "peak_rss_mb": 0.0,
    "message": "System ready for dataset upload.",
    "error": None,
    "duration_sec": 0.0,
    "updated_at": None
}

def get_ingestion_status() -> Dict[str, Any]:
    """Returns the current background ingestion progress and operational state."""
    global _INGESTION_STATUS
    return dict(_INGESTION_STATUS)

def update_ingestion_status(**kwargs):
    """Updates the global ingestion status tracker."""
    global _INGESTION_STATUS
    _INGESTION_STATUS.update(kwargs)
    _INGESTION_STATUS["updated_at"] = datetime.now(timezone.utc).isoformat()

class DatasetIngestor:
    """
    End-to-End Dynamic Dataset Ingestion & Incremental Vector Indexing Engine.
    Executes VARTA's complete 5-stage ingestion pipeline:
    1. Preprocessing (loading, pruning, normalization, metadata cleaning, deduplication)
    2. Standardization (transforming rows into canonical document JSON representations)
    3. Chunking (hierarchical sliding-window semantic chunking with title injection)
    4. Embedding (dense vector generation via provider-agnostic embeddings engine)
    5. Vector DB Indexing & Live Sync (FAISS index append + SQLite metadata sync + live reload)
    """

    def __init__(self, project_root: Optional[str] = None):
        if project_root:
            self.project_root = Path(project_root)
        else:
            self.project_root = Path(__file__).resolve().parent.parent

        self.config_dir = self.project_root / "config"
        self.data_dir = self.project_root / "data"
        self.vdb_dir = self.data_dir / "vector_db"
        self.emb_dir = self.data_dir / "embeddings"

        # Load configs
        with open(self.config_dir / "column_mapping.json", "r", encoding="utf-8") as f:
            self.column_config = json.load(f)

        with open(self.config_dir / "embedding_config.json", "r", encoding="utf-8") as f:
            self.embedding_config = json.load(f)

        with open(self.config_dir / "vector_db_config.json", "r", encoding="utf-8") as f:
            self.vdb_config = json.load(f)

    def ingest_file(self, *args, **kwargs) -> Dict[str, Any]:
        """Alias for ingest_dataset."""
        return self.ingest_dataset(*args, **kwargs)

    def ingest_dataset(
        self,
        file_path: str,
        original_filename: Optional[str] = None,
        dataset_name: Optional[str] = None,
        batch_size: int = 500,
        embedding_batch_size: int = 256
    ) -> Dict[str, Any]:
        """
        Executes full 5-stage ingestion for the supplied dataset file (.csv, .json, or .jsonl).
        Processes datasets in streaming batches to maintain flat, low memory usage (< 150 MB RAM).
        """
        import gc
        import time
        import pandas as pd

        try:
            import psutil
            process = psutil.Process()
            def get_rss_mb() -> float:
                return round(process.memory_info().rss / (1024 * 1024), 2)
        except Exception:
            def get_rss_mb() -> float:
                return 0.0

        resolved_path = Path(file_path).resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Uploaded dataset file not found at: {file_path}")

        file_name = original_filename or resolved_path.name
        ext = resolved_path.suffix.lower()
        if ext not in [".csv", ".json", ".jsonl"]:
            raise ValueError(f"Unsupported file format '{ext}'. VARTA accepts .csv, .json, and .jsonl files.")

        # Determine explicit or inferred source_dataset origin label
        raw_label = dataset_name or original_filename or resolved_path.stem
        clean_label = re.sub(r'[^a-zA-Z0-9_-]', '_', Path(raw_label).stem.lower().strip())
        effective_dataset_name = clean_label if clean_label else "uploaded_dataset"

        if not FAISS_AVAILABLE:
            raise RuntimeError("FAISS library is required for vector database indexing.")

        initial_rss = get_rss_mb()
        peak_rss = initial_rss
        start_time = time.time()

        update_ingestion_status(
            status="processing",
            filename=file_name,
            current_batch=0,
            documents_ingested=0,
            chunks_indexed=0,
            total_vectors_available=0,
            peak_rss_mb=initial_rss,
            message=f"Starting dataset ingestion for {file_name}...",
            error=None
        )

        logger.info(
            f"Initiating streaming 5-stage ingestion pipeline for: {file_name} "
            f"(batch_size={batch_size}, emb_batch_size={embedding_batch_size}, initial_rss={initial_rss} MB)"
        )
        baseline_rss = get_rss_mb()
        initial_rss = baseline_rss
        peak_rss = initial_rss
        peak_rss_relevance = initial_rss
        peak_rss_embedding = initial_rss
        peak_rss_faiss = initial_rss

        loader = DatasetLoader(str(resolved_path))
        cols_to_drop = self.column_config.get("columns_to_drop", [])
        chunk_generator = loader.stream_dataset_chunks(batch_size=batch_size, columns_to_drop=cols_to_drop)

        cleaner = DataCleaner(self.column_config)
        normalizer = TextNormalizer()
        meta_processor = MetadataProcessor()
        dup_handler = DuplicateHandler(
            id_column=self.column_config.get("identifier_column", "post_id"),
            payload_columns=self.column_config.get("core_payload_columns", ["title", "text_content"])
        )
        # Reuse single embedding provider & generator across all batches
        emb_provider = get_embedding_provider(self.embedding_config)
        model_load_rss = get_rss_mb()
        if model_load_rss > peak_rss:
            peak_rss = model_load_rss

        doc_builder = DocumentBuilder(schema_version="1.0.0")
        validator = DocumentValidator()
        chunk_builder = ChunkBuilder(
            target_chunk_size=self.embedding_config.get("chunk_size_chars", 1200),
            chunk_overlap=self.embedding_config.get("chunk_overlap_chars", 200)
        )
        emb_generator = EmbeddingGenerator(provider=emb_provider, batch_size=embedding_batch_size)

        faiss_path = self.vdb_dir / "faiss_index.bin"
        sqlite_path = self.vdb_dir / "metadata.sqlite"
        manifest_path = self.vdb_dir / "db_manifest.json"
        self.vdb_dir.mkdir(parents=True, exist_ok=True)

        target_dim = emb_provider.get_dimension()
        faiss_index = None
        if faiss_path.exists():
            try:
                faiss_index = faiss.read_index(str(faiss_path))
                if faiss_index.d != target_dim:
                    logger.warning(
                        f"Existing FAISS index dimension ({faiss_index.d}) does not match "
                        f"active model dimension ({target_dim}). Re-initializing clean {target_dim}-dim FAISS IndexFlatIP."
                    )
                    faiss_index = faiss.IndexFlatIP(target_dim)
                else:
                    logger.info(f"Loaded existing FAISS index from {faiss_path} with {faiss_index.ntotal} vectors.")
            except Exception as e:
                logger.warning(f"Failed to read existing FAISS index file ({e}). Initializing clean {target_dim}-dim index.")
                faiss_index = faiss.IndexFlatIP(target_dim)
        else:
            faiss_index = faiss.IndexFlatIP(target_dim)
            logger.info(f"Initialized new FAISS IndexFlatIP with dimension {target_dim}.")

        meta_store = MetadataStore(str(sqlite_path))

        total_valid_docs = 0
        total_chunks_added = 0
        doc_index_counter = 0
        batch_counter = 0
        total_embedding_time = 0.0

        for df_raw_chunk in chunk_generator:
            if df_raw_chunk.empty:
                continue

            batch_counter += 1
            raw_count = len(df_raw_chunk)
            print(f"[Batch {batch_counter} | Step 1/5] Streamed {raw_count} raw rows. Current RSS: {get_rss_mb():.1f} MB", flush=True)

            df_clean_cols, _ = cleaner.clean_structure_and_columns(df_raw_chunk)
            df_valid, _ = cleaner.filter_and_fill_identifiers(df_clean_cols)
            del df_raw_chunk, df_clean_cols

            if df_valid.empty:
                del df_valid
                gc.collect()
                continue

            for col in self.column_config.get("core_payload_columns", ["title", "text_content"]):
                if col in df_valid.columns:
                    norm_series, _ = normalizer.normalize_series(df_valid[col])
                    df_valid[col] = norm_series

            df_meta_clean, _ = meta_processor.process_metadata(df_valid)
            del df_valid

            df_dedup, _ = dup_handler.deduplicate(df_meta_clean)
            del df_meta_clean

            if df_dedup.empty:
                del df_dedup
                gc.collect()
                continue

            records = df_dedup.to_dict("records")
            del df_dedup

            # Sub-batch progress: Stage 1/5 Clean Master Standardization
            update_ingestion_status(
                status="processing",
                filename=file_name,
                current_batch=batch_counter,
                documents_ingested=total_valid_docs,
                chunks_indexed=total_chunks_added,
                total_vectors_available=int(faiss_index.ntotal),
                peak_rss_mb=peak_rss,
                message=f"Batch {batch_counter}: Standardizing {len(records)} clean master records..."
            )

            print(f"[Batch {batch_counter} | Step 2/5] Standardizing & Chunking {len(records)} clean docs... Current RSS: {get_rss_mb():.1f} MB", flush=True)

            # Build documents directly from clean records
            documents = []
            for rec in records:
                doc = doc_builder.build_document(rec, doc_index=doc_index_counter)
                doc_index_counter += 1
                documents.append(doc)

            del records

            valid_docs = []
            for doc in documents:
                is_valid, _ = validator.validate_document(doc)
                if is_valid:
                    valid_docs.append(doc)

            del documents

            if not valid_docs:
                gc.collect()
                continue

            chunks, _ = chunk_builder.build_chunks_from_documents(valid_docs)
            if not chunks:
                del valid_docs
                gc.collect()
                continue

            # Sub-batch progress: Stage 4/5 Generating Dense Embeddings
            update_ingestion_status(
                status="processing",
                filename=file_name,
                current_batch=batch_counter,
                documents_ingested=total_valid_docs,
                chunks_indexed=total_chunks_added,
                total_vectors_available=int(faiss_index.ntotal),
                peak_rss_mb=peak_rss,
                message=f"Batch {batch_counter}: Embedding {len(chunks)} chunks via OpenAI (384-d)..."
            )

            print(f"[Batch {batch_counter} | Step 3/5] Generating 384-d embeddings for {len(chunks)} chunks... Current RSS: {get_rss_mb():.1f} MB", flush=True)

            emb_start = time.time()
            new_embeddings, emb_stats = emb_generator.generate_embeddings(chunks)
            total_embedding_time += emb_stats.get("duration_sec", 0.0)
            new_embeddings = np.ascontiguousarray(new_embeddings, dtype=np.float32)

            rss_after_emb = get_rss_mb()
            if rss_after_emb > peak_rss_embedding:
                peak_rss_embedding = rss_after_emb

            print(f"[Batch {batch_counter} | Step 4/5] Indexing into FAISS & SQLite... Current RSS: {get_rss_mb():.1f} MB", flush=True)

            # Incrementally add to loaded FAISS index and SQLite store
            start_vector_id = meta_store.get_next_vector_id()
            faiss.normalize_L2(new_embeddings)
            faiss_index.add(new_embeddings)
            del new_embeddings, valid_docs
            gc.collect()

            meta_store.append_chunks(chunks, start_vector_id=start_vector_id, dataset_name=effective_dataset_name)

            rss_after_faiss = get_rss_mb()
            if rss_after_faiss > peak_rss_faiss:
                peak_rss_faiss = rss_after_faiss

            total_valid_docs += len(chunks)
            total_chunks_added += len(chunks)

            del chunks
            gc.collect()

            current_rss = get_rss_mb()
            if current_rss > peak_rss:
                peak_rss = current_rss

            update_ingestion_status(
                status="processing",
                filename=file_name,
                current_batch=batch_counter,
                documents_ingested=total_valid_docs,
                chunks_indexed=total_chunks_added,
                total_vectors_available=int(faiss_index.ntotal),
                peak_rss_mb=peak_rss,
                message=f"Batch {batch_counter}: {total_valid_docs:,} docs / {total_chunks_added:,} chunks indexed."
            )

            print(f"[Batch {batch_counter} | Step 5/5 Done] Total indexed: {total_valid_docs} docs / {total_chunks_added} chunks. RSS: {current_rss:.1f} MB (Peak: {peak_rss:.1f} MB)", flush=True)

            print(
                f"  [Batch {batch_counter}] Ingested {total_valid_docs} docs / {total_chunks_added} chunks total so far. "
                f"Current RSS: {current_rss} MB (Peak: {peak_rss} MB)",
                flush=True
            )
            sys.stdout.flush()
            sys.stderr.flush()

        if total_chunks_added == 0 and faiss_index.ntotal == 0:
            update_ingestion_status(
                status="failed",
                error="All records were filtered out or invalid. No valid chunks were added.",
                message="Dataset validation failed: No valid chunks found."
            )
            raise ValueError("All records were filtered out or invalid. No valid chunks were added.")

        # Save FAISS index to disk once after all streaming batches complete
        if total_chunks_added > 0:
            logger.info(f"Persisting FAISS index to disk at {faiss_path} ({faiss_index.ntotal} vectors)...")
            faiss.write_index(faiss_index, str(faiss_path))

        total_vectors_after = int(faiss_index.ntotal)
        total_sqlite_records = meta_store.get_total_records_count()
        elapsed_time = round(time.time() - start_time, 2)

        # Update db_manifest.json
        manifest = {}
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

        manifest["total_vectors"] = total_vectors_after
        manifest["sqlite_records"] = total_sqlite_records
        manifest["last_updated"] = datetime.now(timezone.utc).isoformat()
        manifest["last_ingested_file"] = file_name
        manifest["last_ingested_chunks"] = total_chunks_added

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info(
            f"Streaming Dataset Ingestion Complete: {total_valid_docs} documents, {total_chunks_added} chunks added in {elapsed_time}s. "
            f"Total Corpus: {total_vectors_after:,} vectors. Peak RSS: {peak_rss} MB"
        )

        final_result = {
            "status": "ready",
            "message": f"Successfully ingested {total_valid_docs:,} documents ({total_chunks_added:,} chunks). Dataset is now live and queryable.",
            "filename": file_name,
            "documents_ingested": total_valid_docs,
            "chunks_ingested": total_chunks_added,
            "total_vectors_in_corpus": total_vectors_after,
            "sqlite_records_in_corpus": total_sqlite_records,
            "baseline_rss_mb": baseline_rss,
            "model_load_rss_mb": model_load_rss,
            "peak_rss_relevance_mb": peak_rss_relevance,
            "peak_rss_embedding_mb": peak_rss_embedding,
            "peak_rss_faiss_mb": peak_rss_faiss,
            "peak_rss_mb": peak_rss,
            "final_rss_mb": get_rss_mb(),
            "duration_sec": elapsed_time,
            "embedding_time_sec": round(total_embedding_time, 2)
        }

        update_ingestion_status(
            status="ready",
            filename=file_name,
            current_batch=batch_counter,
            documents_ingested=total_valid_docs,
            chunks_indexed=total_chunks_added,
            total_vectors_available=total_vectors_after,
            peak_rss_mb=peak_rss,
            duration_sec=elapsed_time,
            message=final_result["message"],
            error=None
        )

        return final_result
