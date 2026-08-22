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
    Handles persistent disk initialization cleanly if vector DB files do not exist yet.
    """
    global _ASSISTANT_CONTROLLER
    if _ASSISTANT_CONTROLLER is None:
        project_root = Path(__file__).resolve().parent.parent
        vdb_dir = project_root / "data" / "vector_db"
        faiss_file = vdb_dir / "faiss_index.bin"
        sqlite_file = vdb_dir / "metadata.sqlite"

        # First-start persistent disk initialization: if vector DB files do not exist, ingest seed dataset
        if not (faiss_file.exists() and sqlite_file.exists()):
            seed_file = project_root / "data" / "Flood Regional News 25-26 - Sheet1.csv"
            if seed_file.exists():
                logger.info(f"Vector DB files missing. Auto-initializing from seed dataset: {seed_file.name}")
                try:
                    ingestor = DatasetIngestor(project_root=str(project_root))
                    ingestor.ingest_file(str(seed_file))
                except Exception as err:
                    logger.error(f"Failed to initialize vector database from seed: {err}")

        # Check again if database files were successfully loaded/created
        if faiss_file.exists() and sqlite_file.exists():
            logger.info(f"Loading persistent Vector Database from: {vdb_dir}")
            vdb = VectorDatabase.load(str(vdb_dir))
        else:
            logger.warning(f"Persistent Vector DB not found at {vdb_dir}. Initializing in-memory fallback.")
            from src.embedding_storage import VectorEntry
            vdb = VectorDatabase(vector_dim=384)
            vdb.add_entry(VectorEntry(
                doc_id="doc1",
                chunk_id="chunk1",
                embedding=[0.1]*384,
                text="बिहार और असम में बाढ़ से राहत शिविर खोले गए हैं।",
                metadata={"title": "Flood Report"}
            ))

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
