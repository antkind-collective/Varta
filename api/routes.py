import time
import logging
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from api.schemas import (
    ChatRequest,
    ChatResponse,
    SessionCreateResponse,
    SessionEndResponse,
    HealthResponse,
    SystemInfoResponse,
    ErrorResponse,
    DatasetIngestResponse,
    ReviewDecisionRequest,
    ReviewRecordItem,
    ReviewQueueResponse
)
from api.dependencies import get_assistant_controller, get_server_uptime, reload_assistant_controller
from src.assistant_controller import AssistantController
from src.dataset_ingestor import DatasetIngestor, get_ingestion_status, update_ingestion_status

logger = logging.getLogger("VARTA.Routes")
router = APIRouter()

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="API Health Check",
    description="Returns operational status, API version, server uptime, and active LLM model/provider info."
)
def health_check(
    controller: AssistantController = Depends(get_assistant_controller)
) -> HealthResponse:
    llm = controller.rag_orchestrator.llm_adapter
    provider_name = getattr(llm, "__class__", type(llm)).__name__
    model_name = llm.get_model_name() if hasattr(llm, "get_model_name") else "unknown"

    return HealthResponse(
        status="ok",
        api_version="1.0.0",
        uptime_seconds=get_server_uptime(),
        active_model=model_name,
        provider=provider_name
    )

@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input message"},
        404: {"model": ErrorResponse, "description": "Session not found"}
    },
    summary="Process Chat Message",
    description="Main chat endpoint wrapping AssistantController. Executes context resolution, agentic planning, tool routing, and RAG retrieval."
)
def chat_endpoint(
    req: ChatRequest,
    controller: AssistantController = Depends(get_assistant_controller)
) -> ChatResponse:
    clean_msg = req.message.strip()
    if not clean_msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message field cannot be empty or whitespace."
        )

    if req.session_id:
        existing_session = controller.conversation_manager.get_session(req.session_id)
        if not existing_session or existing_session.status != "active":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session ID '{req.session_id}' not found or has been closed."
            )

    try:
        resp_dict = controller.process_query(clean_msg, session_id=req.session_id)
        return ChatResponse(
            session_id=resp_dict["session_id"],
            answer=resp_dict.get("assistant_answer") or resp_dict.get("answer", ""),
            citations=resp_dict.get("citations", []),
            confidence=resp_dict.get("confidence", {}),
            execution_time_ms=resp_dict.get("execution_time_ms", 0.0),
            tool_used=resp_dict.get("tool_selected", "rag_search"),
            plan_type=resp_dict.get("plan_type", "direct")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing /chat request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal assistant processing error: {e}"
        )

@router.post(
    "/session",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Chat Session",
    description="Explicitly initializes a new conversation session and returns its unique session_id."
)
def create_session(
    controller: AssistantController = Depends(get_assistant_controller)
) -> SessionCreateResponse:
    session = controller.conversation_manager.create_session()
    return SessionCreateResponse(session_id=session.session_id)

@router.delete(
    "/session/{session_id}",
    response_model=SessionEndResponse,
    responses={404: {"model": ErrorResponse, "description": "Session not found"}},
    summary="End Chat Session",
    description="Gracefully closes an active conversation session and frees in-memory history."
)
def end_session(
    session_id: str,
    controller: AssistantController = Depends(get_assistant_controller)
) -> SessionEndResponse:
    session = controller.conversation_manager.get_session(session_id)
    if not session or session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session ID '{session_id}' not found or already closed."
        )

    controller.conversation_manager.end_session(session_id)
    return SessionEndResponse(
        session_id=session_id,
        message="Session gracefully closed."
    )

