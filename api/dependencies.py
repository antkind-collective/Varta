import sys
import time
import logging
from pathlib import Path
from typing import Optional
from src.vector_database import VectorDatabase
from src.semantic_retriever import SemanticRetriever
from src.rag_orchestrator import RAGOrchestrator
from src.llm_adapter import get_llm_adapter
from src.conversation_manager import ConversationManager
from src.assistant_controller import AssistantController
from src.dataset_ingestor import DatasetIngestor

logger = logging.getLogger("VARTA.Dependencies")

# Global Singleton State
_SERVER_START_TIME: float = time.time()
_ASSISTANT_CONTROLLER: Optional[AssistantController] = None

def _ensure_seed_metadata(project_root: Path, meta_store: MetadataStore):
    if meta_store.get_total_records_count() == 0:
        logger.info("Initializing metadata.sqlite from seed files...")
        chunks_json = project_root / "data" / "embeddings" / "chunks.json"
        if chunks_json.exists():
            import json
            with open(chunks_json, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            # Filter out the 8 test fabricated records if present
            valid_chunks = [c for c in chunks if not str(c.get("doc_id", "")).startswith("reddit_post_")]
            meta_store.append_chunks(valid_chunks, source_dataset="master_news_corpus")
            logger.info(f"Seeded {len(valid_chunks)} master_news_corpus chunks into metadata.sqlite.")
        
        reddit_csv = project_root / "data" / "uploads" / "Disaster Reddit.csv"
        if reddit_csv.exists():
            import json
            from src.dataset_loader import DatasetLoader
            from src.preprocessing_pipeline import PreprocessingPipeline
            from src.document_builder import DocumentBuilder
            
            with open(project_root / "config" / "column_mapping.json", "r", encoding="utf-8") as f:
                col_config = json.load(f)
            with open(project_root / "config" / "embedding_config.json", "r", encoding="utf-8") as f:
                emb_config = json.load(f)
                
            cleaner = PreprocessingPipeline(col_config)
            doc_builder = DocumentBuilder(
                chunk_size=emb_config.get("chunk_size_chars", 1000),
                chunk_overlap=emb_config.get("chunk_overlap_chars", 200)
            )
            loader = DatasetLoader(str(reddit_csv))
            for df_raw in loader.stream_data(batch_size=1000):
                df_clean, _ = cleaner.clean_structure_and_columns(df_raw)
                df_valid, _ = cleaner.filter_and_fill_identifiers(df_clean)
                if not df_valid.empty:
                    batch_docs = doc_builder.build_canonical_documents(df_valid, dataset_name="sagar_reddit_dataset")
                    batch_chunks = doc_builder.extract_hierarchical_chunks(batch_docs, dataset_name="sagar_reddit_dataset")
                    meta_store.append_chunks(batch_chunks, source_dataset="sagar_reddit_dataset")
            logger.info("Seeded sagar_reddit_dataset into metadata.sqlite.")

def get_assistant_controller() -> AssistantController:
    """
    FastAPI dependency supplying singleton AssistantController instance.
    Initializes Vector DB, Semantic Retriever, LLM Adapter, RAG Orchestrator,
    and Conversation Manager on first invocation.
    """
    global _ASSISTANT_CONTROLLER
    if _ASSISTANT_CONTROLLER is None:
        project_root = Path(__file__).resolve().parent.parent
        vdb_dir = project_root / "data" / "vector_db"
        faiss_file = vdb_dir / "faiss_index.bin"
        sqlite_file = vdb_dir / "metadata.sqlite"
        manifest_file = vdb_dir / "db_manifest.json"

        from src.embedding_providers import get_embedding_provider
        from src.metadata_store import MetadataStore
        import faiss

        active_provider = get_embedding_provider()
        target_dim = getattr(active_provider, "dimension", 384)
        meta_store = MetadataStore(str(sqlite_file))
        _ensure_seed_metadata(project_root, meta_store)

        if faiss_file.exists():
            logger.info(f"Loading persistent FAISS index from: {faiss_file}")
            index = faiss.read_index(str(faiss_file))
        else:
            logger.warning(f"FAISS index file missing at {faiss_file}. Initializing clean {target_dim}-dim index.")
            index = faiss.IndexFlatIP(target_dim)

        manifest = {}
        if manifest_file.exists():
            import json
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        else:
            manifest = {
                "total_vectors": index.ntotal if index else 0,
                "sqlite_records": meta_store.get_total_records_count(),
                "status": "ready"
            }

        vdb = VectorDatabase(index=index, metadata_store=meta_store, manifest=manifest, load_time_sec=0.0)

        retriever = SemanticRetriever(vector_db=vdb, embedding_provider=active_provider)
        llm_adapter = get_llm_adapter()
        orchestrator = RAGOrchestrator(
            retriever=retriever,
            llm_adapter=llm_adapter,
            max_context_tokens=3500
        )

        conversation_manager = ConversationManager()
        _ASSISTANT_CONTROLLER = AssistantController(
            rag_orchestrator=orchestrator,
            conversation_manager=conversation_manager
        )

    return _ASSISTANT_CONTROLLER

def reload_assistant_controller() -> AssistantController:
    """
    Reloads the VectorDatabase and SemanticRetriever in the active AssistantController,
    enabling newly ingested documents to be queried immediately without server restart.
    """
    global _ASSISTANT_CONTROLLER
    project_root = Path(__file__).resolve().parent.parent
    vdb_dir = project_root / "data" / "vector_db"

    if not vdb_dir.exists():
        return get_assistant_controller()

    from src.embedding_providers import get_embedding_provider
    active_provider = get_embedding_provider()
    target_dim = getattr(active_provider, "dimension", 384)

    vdb = VectorDatabase.load(str(vdb_dir))
    if vdb.index is not None and getattr(vdb.index, "d", None) != target_dim:
        logger.warning(
            f"Reloaded persistent FAISS index dimension ({vdb.index.d}) does not match "
            f"active model dimension ({target_dim}). Re-initializing clean {target_dim}-dim index."
        )
        import faiss
        index = faiss.IndexFlatIP(target_dim) if 'faiss' in sys.modules or hasattr(faiss, 'IndexFlatIP') else None
        manifest = {"total_vectors": 0, "sqlite_records": vdb.metadata_store.get_total_records_count(), "status": "reinitialized_dim_mismatch"}
        vdb = VectorDatabase(index=index, metadata_store=vdb.metadata_store, manifest=manifest, load_time_sec=0.0)

    new_retriever = SemanticRetriever(vector_db=vdb, embedding_provider=active_provider)

    if _ASSISTANT_CONTROLLER is not None:
        _ASSISTANT_CONTROLLER.rag_orchestrator.retriever = new_retriever
    else:
        llm_adapter = get_llm_adapter()
        orchestrator = RAGOrchestrator(
            retriever=new_retriever,
            llm_adapter=llm_adapter,
            max_context_tokens=2048
        )
        conversation_manager = ConversationManager()
        _ASSISTANT_CONTROLLER = AssistantController(
            rag_orchestrator=orchestrator,
            conversation_manager=conversation_manager
        )

    return _ASSISTANT_CONTROLLER

def get_server_uptime() -> float:
    """Returns total server uptime in seconds."""
    return round(time.time() - _SERVER_START_TIME, 2)
