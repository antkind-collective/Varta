# VARTA — AI Research Assistant

VARTA is a modular RAG-based AI research assistant designed to process large datasets and answer user queries using relevant information retrieved from the uploaded data.

The system combines semantic search, vector embeddings, FAISS retrieval, metadata storage, and an LLM to generate grounded responses with source references.

---

## Features

- CSV dataset ingestion
- Data cleaning and normalization
- Context relevance filtering
- Semantic/vector search
- Multilingual retrieval support
- SentenceTransformer / dense embeddings
- FAISS vector database
- SQLite metadata storage
- RAG-based answer generation
- Source URL/reference support
- Conversation/session handling
- Configurable Top-K retrieval
- REST API through FastAPI
- Static web interface
- Dockerized deployment
- OpenAI Responses API integration

---

## Architecture

```text
User
  ↓
Web UI
  ↓
FastAPI
  ↓
Query Processing
  ↓
Semantic Embedding
  ↓
FAISS Vector Search
  ↓
Relevant Context / Top-K Results
  ↓
RAG Context Assembly
  ↓
OpenAI LLM
  ↓
Grounded Response + Sources
```

### Data Ingestion

```text
CSV Dataset
    ↓
Cleaning & Normalization
    ↓
Relevance Filtering
    ↓
Chunking
    ↓
Embeddings
    ↓
FAISS Index
    +
SQLite Metadata
```

---

## Tech Stack

* **Backend:** FastAPI
* **Frontend:** HTML / CSS / JavaScript
* **Embeddings:** SentenceTransformers / OpenAI Embeddings (384 dimensions)
* **Vector Database:** FAISS
* **Metadata Database:** SQLite
* **LLM:** OpenAI Responses API
* **Containerization:** Docker
* **Deployment Platform:** Render / Railway (with Persistent Volume)
* **Language:** Python

---

## Project Structure

```text
VARTA/
│
├── api/
│   ├── app.py
│   ├── routes.py
│   ├── schemas.py
│   └── dependencies.py
│
├── src/
│   ├── assistant_controller.py
│   ├── chunk_builder.py
│   ├── conversation_validator.py
│   ├── document_validator.py
│   └── ...
│
├── data/
│   ├── vector_db/
│   ├── embeddings/
│   ├── conversations/
│   ├── uploads/
│   └── ...
│
├── scripts/
│   ├── ...
│
├── reports/
│
├── static/
│   └── ...
│
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

## Environment Variables

Create a `.env` file locally or configure these variables in the deployment platform.

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=your_model
LLM_PROVIDER=openai
```

### Important

* Never commit API keys or other secrets to GitHub.
* `OPENAI_API_KEY` must be configured as a secret/environment variable in the deployment platform.

---

## Running Locally

### 1. Clone the repository

```bash
git clone <repository-url>
cd Varta
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

**Windows**

```bash
venv\Scripts\activate
```

**Linux/macOS**

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create `.env`:

```env
OPENAI_API_KEY=your_key
OPENAI_MODEL=your_model
LLM_PROVIDER=openai
```

### 5. Start the application

```bash
uvicorn api.app:app --reload
```

The application will be available locally at:

```text
http://localhost:8000
```

API documentation:

```text
http://localhost:8000/docs
```

---

## Docker

Build the image:

```bash
docker build -t varta .
```

Run:

```bash
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e OPENAI_MODEL=your_model \
  -e LLM_PROVIDER=openai \
  varta