@router.get(
    "/system",
    response_model=SystemInfoResponse,
    summary="System Telemetry & Information",
    description="Reports backend system status, LLM model/provider, Vector DB status, active sessions, and registered tool counts."
)
def system_info(
    controller: AssistantController = Depends(get_assistant_controller)
) -> SystemInfoResponse:
    llm = controller.rag_orchestrator.llm_adapter
    provider_name = getattr(llm, "__class__", type(llm)).__name__
    model_name = llm.get_model_name() if hasattr(llm, "get_model_name") else "unknown"

    active_sessions_count = len(controller.conversation_manager.list_active_sessions())
    tool_count = len(controller.tool_registry.list_tools())
    vdb_status = "healthy" if controller.rag_orchestrator.retriever and controller.rag_orchestrator.retriever.vector_db else "unavailable"

    return SystemInfoResponse(
        active_model=model_name,
        provider=provider_name,
        vector_db_status=vdb_status,
        active_sessions=active_sessions_count,
        tool_count=tool_count,
        build_version="1.0.0"
    )

def _run_background_dataset_ingestion(temp_file_path: str, filename: str):
    """Background worker for asynchronous dataset ingestion without blocking HTTP proxy timeouts."""
    file_path = Path(temp_file_path)
    try:
        logger.info(f"Starting background dataset ingestion for: {filename}")
        ingestor = DatasetIngestor()
        ingestor.ingest_file(str(file_path), original_filename=filename)
        reload_assistant_controller()
        logger.info(f"Background dataset ingestion completed successfully for: {filename}")
    except Exception as e:
        logger.error(f"Error during background ingestion of {filename}: {e}", exc_info=True)
        update_ingestion_status(
            status="failed",
            error=str(e),
            message=f"Dataset ingestion error: {e}"
        )
    finally:
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass

@router.get(
    "/dataset/status",
    summary="Get Dataset Ingestion Progress & Status",
    description="Returns the real-time background status, batch progress, and corpus vector counts of dataset ingestion."
)
async def get_dataset_status():
    return get_ingestion_status()

@router.post(
    "/dataset/upload",
    response_model=DatasetIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"model": DatasetIngestResponse, "description": "Dataset upload accepted and ingestion started in background"},
        400: {"model": ErrorResponse, "description": "Invalid file type or empty dataset"},
        500: {"model": ErrorResponse, "description": "Ingestion upload error"}
    },
    summary="Upload & Ingest New Dataset",
    description="Uploads a .csv, .json, or .jsonl dataset, and starts background streaming ingestion into the vector database."
)
async def upload_dataset(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> DatasetIngestResponse:
    filename = file.filename or "uploaded_dataset"
    ext = Path(filename).suffix.lower()

    if ext not in [".csv", ".json", ".jsonl"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. VARTA accepts .csv, .json, and .jsonl files."
        )

    # Clean up ALL temporary uploads and stale embedding cache files to free volume disk space
    project_root = Path(__file__).resolve().parent.parent
    uploads_dir = project_root / "data" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    for old_file in uploads_dir.glob("*"):
        if old_file.is_file():
            try:
                old_file.unlink()
            except Exception:
                pass

    emb_dir = project_root / "data" / "embeddings"
    if emb_dir.exists():
        for old_emb in emb_dir.glob("*"):
            if old_emb.is_file():
                try:
                    old_emb.unlink()
                except Exception:
                    pass

    temp_file_path = uploads_dir / f"upload_{int(time.time())}_{filename}"

    try:
        # Stream file in 64KB chunks to avoid RAM spikes and write efficiently
        file_size = 0
        with open(temp_file_path, "wb") as f:
            while True:
                chunk = await file.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                file_size += len(chunk)

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty."
            )

        update_ingestion_status(
            status="processing",
            filename=filename,
            current_batch=0,
            documents_ingested=0,
            chunks_indexed=0,
            total_vectors_available=0,
            message=f"Uploaded {filename} ({file_size:,} bytes). Ingestion pipeline initiated in background...",
            error=None
        )

        # Enqueue background task
        background_tasks.add_task(_run_background_dataset_ingestion, str(temp_file_path), filename)

        return DatasetIngestResponse(
            status="processing",
            message=f"Dataset '{filename}' received ({file_size:,} bytes). Processing in background.",
            filename=filename,
            documents_ingested=0,
            chunks_indexed=0,
            total_vectors_available=0,
            duration_sec=0.0
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling /dataset/upload request: {e}", exc_info=True)
        if temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dataset upload initialization error: {e}"
        )

