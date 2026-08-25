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

        target_dim = 1536
        if faiss_file.exists() and sqlite_file.exists():
            logger.info(f"Loading persistent Vector Database from: {vdb_dir}")
            vdb = VectorDatabase.load(str(vdb_dir))
            if vdb.index is not None and getattr(vdb.index, "d", None) != target_dim:
                logger.warning(
                    f"Loaded persistent FAISS index dimension ({vdb.index.d}) does not match "
                    f"active model dimension ({target_dim}). Re-initializing clean {target_dim}-dim index."
                )
                import faiss
                index = faiss.IndexFlatIP(target_dim) if 'faiss' in sys.modules or hasattr(faiss, 'IndexFlatIP') else None
                manifest = {"total_vectors": 0, "sqlite_records": vdb.metadata_store.get_total_records_count(), "status": "reinitialized_dim_mismatch"}
                vdb = VectorDatabase(index=index, metadata_store=vdb.metadata_store, manifest=manifest, load_time_sec=0.0)
        else:
            logger.warning(f"Persistent Vector DB files missing at {vdb_dir}. Initializing clean base VectorDatabase.")
            import faiss
            from src.metadata_store import MetadataStore
            meta_store = MetadataStore(str(vdb_dir / "metadata.sqlite"))
            index = faiss.IndexFlatIP(target_dim) if 'faiss' in sys.modules or hasattr(faiss, 'IndexFlatIP') else None
            manifest = {"total_vectors": 0, "sqlite_records": 0, "status": "uninitialized"}
            vdb = VectorDatabase(index=index, metadata_store=meta_store, manifest=manifest, load_time_sec=0.0)

        retriever = SemanticRetriever(vector_db=vdb)
        llm_adapter = get_llm_adapter()
        orchestrator = RAGOrchestrator(
            retriever=retriever,
            llm_adapter=llm_adapter,
            max_context_tokens=2048
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

    vdb = VectorDatabase.load(str(vdb_dir))
    target_dim = 1536
    if vdb.index is not None and getattr(vdb.index, "d", None) != target_dim:
        logger.warning(
            f"Reloaded persistent FAISS index dimension ({vdb.index.d}) does not match "
            f"active model dimension ({target_dim}). Re-initializing clean {target_dim}-dim index."
        )
        import faiss
        index = faiss.IndexFlatIP(target_dim) if 'faiss' in sys.modules or hasattr(faiss, 'IndexFlatIP') else None
        manifest = {"total_vectors": 0, "sqlite_records": vdb.metadata_store.get_total_records_count(), "status": "reinitialized_dim_mismatch"}
        vdb = VectorDatabase(index=index, metadata_store=vdb.metadata_store, manifest=manifest, load_time_sec=0.0)

    new_retriever = SemanticRetriever(vector_db=vdb)

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