```

---

## Dataset Upload

VARTA currently accepts **CSV datasets** through the dataset upload functionality.

The uploaded dataset is processed through:

1. Validation
2. Cleaning
3. Normalization
4. Context relevance filtering
5. Chunking
6. Embedding generation
7. FAISS indexing
8. SQLite metadata storage

Once ingestion is complete, the indexed information becomes available to the RAG pipeline.

---

## Query Processing

For every user query, VARTA:

1. Processes the query.
2. Generates a semantic embedding.
3. Searches the FAISS vector index.
4. Retrieves the most relevant records/chunks.
5. Builds context from the retrieved information.
6. Sends the relevant context to the LLM.
7. Generates a response based on the retrieved data.
8. Returns relevant source information where available.

The retrieval pipeline is designed to avoid sending the complete dataset to the LLM for every query. Only relevant retrieved context is passed to the model.

---

## Top-K Retrieval

VARTA uses a configurable **Top-K** retrieval approach.

Top-K determines how many candidate results are retrieved from the vector database before context is assembled for the LLM.

The value needs to be tuned depending on:

* Dataset size
* Query type
* Retrieval relevance
* Context size
* Response quality
* Latency
* API cost

A higher Top-K can improve retrieval coverage for some queries, while a lower value can reduce irrelevant context and cost.

---

## API Endpoints

| Endpoint          | Method | Purpose                       |
| ----------------- | ------ | ----------------------------- |
| `/`               | GET    | Web application               |
| `/health`         | GET    | Application health check      |
| `/system`         | GET    | System information            |
| `/docs`           | GET    | Swagger API documentation     |
| `/chat`           | POST   | Submit a query                |
| `/session`        | ...    | Session/conversation handling |
| `/dataset/upload` | POST   | Upload and ingest dataset     |

---

# Deployment

VARTA is designed to be deployed as a Dockerized FastAPI service.

### Deployment Platform

**Render / Railway**

The deployment must use an instance with a **persistent disk/volume** for production use.

> **CRITICAL REQUIREMENT:** A **persistent disk is a strict deployment requirement**, not an optional feature.

Persistent storage is required because VARTA stores:

* Uploaded datasets
* FAISS vector index
* SQLite metadata database
* Conversation logs and session state

These files must survive service restarts and redeployments.

### Required Environment Variables

Configure the following in the deployment platform:

```text
OPENAI_API_KEY
OPENAI_MODEL
LLM_PROVIDER
```

`OPENAI_API_KEY` must be stored as a **secret environment variable** and must never be committed to the repository.

### Redeployment

The deployment is connected to the central GitHub repository.

To deploy a new version:

1. Push the changes to the configured GitHub branch.
2. The platform detects the new commit.
3. The platform builds the Docker image.
4. The service is redeployed.
5. Persistent disk data remains intact across redeployments.

---

# Production Considerations

VARTA currently uses local FAISS and SQLite storage.

For production:

* **Persistent disk is a hard requirement** to prevent loss of index and metadata state.
* Keep API keys in platform secrets; avoid storing secrets in Git.
* Keep the deployment on a single instance.
* Monitor memory usage during dataset ingestion.
* Use batched/streaming ingestion for large datasets.

---

# Known Limitations / Next Steps

### 1. Numerical / Aggregation Queries

The current retrieval pipeline is primarily optimized for **semantic search and qualitative information retrieval**.

Queries requiring operations such as:

* COUNT
* SUM
* Percentage calculations
* Complex aggregations
* Structured statistical analysis

may require a dedicated structured-query/data-processing layer rather than relying only on semantic retrieval.

### 2. Retrieval Tuning

Top-K and retrieval thresholds can be further tuned using a larger evaluation dataset to improve recall and answer quality.

### 3. Large Dataset Ingestion

Large datasets should be processed in batches to control memory consumption and avoid holding the complete dataset and all embeddings in memory simultaneously.

### 4. Single-Instance Architecture

The current architecture is primarily designed for a single running application instance.

For larger-scale production usage, the system could be extended with:

* External database/storage
* Distributed vector storage
* Background ingestion workers
* Multiple application instances
* Centralized object storage

### 5. External Backup / Storage

A future improvement could be integrating an external storage solution such as Supabase Storage to periodically back up:

* Uploaded datasets
* SQLite metadata
* FAISS indexes

This is optional and not required for the current persistent-disk deployment.

### 6. Authentication

Authentication is not implemented inside VARTA.

Access can be restricted at the infrastructure layer using **Cloudflare Access** with the organization's domain.

---

# Testing & Validation

The project includes health checks and validation scripts for:

* Application health
* Vector database health
* Retrieval quality
* RAG pipeline
* OpenAI connectivity
* Multilingual queries
* End-to-end query processing

The system has been tested with both English and Hindi queries to validate multilingual retrieval.

---

# Security

* API keys are loaded through environment variables.
* Secrets must not be committed to GitHub.
* Production API keys should be stored using the deployment platform's secret/environment-variable mechanism.
* Authentication/access control can be handled through Cloudflare Access.

---

# Future Improvements

Potential future improvements include:

* Structured query engine for numerical/aggregation queries
* Hybrid search (semantic + keyword)
* Improved reranking
* Better retrieval evaluation and benchmarking
* Background dataset ingestion
* External persistent object storage
* Distributed vector database
* Authentication and user management
* Multi-instance/scalable deployment
* Advanced source/document parsing

---

## Status

VARTA currently provides an end-to-end RAG pipeline covering:

**Dataset → Processing → Embeddings → FAISS Retrieval → Context Assembly → LLM → Answer + Sources**

The current architecture is **deployable** for continued development, evaluation, and operational use, with the known limitations and future scale improvements documented above.