# =========================================================================
# Sagar Preprocessing Review Queue Endpoints
# =========================================================================

def _get_review_queue_path() -> Path:
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "reports" / "sagar_review_queue.csv"

@router.get(
    "/review/records",
    response_model=ReviewQueueResponse,
    summary="Get Context-Specific Review Queue Records",
    description="Retrieves borderline records pending stakeholder review for the active research context."
)
def get_review_records(context_topic: str = "Floods in Assam") -> ReviewQueueResponse:
    import pandas as pd
    review_path = _get_review_queue_path()
    if not review_path.exists():
        return ReviewQueueResponse(
            context_topic=context_topic,
            total_records=0,
            reviewed_count=0,
            pending_count=0,
            keep_count=0,
            exclude_count=0,
            records=[]
        )

    try:
        df = pd.read_csv(review_path).fillna("")
        records = []
        keep_count = 0
        exclude_count = 0
        pending_count = 0

        for _, row in df.iterrows():
            rec_id = str(row.get("record_id", ""))
            title = str(row.get("title", ""))
            content = str(row.get("content_preview", ""))
            score = float(row.get("relevance_score", 0.0)) if str(row.get("relevance_score", "")).strip() != "" else 0.0
            keywords = str(row.get("matched_keywords", "None"))
            reason = str(row.get("relevance_reason", ""))
            final_dec = str(row.get("final_decision", "REVIEW")).upper()
            row_ctx = str(row.get("context_topic", context_topic))

            if final_dec == "KEEP":
                keep_count += 1
            elif final_dec == "EXCLUDE":
                exclude_count += 1
            else:
                pending_count += 1

            records.append(ReviewRecordItem(
                record_id=rec_id,
                title=title,
                content_preview=content,
                relevance_score=score,
                matched_keywords=keywords,
                relevance_reason=reason,
                final_decision=final_dec,
                context_topic=row_ctx
            ))

        total = len(records)
        reviewed = keep_count + exclude_count

        return ReviewQueueResponse(
            context_topic=context_topic,
            total_records=total,
            reviewed_count=reviewed,
            pending_count=pending_count,
            keep_count=keep_count,
            exclude_count=exclude_count,
            records=records
        )
    except Exception as e:
        logger.error(f"Error reading review queue CSV: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load review queue: {e}"
        )

@router.post(
    "/review/decision",
    response_model=ReviewQueueResponse,
    summary="Submit Stakeholder Review Decision",
    description="Updates final decision (KEEP / EXCLUDE) for a specific record for the active research context."
)
def submit_review_decision(req: ReviewDecisionRequest) -> ReviewQueueResponse:
    import pandas as pd
    clean_dec = req.decision.strip().upper()
    if clean_dec not in ("KEEP", "EXCLUDE"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be either 'KEEP' or 'EXCLUDE'."
        )

    review_path = _get_review_queue_path()
    if not review_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review queue CSV not found."
        )

    try:
        df = pd.read_csv(review_path).fillna("")
        if "record_id" not in df.columns:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Malformed review queue format."
            )

        match_mask = df["record_id"].astype(str) == req.record_id
        if not match_mask.any():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Record ID '{req.record_id}' not found in review queue."
            )

        if "context_topic" not in df.columns:
            df["context_topic"] = req.context_topic or "Floods in Assam"

        df.loc[match_mask, "final_decision"] = clean_dec
        if req.context_topic:
            df.loc[match_mask, "context_topic"] = req.context_topic

        df.to_csv(review_path, index=False, encoding="utf-8")

        # Return updated state
        return get_review_records(context_topic=req.context_topic or "Floods in Assam")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error persisting review decision: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist decision: {e}"
        )
