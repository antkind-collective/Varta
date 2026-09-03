# VARTA System Handover & Technical Status Report

**Project Title:** VARTA — Grounded Disaster Intelligence & Multi-Source Evidence Retrieval  
**Handover Date:** August 31, 2026  
**Live Production URL:** [https://varta-production-0038.up.railway.app](https://varta-production-0038.up.railway.app)  
**Repository:** `antkind-collective/Varta` (Branch: `main`)

---

## Executive Summary

VARTA is a production-grade conversational research intelligence system designed for disaster risk reduction, hydrometeorological analysis, and regional policy evaluation across English and Hindi corpora.

This document establishes the exact state of the system for handover, detailing what is **fully built and working**, what has been **designed and partially proven**, what is **explicitly not yet built**, and the **recommended next steps** for engineering teams continuing this work.

---

## 1. What's Fully Built & Working

### 1.1 Two-Layer Scoped RAG Architecture
- **Layer 1 (Corpus Scoping):** Fast SQL-accelerated metadata filtering that bounds document search spaces by geography (e.g., Assam, Bihar, Odisha, Mumbai), disaster domain (floods, cyclones, landslides), and source dataset tags.
- **Layer 2 (Semantic Vector Retrieval):** FAISS-indexed Cosine Similarity matching over OpenAI `text-embedding-3-small` dense vector embeddings configured at 384 dimensions (via OpenAI's native Matryoshka `dimensions=384` reduction parameter to minimize memory and keep the vector index lightweight on Railway), retrieving granular text chunks synchronized 1-to-1 with SQLite metadata.

### 1.2 Multi-Turn Conversational Memory & Context Resolution
- **Session State Management:** In-memory + SQLite conversation log persistence with unique session IDs (`/session`, `/chat`).
- **Query Resolution:** Resolves ambiguous follow-up questions (e.g., *"What about Patna?"*, *"What were the relief measures there?"*) by combining conversation history with domain taxonomy context before retrieval.
- **Deduplication & Anti-Looping:** Context assembler tracks previously cited document IDs (`excluded_post_ids`) across turns to prevent repetitive citations.

### 1.3 Knowledge Scope & Dataset Picker (API + UI)
- **Backend API (`GET /datasets/list`):** Aggregates indexed chunk counts across all uploaded datasets directly from SQLite `chunk_metadata`.
- **Frontend Chip UI:** Interactive multi-select filter allowing researchers to search across *All Datasets* or scope queries to specific uploaded datasets (e.g., *Master News Corpus* vs. *Sagar's Reddit Data*).
- **Backend Scoping Filter:** The `/chat` endpoint accepts an optional `dataset_filter` array and enforces strict SQL vector scoping.

### 1.4 Natural Analytical Response Generation
- **Prompt Engineering (`src/prompt_builder.py`):** Generates ChatGPT/Claude-style analytical prose tailored to inquiry types (situational updates, comparative analysis, policy evaluations) without rigid boilerplate or formulaic sections.
- **Verifiable Citations:** Inline citation format `[D1: Source Title]` mapped directly to full source documents with clean, canonical URLs and provenance metadata.

### 1.5 Live Railway Production Deployment
- **Live URL:** `https://varta-production-749d.up.railway.app`
- **Indexed Production Corpus (10,210 vectors total):**
  - `sagar_reddit_dataset`: **10,210 chunks** (Real Reddit discussions, community updates, and megathread posts)
  - *(Note: `master_news_corpus` was permanently pruned and removed along with raw CSV files to free ~265 MB disk space to remain well within Railway's 500 MB persistent volume limit).*
- **Deployment Engine:** Docker container with automated database integrity synchronization on startup via `src/seed_metadata.sqlite.gz` and fallback on-demand endpoint (`/dataset/sync-seed`).


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
| :--- | :--- | :--- |
| **F3: Impact, Disruption & Damage** | 912 | 36.48% |
| **F4: Emergency Response, Relief & Community Solidarity** | 825 | 33.00% |
| **F1: Forecasts, Alerts & Hazard Monitoring** | 420 | 16.80% |
| **F5: Governance, Policy & Institutional Politics** | 192 | 7.68% |
| **F6: Non-Disaster / Metaphorical / Unrelated** | 118 | 4.72% |
| **F2: Risk, Vulnerability & Preparedness Assessment** | 33 | 1.32% |

> [!NOTE]
> This demonstrates the automated categorical classification and SQL statistical pipeline working end-to-end on empirical data. Full-corpus classification was deferred to respect project delivery timelines.

---

## 3. What's NOT Built (Known Scope Boundaries)

To ensure clear ownership and avoid misaligned expectations, the following items from the broad theoretical brief remain open for future engineering phases:

1. **Full-Corpus Classification at Scale:**
   - The taxonomy classifier has only been run on a sample ($N = 2,500$). Running batch inference across the entire 49,374+ chunk corpus requires a background worker queue or asynchronous batch LLM pipeline.
2. **Production SQL Statistical Query Engine UI:**
   - The system does not currently feature a frontend dashboard for executing ad-hoc SQL aggregation queries, cross-tabs, or computing statistical margins of error through the web interface.
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
│   ├── routes.py                # REST endpoints (/chat, /health, /datasets/list, /session, /dataset/sync-seed)
│   ├── models.py                # Pydantic request/response schemas
│   └── dependencies.py          # Singleton AssistantController & SQLite seed extraction
├── config/
│   └── config.yaml              # Core hyperparameters & model configs
├── data/
│   ├── taxonomies/
│   │   ├── generated_disaster_taxonomy.md     # Approved v1 coding taxonomy
│   │   └── sample_classification_results.md  # 2,500-sample statistical report
│   └── vector_db/
│       ├── faiss_index.bin      # FAISS Dense Vector Index (10,210 vectors, 384 dim, 14.96 MB)
│       └── metadata.sqlite      # SQLite metadata database (10,210 rows, 24.09 MB)
├── scripts/
│   ├── run_sample_taxonomy_classification.py # Sample taxonomy tagging & SQL aggregations
│   ├── test_live_uvicorn_startup.py          # Local container startup simulator
│   ├── remove_master_news_corpus.py          # Pruning & disk reclamation script
│   └── rebuild_faiss_index.py                # FAISS indexing & metadata alignment script
├── src/
│   ├── assistant_controller.py  # Central workflow orchestrator
│   ├── context_resolver.py      # Multi-turn context resolution & query reformulator
│   ├── prompt_builder.py        # Natural conversational prompt constructor
│   ├── metadata_store.py        # SQLite relational metadata layer & scoping queries
│   ├── vector_database.py       # FAISS vector database facade & search engine
│   ├── seed_metadata.sqlite.gz  # 4.38 MB compressed seed archive for Docker container sync
│   └── taxonomy_generator.py    # Inducto-deductive taxonomy generator
├── static/
│   ├── app.js                   # Frontend client logic & dataset chip picker
│   ├── index.html               # Web interface
│   └── styles.css               # Clean typography & theme design
├── Dockerfile                   # Railway production deployment container definition
└── HANDOVER.md                  # This technical handover document
```

---

## 5. Next Steps for Next Team

1. **Scale Taxonomy Classification:**
   - Create a background Celery/RQ worker script that reads `chunk_metadata` in batches of 500, executes zero-shot or few-shot classification using `src/taxonomy_generator.py`, and writes tags back into `chunk_metadata`.
2. **Build Analytics & Visualization Dashboard:**
   - Expose a `GET /analytics/taxonomy-breakdown` endpoint querying `sample_taxonomy_classifications` or `chunk_metadata`.
   - Add chart visualizations (e.g., Chart.js or D3.js bar charts for Primary Frame and Causal Attribution) in the web UI.
3. **Implement Voice & Gap Mapping:**
   - Integrate speaker entity recognition (Named Entity Recognition + Source Type heuristics) to distinguish institutional statements from citizen voices.
   - Build cross-tabulation queries comparing institutional news sources with Reddit community reports.
