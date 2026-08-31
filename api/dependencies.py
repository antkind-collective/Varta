import sys
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple
from src.metadata_store import MetadataStore
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

def _ensure_seed_metadata(project_root: Path, sqlite_path: Path, gz_path: Optional[Path] = None, force: bool = False):
    expected_total = 49374
    needs_sync = force
    
    candidate_gz_paths = [
        project_root / "src" / "seed_metadata.sqlite.gz",
        project_root / "data" / "vector_db" / "metadata.sqlite.gz",
        sqlite_path.parent / "metadata.sqlite.gz"
    ]
    if gz_path:
        candidate_gz_paths.insert(0, gz_path)

    valid_gz = None
    for p in candidate_gz_paths:
        if p.exists() and p.is_file():
            valid_gz = p
            break

    if not needs_sync:
        if not sqlite_path.exists():
            needs_sync = True
        else:
            try:
                import sqlite3
                conn = sqlite3.connect(str(sqlite_path))
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunk_metadata'")
                if not cursor.fetchone():
                    needs_sync = True
                else:
                    cursor.execute("SELECT source_dataset, COUNT(*) FROM chunk_metadata GROUP BY source_dataset")
                    rows = dict(cursor.fetchall())
                    total = sum(rows.values())
                    if total != expected_total or "master_news_corpus" not in rows or "sagar_reddit_dataset" not in rows:
                        needs_sync = True
                conn.close()
            except Exception as e:
                logger.warning(f"Error checking existing metadata.sqlite ({e}), flagging for sync...")
                needs_sync = True

    if needs_sync and valid_gz and valid_gz.exists():
        import gzip
        import shutil
        logger.info(f"Restoring metadata.sqlite from synchronized gold standard archive: {valid_gz}...")
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        temp_sqlite = sqlite_path.parent / "metadata_temp.sqlite"
        try:
            with gzip.open(valid_gz, "rb") as f_in:
                with open(temp_sqlite, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            if sqlite_path.exists():
                try:
                    sqlite_path.unlink()
                except Exception as e:
                    logger.warning(f"Could not unlink old sqlite directly ({e})")
            try:
                temp_sqlite.replace(sqlite_path)
            except Exception:
                with open(temp_sqlite, "rb") as f_in, open(sqlite_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                try:
                    temp_sqlite.unlink()
                except Exception:
                    pass
            logger.info("Successfully restored and synchronized 49,374 metadata records into metadata.sqlite.")
        except Exception as e:
            logger.error(f"Error extracting metadata archive: {e}", exc_info=True)



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
        gz_file = vdb_dir / "metadata.sqlite.gz"
        manifest_file = vdb_dir / "db_manifest.json"

        from src.embedding_providers import get_embedding_provider
        from src.metadata_store import MetadataStore
        import faiss

        active_provider = get_embedding_provider()
        target_dim = getattr(active_provider, "dimension", 384)
        _ensure_seed_metadata(project_root, sqlite_file, gz_file)
        meta_store = MetadataStore(str(sqlite_file))

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
