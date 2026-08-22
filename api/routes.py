import time
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from api.schemas import (
    ChatRequest,
    ChatResponse,
    SessionCreateResponse,
    SessionEndResponse,
    HealthResponse,
    SystemInfoResponse,
    ErrorResponse,
    DatasetIngestResponse
)
from api.dependencies import get_assistant_controller, get_server_uptime, reload_assistant_controller
from src.assistant_controller import AssistantController
from src.dataset_ingestor import DatasetIngestor

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
    except Exception as e:
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

@router.post(
    "/dataset/upload",
    response_model=DatasetIngestResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file type or empty dataset"},
        500: {"model": ErrorResponse, "description": "Ingestion processing error"}
    },
    summary="Upload & Ingest New Dataset",
    description="Uploads a .csv, .json, or .jsonl dataset, processes it through VARTA's 5-stage ingestion pipeline, and indexes it into the vector database for real-time querying."
)
async def upload_dataset(
    file: UploadFile = File(...),
) -> DatasetIngestResponse:
    filename = file.filename or "uploaded_dataset"
    ext = Path(filename).suffix.lower()

    if ext not in [".csv", ".json", ".jsonl"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. VARTA accepts .csv, .json, and .jsonl files."
        )

    # Save uploaded file to a temporary uploads directory
    uploads_dir = Path(__file__).resolve().parent.parent / "data" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    temp_file_path = uploads_dir / f"upload_{int(time.time())}_{filename}"

    try:
        content = await file.read()
        if not content or len(content.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty."
            )
        with open(temp_file_path, "wb") as f:
            f.write(content)

        ingestor = DatasetIngestor()
        result = ingestor.ingest_file(str(temp_file_path), original_filename=filename)

        # Reload assistant controller so new vectors are immediately live
        reload_assistant_controller()

        return DatasetIngestResponse(
            status=result.get("status", "ready"),
            message=result.get("message", "Dataset successfully indexed and queryable."),
            filename=filename,
            documents_ingested=result.get("documents_ingested", 0),
            chunks_indexed=result.get("chunks_indexed", 0),
            total_vectors_available=result.get("total_vectors_available", 0),
            duration_sec=result.get("duration_sec", 0.0)
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset validation error: {ve}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dataset ingestion error: {e}"
        )
    finally:
        if temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except Exception:
                pass
