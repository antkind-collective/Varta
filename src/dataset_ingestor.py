import os
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

    def ingest_file(self, file_path: str, original_filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes full 5-stage ingestion for the supplied dataset file (.csv, .json, or .jsonl).
        """
        resolved_path = Path(file_path).resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Uploaded dataset file not found at: {file_path}")

        file_name = original_filename or resolved_path.name
        ext = resolved_path.suffix.lower()
        if ext not in [".csv", ".json", ".jsonl"]:
            raise ValueError(f"Unsupported file format '{ext}'. VARTA accepts .csv, .json, and .jsonl files.")

        logger.info(f"Initiating 5-stage ingestion pipeline for: {file_name}")

        # =========================================================================
        # Stage 1: Preprocessing
        # =========================================================================
        loader = DatasetLoader(str(resolved_path))
        df_raw, raw_meta = loader.load_dataset()
        if df_raw.empty:
            raise ValueError("The uploaded dataset is empty and contains no records.")

        cleaner = DataCleaner(self.column_config)
        df_clean_cols, _ = cleaner.clean_structure_and_columns(df_raw)
        df_valid, _ = cleaner.filter_and_fill_identifiers(df_clean_cols)

        if df_valid.empty:
            raise ValueError("No valid textual records found in dataset after filtering.")

        # Text Normalization
        normalizer = TextNormalizer()
        df_text_norm = df_valid.copy()
        for col in self.column_config.get("core_payload_columns", ["title", "text_content"]):
            if col in df_text_norm.columns:
                norm_series, _ = normalizer.normalize_series(df_text_norm[col])
                df_text_norm[col] = norm_series

        # Metadata Processing
        meta_processor = MetadataProcessor()
        df_meta_clean, _ = meta_processor.process_metadata(df_text_norm)

        # Deduplication
        dup_handler = DuplicateHandler(
            id_column=self.column_config.get("identifier_column", "post_id"),
            payload_columns=self.column_config.get("core_payload_columns", ["title", "text_content"])
        )
        df_dedup, dedup_stats = dup_handler.deduplicate(df_meta_clean)

        if df_dedup.empty:
            raise ValueError("All records were filtered out during deduplication.")

        # Context Relevance Engine Filtering
        rel_engine = ContextRelevanceEngine()
        context = ResearchContext()
        records = df_dedup.to_dict("records")
        filtered_records, rel_stats = rel_engine.filter_dataset(records, context=context, allowed_decisions=("KEEP", "REVIEW"))

        import pandas as pd
        df_processed = pd.DataFrame(filtered_records)
        if df_processed.empty:
            raise ValueError("All records were filtered out by ContextRelevanceEngine as EXCLUDE.")

        # =========================================================================
        # Stage 2: Document Standardization
        # =========================================================================
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

        if not valid_docs:
            raise ValueError("Failed to construct standardized documents conforming to VARTA schema.")

        # =========================================================================
        # Stage 3: Semantic Chunking
        # =========================================================================
        chunk_builder = ChunkBuilder(
            target_chunk_size=self.embedding_config.get("chunk_size_chars", 1200),
            chunk_overlap=self.embedding_config.get("chunk_overlap_chars", 200)
        )
        chunks, chunk_stats = chunk_builder.build_chunks_from_documents(valid_docs)

        if not chunks:
            raise ValueError("No valid text chunks could be extracted from documents.")

        # =========================================================================
        # Stage 4: Dense Vector Embedding Generation
        # =========================================================================
        batch_size = self.embedding_config.get("batch_size", 64)
        emb_provider = get_embedding_provider(self.embedding_config)
        emb_generator = EmbeddingGenerator(provider=emb_provider, batch_size=batch_size)
        new_embeddings, emb_stats = emb_generator.generate_embeddings(chunks)

        # Ensure float32 C-contiguous 2D matrix
        new_embeddings = np.ascontiguousarray(new_embeddings, dtype=np.float32)

        # =========================================================================
        # Stage 5: Incremental Vector DB Indexing & Storage
        # =========================================================================
        faiss_path = self.vdb_dir / "faiss_index.bin"
        sqlite_path = self.vdb_dir / "metadata.sqlite"
        manifest_path = self.vdb_dir / "db_manifest.json"

        if not FAISS_AVAILABLE:
            raise RuntimeError("FAISS library is required for vector database indexing.")

        if faiss_path.exists() and sqlite_path.exists():
            # Read existing FAISS index & append
            faiss_index = faiss.read_index(str(faiss_path))
            start_vector_id = int(faiss_index.ntotal)

            # Normalize new embeddings and add to FAISS
            faiss.normalize_L2(new_embeddings)
            faiss_index.add(new_embeddings)
            total_vectors_after = int(faiss_index.ntotal)

            # Save updated FAISS index
            faiss.write_index(faiss_index, str(faiss_path))

            # Append chunk metadata to SQLite
            meta_store = MetadataStore(str(sqlite_path))
            records_added = meta_store.append_chunks(chunks, start_vector_id=start_vector_id)
            total_sqlite_records = meta_store.get_total_records_count()
        else:
            # Build new FAISS index & initialize SQLite metadata store from scratch
            from src.index_builder import FAISSIndexBuilder
            builder = FAISSIndexBuilder()
            build_res = builder.build_and_save_index(new_embeddings, str(faiss_path))
            total_vectors_after = build_res.get("num_vectors", len(chunks))

            meta_store = MetadataStore(str(sqlite_path))
            meta_store.append_chunks(chunks, start_vector_id=0)
            total_sqlite_records = meta_store.get_total_records_count()

        # Update db_manifest.json
        manifest = {}
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

        manifest["total_vectors"] = total_vectors_after
        manifest["sqlite_records"] = total_sqlite_records
        manifest["last_updated"] = datetime.now(timezone.utc).isoformat()
        manifest["last_ingested_file"] = file_name
        manifest["last_ingested_chunks"] = len(chunks)

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Append to chunks.json for archival/validation integrity
        chunks_json_path = self.emb_dir / "chunks.json"
        if chunks_json_path.exists():
            try:
                with open(chunks_json_path, "r", encoding="utf-8") as f:
                    existing_chunks = json.load(f)
                existing_chunks.extend(chunks)
                with open(chunks_json_path, "w", encoding="utf-8") as f:
                    json.dump(existing_chunks, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Could not append to chunks.json: {e}")

        logger.info(
            f"Dataset Ingestion Complete: {len(valid_docs)} documents, {len(chunks)} chunks added. "
            f"Total Corpus: {total_vectors_after:,} vectors."
        )

        return {
            "status": "ready",
            "message": f"Successfully ingested {len(valid_docs)} documents ({len(chunks)} chunks). Dataset is now live and queryable.",
            "filename": file_name,
            "documents_ingested": len(valid_docs),
            "chunks_indexed": len(chunks),
            "total_vectors_available": total_vectors_after,
            "duration_sec": round(emb_stats.get("duration_sec", 0.0), 2)
        }
