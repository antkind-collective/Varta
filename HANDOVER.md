# VARTA System Handover & Technical Status Report

**Project Title:** VARTA — Grounded Disaster Intelligence & Multi-Source Evidence Retrieval  
**Handover Date:** September 3, 2026  
**Live Production URL:** [https://varta-production-0038.up.railway.app](https://varta-production-0038.up.railway.app)  
**Repository:** `antkind-collective/Varta` (Branch: `main`)

---

## Executive Summary

VARTA is a production-grade conversational research intelligence system designed for disaster risk reduction, hydrometeorological analysis, and regional policy evaluation across English and Hindi corpora.

This document establishes the exact state of the system for handover, detailing what is **fully built and working**, how the system handles **cleaned vs. raw dataset metrics**, what has been **designed and partially proven**, what is **explicitly not yet built**, and the **recommended next steps** for engineering teams continuing this work.

---

## 1. What's Fully Built & Working

### 1.1 Two-Layer Scoped RAG Architecture
- **Layer 1 (Corpus Scoping):** Fast SQL-accelerated metadata filtering that bounds document search spaces by geography (Assam, Bihar, Odisha, Mumbai, Punjab, Himachal Pradesh, Uttarakhand, Sikkim), disaster domain (floods, cyclones, landslides, cloudbursts), and source dataset tags.
- **Layer 2 (Semantic Vector Retrieval):** FAISS-indexed Cosine Similarity matching over OpenAI `text-embedding-3-small` dense vector embeddings configured at 384 dimensions (via native Matryoshka `dimensions=384` reduction parameter to minimize memory footprint on Railway).
- **Retrieval Depth (`top_k = 10`):** Retrieves up to 10 granular text chunks per query (doubled from previous 5-chunk limit), maximizing evidentiary support while remaining well within the 3,500-token budget.

### 1.2 Automated Clean vs. Raw Dataset Inventory Engine
- **Automated Hygiene & Out-of-Domain Detection:** In `src/metadata_store.py` (`get_available_datasets`), an automated SQL filter dynamically evaluates raw rows:
  - Excludes blank or trivial records (`< 40 characters`).
  - Excludes promotional/out-of-domain hashtag spam (e.g., gaming clips like *Bus Simulator*, car sales, music videos, and real-estate ads).
  - Identifies authentic disaster content containing verified disaster/emergency markers (`flood`, `cyclone`, `landslide`, `rain`, `NDRF`, `SDRF`, `rescue`, `relief`, `बाढ़`, `आपदा`).
- **Production Corpus Scale (20,656 total vector chunks across 17,230 raw rows):**

| Dataset Source | Raw Uploaded Rows | Clean Disaster Records | Searchable Vector Chunks | Noise / Spam Filtered |
| :--- | :---: | :---: | :---: | :---: |
| **Disaster YouTube** (`disaster_youtube`) | **8,345** | **~6,150** (73.7%) | **10,446** | ~2,195 (gaming, songs, ads, blank shorts) |
| **Sagar's Reddit Data** (`sagar_reddit_dataset`) | **8,885** | **8,203** (92.3%) | **10,210** | 682 (off-topic / blank) |
| **Total Active Corpus** | **17,230** | **~14,353** | **20,656** | **~2,877** |

### 1.3 Multi-Turn Conversational Memory & Context Resolution
- **Session State Management:** In-memory + SQLite conversation log persistence with unique session IDs (`/session`, `/chat`).
- **Query Resolution:** Resolves ambiguous follow-up questions (e.g., *"What about Patna?"*, *"What were the relief measures there?"*) by combining conversation history with domain taxonomy context before retrieval.
- **Deduplication & Anti-Looping:** Context assembler tracks previously cited document IDs (`excluded_post_ids`) across turns to prevent repetitive citations.

### 1.4 Dataset Metadata & Pipeline Routing (`SystemInfoTool`)
- **Direct Inventory Answering:** Whenever a user queries counts (`"how many total videos"`, `"how many records"`, `"how many entries"`), `AgentPlanner` routes to `SystemInfoTool`, which leads with the **cleaned authentic count** rather than blindly reporting raw database rows or chunks.
- **Verified 5-Stage Cleaning Pipeline Documentation:** Queries about data cleaning (`"what was the cleaning logic you used?"`) return the exact 5-stage transformation pipeline:
  1. *Raw Text Ingestion & Sanitization:* HTML stripping, whitespace normalization, Unicode sanitization.
  2. *Deduplication & Multilingual Partitioning:* Content hash deduplication, English/Hindi language classification.
  3. *Semantic Sliding-Window Chunking:* 500-token chunks with 100-token overlap to maintain narrative continuity.
  4. *Dense Vector Embedding:* 384-dimensional dense vectors via OpenAI `text-embedding-3-small`.
  5. *Dynamic Context Relevance & SQL Scoping:* Layer 1 geographic and domain pre-filtering.

### 1.5 Grounded & Natural Response Generation
- **Corpus-Aware Prompting (`src/prompt_builder.py`):** Explicitly informs the LLM that the repository contains 20,000+ indexed entries, preventing the model from claiming the dataset consists only of the 3–10 retrieved snippets.
- **Banned Sample-as-Dataset Fallacy:** Prohibits artificial percentage calculations over retrieved sample blocks (e.g. no longer outputting *"1 out of 5 = 20%"*). For statistical queries, the model qualitative analyzes retrieved evidence and notes that exact corpus-wide percentages require full-corpus database aggregation.
- **Hybrid LLM Fallback (`src/rag_orchestrator.py`):** Replaced rigid hardcoded refusal short-circuits with an intelligent hybrid fallback. When no direct documents meet the similarity threshold, the model answers helpfully using its broad analytical knowledge while transparently stating the retrieval boundary.

### 1.6 Knowledge Scope & Dataset Picker (API + UI)
- **Backend API (`GET /datasets/list`):** Aggregates indexed chunk counts and clean document counts across all uploaded datasets directly from SQLite `chunk_metadata`.
- **Frontend Chip UI:** Interactive multi-select filter allowing researchers to search across *All Datasets* or scope queries to specific uploaded datasets (e.g., *Disaster YouTube* vs. *Sagar's Reddit Data*).
- **Backend Scoping Filter:** The `/chat` endpoint accepts an optional `dataset_filter` array and enforces strict SQL vector scoping.

### 1.7 Live Railway Production Deployment
- **Live URL:** [https://varta-production-0038.up.railway.app](https://varta-production-0038.up.railway.app)
- **Deployment Engine:** Docker container with automated database integrity synchronization on startup via `src/seed_metadata.sqlite.gz` and on-demand sync endpoint (`/dataset/sync-seed`).
- **Resource Footprint:** Operates strictly within Railway's 500 MB RAM and 500 MB persistent disk boundaries through memory-mapped SQLite and Matryoshka 384-dim embeddings.

---

## 2. What's Designed & Partially Proven

### 2.1 Inducto-Deductive Taxonomy Generation
- **Pipeline (`src/taxonomy_generator.py`):** Automatically synthesizes theoretical research briefs with empirical dataset samples to produce formal coding schemas.
- **Approved Taxonomy Schema (`data/taxonomies/generated_disaster_taxonomy.md`):** Complete 4-dimensional coding framework:
  1. `dim_primary_frame`: F1 (Alerts) to F6 (Non-disaster/Metaphorical)
  2. `dim_causal_attribution`: C1 (Meteorological) to C6 (Descriptive/No claim)
  3. `dim_temporal_phase`: T1 (Pre-event) to T5 (General/No anchor)
  4. `dim_stance_action`: A1 (Accountability) to A6 (Neutral)

### 2.2 Sample Classification Mechanism & Statistical Aggregations
- **Working Mechanism (`scripts/run_sample_taxonomy_classification.py`):** Evaluated and tagged across a representative stratified sample of **2,500 records** (1,800 news + 700 Reddit).
- **Sample Results Table (`sample_taxonomy_classifications` in SQLite):**

| Primary Communicative Frame (`dim_primary_frame`) | Sample Count | Sample Percentage (%) |
| :--- | :---: | :---: |
| **F3: Impact, Disruption & Damage** | 912 | 36.48% |
| **F4: Emergency Response, Relief & Community Solidarity** | 825 | 33.00% |
| **F1: Forecasts, Alerts & Hazard Monitoring** | 420 | 16.80% |
| **F5: Governance, Policy & Institutional Politics** | 192 | 7.68% |
| **F6: Non-Disaster / Metaphorical / Unrelated** | 118 | 4.72% |
| **F2: Risk, Vulnerability & Preparedness Assessment** | 33 | 1.32% |

---

## 3. What's NOT Built (Known Scope Boundaries)

To ensure clear ownership and avoid misaligned expectations, the following items from the broad theoretical brief remain open for future engineering phases:

1. **Full-Corpus Classification at Scale:**
   - The taxonomy classifier has only been run on a sample ($N = 2,500$). Running batch inference across the entire 20,656+ chunk corpus requires a background worker queue or asynchronous batch LLM pipeline.
2. **Production SQL Statistical Query Engine UI:**
   - The system does not currently feature a dedicated frontend dashboard for executing ad-hoc SQL aggregation queries, cross-tabs, or computing statistical margins of error through the web interface.
3. **Advanced Brief Modules (Voice, Narrative Stage & Gap Mapping):**
   - **Voice Mapping:** Classifying speaker identities (citizen vs. official vs. journalist).
   - **Narrative Stage Mapping:** Tracking thematic evolution across multi-week crisis timelines.
   - **Discourse Gap Mapping:** Automated comparative matrix identifying disconnects between official reports and public discourse.

---

## 4. Key Architecture & File Reference

```
VARTA/
├── api/
│   ├── app.py                   # FastAPI application & lifespan management
│   ├── routes.py                # REST endpoints (/chat, /health, /datasets/list, /session, /dataset/upload, /dataset/sync-seed)
│   ├── schemas.py               # Pydantic request/response schemas
│   └── dependencies.py          # Singleton AssistantController & SQLite seed extraction
├── config/
│   ├── analysis_config.json     # Analysis & evaluation thresholds
│   ├── column_mapping.json      # Dynamic CSV header resolvers
│   └── context_relevance_config.json # Keep/Review/Exclude threshold boundaries
├── data/
│   ├── taxonomies/
│   │   ├── generated_disaster_taxonomy.md     # Approved v1 coding taxonomy
│   │   └── sample_classification_results.md  # 2,500-sample statistical report
│   └── vector_db/
│       ├── faiss_index.bin      # FAISS Dense Vector Index (384 dim)
│       └── metadata.sqlite      # SQLite metadata database with chunk_metadata
├── scripts/
│   ├── run_sample_taxonomy_classification.py # Sample taxonomy tagging & SQL aggregations
│   ├── test_live_uvicorn_startup.py          # Local container startup simulator
│   ├── rebuild_faiss_index.py                # FAISS indexing & metadata alignment script
│   └── verify_all_ast_and_types.py           # Static analysis and type checker
├── src/
│   ├── assistant_controller.py  # Central workflow orchestrator & tool registration
│   ├── agent_planner.py         # Agentic intent classifier & execution plan generator
│   ├── context_resolver.py      # Multi-turn context resolution & query reformulator
│   ├── prompt_builder.py        # Natural conversational prompt constructor with corpus awareness
│   ├── rag_orchestrator.py      # End-to-end RAG pipeline, top_k=10, hybrid LLM fallback
│   ├── metadata_store.py        # SQLite relational metadata layer, clean vs raw metrics, scoping queries
│   ├── vector_database.py       # FAISS vector database facade & search engine
│   ├── seed_metadata.sqlite.gz  # Compressed seed archive for Docker container sync
│   └── tools/
│       ├── system_info_tool.py  # Reports clean counts, raw rows, noise breakdown, 5-stage pipeline
│       ├── rag_search_tool.py   # RAG vector search tool
│       ├── calculator_tool.py   # Deterministic arithmetic calculator
│       └── conversation_memory_tool.py # Session memory retrieval
├── static/
│   ├── app.js                   # Frontend client logic & dataset chip picker
│   ├── index.html               # Web interface
│   └── styles.css               # Clean typography & theme design
├── Dockerfile                   # Railway production deployment container definition
└── HANDOVER.md                  # This technical handover document
```

---

## 5. Next Steps for Next Team

1. **Scale Full-Corpus Taxonomy Classification:**
   - Create a background Celery/RQ worker script that reads `chunk_metadata` in batches of 500, executes zero-shot or few-shot classification using `src/taxonomy_generator.py`, and writes tags back into `chunk_metadata`.
2. **Build Analytics & Visualization Dashboard:**
   - Expose a `GET /analytics/taxonomy-breakdown` endpoint querying `sample_taxonomy_classifications` or `chunk_metadata`.
   - Add chart visualizations (e.g., Chart.js or D3.js bar charts for Primary Frame and Causal Attribution) in the web UI.
3. **Direct Excel (.xlsx) Upload Pipeline:**
   - Extend [src/dataset_loader.py](file:///c:/Users/binda/OneDrive/Desktop/Varta/src/dataset_loader.py) with `openpyxl`/`pd.read_excel` to accept `.xlsx` spreadsheets directly without manual CSV export.
