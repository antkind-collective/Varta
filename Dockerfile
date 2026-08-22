# ==============================================================================
# VARTA AI Assistant — Production Dockerfile
# Multi-stage lightweight container setup for FastAPI REST API & Research Web UI
# ==============================================================================

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VARTA_ENV=production \
    VARTA_HOST=0.0.0.0 \
    VARTA_PORT=8000

# Install minimal OS dependencies for FAISS, SQLite & healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code, assets, and seed data
COPY api/ ./api/
COPY src/ ./src/
COPY config/ ./config/
COPY static/ ./static/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Create runtime directories safely for databases, conversations, uploads & reports
RUN mkdir -p data/vector_db data/embeddings data/conversations data/uploads reports

# Expose API and Web UI port
EXPOSE 8000

# Health check configuration
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Launch production server binding to 0.0.0.0 and supporting cloud provider PORT
CMD ["sh", "-c", "uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-${VARTA_PORT:-8000}} --workers 1"]
