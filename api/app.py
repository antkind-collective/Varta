import sys
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Determine environment flags
VARTA_ENV = os.getenv("VARTA_ENV", "development").lower()
IS_PRODUCTION = VARTA_ENV == "production"
ENABLE_DOCS = os.getenv("VARTA_ENABLE_DOCS", "true").lower() in ("true", "1", "yes")

# CORS Origins configuration
raw_cors = os.getenv("VARTA_CORS_ORIGINS", "*")
if raw_cors.strip() == "*":
    ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = [origin.strip() for origin in raw_cors.split(",") if origin.strip()]

from api.routes import router as api_router
from api.dependencies import get_assistant_controller

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Pre-warm AssistantController singleton (VectorDB, SentenceTransformer, LLM)
    get_assistant_controller()
    yield

app = FastAPI(
    title="VARTA AI Assistant REST API",
    description=(
        "Service-oriented backend REST API wrapping VARTA Conversational AI Assistant. "
        "Exposes endpoints for health checks, chat processing, session management, and system telemetry."
    ),
    version="1.0.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets directory
static_dir = project_root / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", summary="Researcher Web Interface", description="Renders the researcher-facing web UI.")
def serve_ui():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(content={"status": "ok", "message": "VARTA REST API running."})

# Include API Router
app.include_router(api_router)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled internal exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": f"An unhandled server error occurred: {str(exc)}",
            "error_code": "INTERNAL_SERVER_ERROR"
        }
    )

def main():
    import uvicorn
    host = os.getenv("VARTA_HOST", "0.0.0.0")
    port = int(os.getenv("VARTA_PORT", "8000"))
    reload = not IS_PRODUCTION and os.getenv("VARTA_RELOAD", "true").lower() in ("true", "1")
    uvicorn.run("api.app:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    main()
