# VARTA — AI-Powered Research Assistant

VARTA is an AI-powered research assistant designed to explore, analyze, clean, standardize, chunk, embed, index, query, assemble context, and orchestrate Retrieval-Augmented Generation (RAG) over structured or semi-structured datasets.

The platform is designed to be **dataset-agnostic**, **modular**, **reusable**, and **scalable**, supporting datasets from diverse domains without requiring architectural code changes.

---

## 📁 Project Directory Structure

```
VARTA/
│
├── config/
│   ├── analysis_config.json        # Thresholds & pattern detectors (Sprint 1.1)
│   ├── column_mapping.json         # Column renames, ghost pruning, & payload roles (Sprint 1.2)
│   ├── embedding_config.json      # Chunk size, overlap, provider & embedding model settings (Sprint 2.1)
│   ├── vector_db_config.json       # FAISS vector index & SQLite metadata store settings (Sprint 2.2)
│   ├── retrieval_config.json       # Semantic retrieval settings, top-k defaults & score bounds (Sprint 2.3)
│   └── rag_config.json             # RAG token budget, prompt template & LLM provider settings (Sprint 2.4)
│
├── data/
│   ├── Flood Regional News 25-26 - Sheet1.csv  # Raw input dataset (unmodified)
│   ├── processed/
│   │   └── processed_dataset.csv   # Preprocessed & cleaned dataset (Sprint 1.2)
│   ├── standardized/
│   │   ├── manifest.json           # Dataset-level manifest (Sprint 1.3)
│   │   ├── standardized_dataset.csv  # Standardized CSV dataset (Sprint 1.3)
│   │   └── standardized_documents.json # Standardized JSON documents (Sprint 1.3)
│   ├── embeddings/
│   │   ├── chunks.json             # Structured chunk objects with preserved title & metadata (Sprint 2.1)
│   │   ├── embeddings.npy          # Dense float32 NumPy binary vector matrix (Sprint 2.1)
│   │   └── embedding_statistics.json # Corpus-level embedding statistics artifact (Sprint 2.1)
│   ├── vector_db/
│   │   ├── faiss_index.bin         # Persistent binary FAISS C++ vector index (Sprint 2.2)
│   │   ├── metadata.sqlite         # Relational SQLite metadata store (Sprint 2.2)
│   │   ├── db_manifest.json        # Vector database manifest (Sprint 2.2)
│   │   ├── index_statistics.json   # Vector database statistics artifact (Sprint 2.2)
│   │   └── index_health.json       # Machine-readable vector database health audit (Sprint 2.2)
│   ├── retrieval/
│   │   ├── sample_queries.json     # Multilingual query test suite (Sprint 2.3)
│   │   ├── benchmark_results.json  # Benchmark latency & Cosine score metrics (Sprint 2.3)
│   │   ├── retrieval_statistics.json # Retrieval statistics manifest (Sprint 2.3)
│   │   └── retrieval_health.json   # Machine-readable retrieval health audit (Sprint 2.3)
│   └── rag/
│       ├── sample_prompts.json     # Generated RAG prompt samples (Sprint 2.4)
│       ├── benchmark_results.json  # End-to-end RAG latency & token metrics (Sprint 2.4)
│       ├── rag_statistics.json     # RAG statistics manifest (Sprint 2.4)
│       └── rag_health.json         # Machine-readable RAG pipeline health audit (Sprint 2.4)
│
├── reports/                        # Analysis, Preprocessing, Standardization, Embedding, Vector DB, Retrieval & RAG deliverables
│   ├── dataset_summary.md          # Dataset dimensions, RAM consumption, inventory (Sprint 1.1)
│   ├── schema_analysis.md          # Column classification & reasoning (Sprint 1.1)
│   ├── data_quality_report.md      # Missing values, duplicates, ghost column analysis (Sprint 1.1)
│   ├── data_dictionary.md          # Data Dictionary of all 27 detected columns (Sprint 1.1)
│   ├── preprocessing_strategy.md   # Metadata evaluation & Sprint 1.2 roadmap (Sprint 1.1)
│   ├── preprocessing_report.md     # Narrative preprocessing report (Sprint 1.2)
│   ├── cleaning_statistics.md      # Quantitative cleaning statistics (Sprint 1.2)
│   ├── preprocessing_audit.md      # Preprocessing audit & validation report (Sprint 1.2)
│   ├── document_standardization_report.md # Document standardization specification (Sprint 1.3)
│   ├── document_validation_report.md      # Document schema & quality validation (Sprint 1.3)
│   ├── phase1_validation_report.md # Phase 1 Cross-artifact integrity validation (Sprint 1.4)
│   ├── phase1_quality_assessment.md# Phase 1 Data quality assessment (Sprint 1.4)
│   ├── phase1_readiness_report.md  # Phase 1 Readiness & hand-off sign-off (Sprint 1.4)
│   ├── chunking_strategy_report.md # Document chunking strategy & metrics (Sprint 2.1)
│   ├── chunk_distribution_report.md# Empirical chunk distribution & corpus verification (Sprint 2.1)
│   ├── embedding_pipeline_report.md# Embedding provider & vector matrix metrics (Sprint 2.1)
│   ├── embedding_validation_report.md# Vector QA & referential integrity report (Sprint 2.1)
│   ├── vector_database_report.md   # FAISS + SQLite Vector DB architecture specification (Sprint 2.2)
│   ├── indexing_validation_report.md# Index coverage, synchronization & reload QA report (Sprint 2.2)
│   ├── index_statistics_report.md  # Vector database index metrics & storage report (Sprint 2.2)
│   ├── retrieval_report.md         # Semantic retrieval architecture specification (Sprint 2.3)
│   ├── retrieval_validation_report.md# Retrieval QA & edge case validation report (Sprint 2.3)
│   ├── retrieval_benchmark_report.md # Multilingual benchmark performance & score report (Sprint 2.3)
│   ├── rag_pipeline_report.md      # RAG orchestration architecture specification (Sprint 2.4)
│   ├── rag_validation_report.md    # Token budget, prompt & citation validation report (Sprint 2.4)
│   └── rag_benchmark_report.md     # End-to-end RAG latency & token utilization report (Sprint 2.4)
│
├── scripts/
│   ├── dataset_analysis.py               # CLI entrypoint for dynamic discovery & analysis (Sprint 1.1)
│   ├── run_preprocessing.py              # CLI entrypoint for data cleaning pipeline (Sprint 1.2)
│   ├── run_document_standardization.py   # CLI entrypoint for document standardization (Sprint 1.3)
│   ├── run_phase1_validation.py          # CLI entrypoint for Phase 1 QA & validation (Sprint 1.4)
│   ├── run_chunking.py                  # CLI entrypoint for document chunking (Sprint 2.1)
│   ├── run_embedding.py                 # CLI entrypoint for embedding generation (Sprint 2.1)
│   ├── run_embedding_validation.py      # CLI entrypoint for vector validation (Sprint 2.1)
│   ├── build_vector_database.py         # CLI entrypoint for vector DB construction (Sprint 2.2)
│   ├── validate_vector_database.py      # CLI entrypoint for vector DB QA validation (Sprint 2.2)
│   ├── inspect_vector_database.py       # CLI entrypoint for vector DB inspection (Sprint 2.2)
│   ├── run_semantic_retrieval.py        # CLI entrypoint for executing semantic queries (Sprint 2.3)
│   ├── validate_retrieval.py            # CLI entrypoint for retrieval QA validation (Sprint 2.3)
│   ├── benchmark_retrieval.py           # CLI entrypoint for retrieval benchmarking (Sprint 2.3)
│   ├── test_openai_connection.py        # OpenAI API connectivity & Responses API test script
│   ├── test_gemini_connection.py        # Legacy Gemini API connectivity test script
│   ├── run_rag_pipeline.py              # CLI entrypoint for end-to-end RAG execution (Sprint 2.4)
│   ├── validate_rag.py                  # CLI entrypoint for RAG QA & token budget validation (Sprint 2.4)
│   └── benchmark_rag.py                 # CLI entrypoint for RAG performance benchmarking (Sprint 2.4)
│
├── src/                            # Modular core python packages
│   ├── __init__.py
│   ├── dataset_loader.py           # Loads CSV & extracts RAM/file metadata
│   ├── schema_classifier.py        # Dynamic column classification
│   ├── quality_assessor.py         # Data quality assessment
│   ├── text_analyzer.py            # Text profiling & noise detection
│   ├── report_generator.py         # Markdown report generator
│   ├── data_cleaner.py             # Column pruning, renames, invalid payload filtering
│   ├── text_normalizer.py          # Whitespace, linebreak, control char & Unicode cleaning
│   ├── metadata_processor.py       # Metadata field standardization
│   ├── duplicate_handler.py        # Multi-level deduplication (full row, ID, content hash)
│   ├── preprocessing_pipeline.py  # Preprocessing pipeline orchestrator & report exporter
│   ├── metadata_formatter.py       # Standardized metadata dictionary formatter (Sprint 1.3)
│   ├── document_builder.py         # Constructs dataset-agnostic document models (Sprint 1.3)
│   ├── document_serializer.py      # Serializes documents to JSON and CSV (Sprint 1.3)
│   ├── document_validator.py       # Validates schema, doc_id uniqueness & JSON integrity (Sprint 1.3)
│   ├── phase1_validator.py         # Phase 1 Quality Assurance & referential validator (Sprint 1.4)
│   ├── chunk_builder.py            # Recursive character chunking & header injection (Sprint 2.1)
│   ├── embedding_providers.py      # Provider-agnostic embedding interface (Sprint 2.1)
│   ├── embedding_generator.py      # Batch vector inference engine (Sprint 2.1)
│   ├── embedding_storage.py        # Exporter for embeddings.npy, chunks.json & statistics (Sprint 2.1)
│   ├── embedding_validator.py      # Vector coverage, dimension & referential QA validator (Sprint 2.1)
│   ├── metadata_store.py           # SQLite relational metadata store manager (Sprint 2.2)
│   ├── index_builder.py            # FAISS C++ vector index builder (Sprint 2.2)
│   ├── index_loader.py             # Fast persistent index loader module (Sprint 2.2)
│   ├── vector_database.py          # Main VectorDatabase facade & search API interface (Sprint 2.2)
│   ├── vector_validator.py         # Vector database QA & reload integrity validator (Sprint 2.2)
│   ├── query_processor.py          # Multilingual query preprocessor & validator (Sprint 2.3)
│   ├── retrieval_engine.py         # Ranking, score normalizer & deduplication engine (Sprint 2.3)
│   ├── semantic_retriever.py       # Backend-Agnostic SemanticRetriever facade API (Sprint 2.3)
│   ├── retrieval_validator.py      # Retrieval QA & edge-case validator (Sprint 2.3)
│   ├── retrieval_benchmark.py      # Latency & score benchmarking suite (Sprint 2.3)
│   ├── token_counters.py           # Pluggable BaseTokenCounter interface (Heuristic & Tiktoken) (Sprint 2.4)
│   ├── context_assembler.py        # Merges overlapping chunks & preserves metadata (Sprint 2.4)
│   ├── context_ranker.py           # Priority scoring & parent doc diversity ranker (Sprint 2.4)
│   ├── token_budget_manager.py     # Enforces max context token budget (Sprint 2.4)
│   ├── prompt_builder.py           # Formats system prompt & citation-tagged context blocks (Sprint 2.4)
│   ├── llm_adapter.py              # Decoupled BaseLLMAdapter interface (OpenAI, Gemini, Mock) (Sprint 2.4)
│   ├── rag_orchestrator.py         # RAGOrchestrator pipeline coordinator & short-circuiter (Sprint 2.4)
│   ├── rag_validator.py            # QA validator for RAG token budgets & citations (Sprint 2.4)
│   └── rag_benchmark.py            # End-to-end RAG latency & token utilization benchmarker (Sprint 2.4)
│
├── .env.example                    # Template for environment configuration
└── README.md                       # Project documentation
```

---

## ⚙️ Environment & LLM Configuration

VARTA uses a decoupled LLM Integration Layer supporting OpenAI, Google Gemini, and Mock testing adapters. Selection is configured dynamically via `.env`:

```env
# OpenAI API Configuration (Primary)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5
LLM_PROVIDER=openai
```

To switch providers dynamically without changing any application code:
- **OpenAI**: Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY=<key>`
- **Gemini**: Set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY=<key>`
- **Mock**: Set `LLM_PROVIDER=mock` (no API key required)

---

## 🚀 End-to-End Pipeline Execution Guide

To reproduce VARTA Phase 1 and Phase 2 (Sprints 2.1, 2.2, 2.3, 2.4) from raw data to end-to-end RAG:

```bash
# Step 0: Test OpenAI API Connectivity & Responses API
python scripts/test_openai_connection.py

# Step 1: Dataset Discovery & Analysis (Sprint 1.1)
python scripts/dataset_analysis.py

# Step 2: Data Cleaning & Preprocessing (Sprint 1.2)
python scripts/run_preprocessing.py

# Step 3: Document Standardization & Manifest (Sprint 1.3)
python scripts/run_document_standardization.py

# Step 4: Phase 1 Quality Assurance & Validation (Sprint 1.4)
python scripts/run_phase1_validation.py

# Step 5: Document Chunking (Sprint 2.1)
python scripts/run_chunking.py

# Step 6: Embedding Generation (Sprint 2.1)
python scripts/run_embedding.py

# Step 7: Embedding QA & Validation (Sprint 2.1)
python scripts/run_embedding_validation.py

# Step 8: Vector Database Construction (Sprint 2.2)
python scripts/build_vector_database.py

# Step 9: Vector Database QA Validation (Sprint 2.2)
python scripts/validate_vector_database.py

# Step 10: Vector Database Inspection (Sprint 2.2)
python scripts/inspect_vector_database.py

# Step 11: Semantic Retrieval QA Validation (Sprint 2.3)
python scripts/validate_retrieval.py

# Step 12: Multilingual Latency & Score Benchmarking (Sprint 2.3)
python scripts/benchmark_retrieval.py

# Step 13: Execute Semantic Retrieval Query CLI (Sprint 2.3)
python scripts/run_semantic_retrieval.py --query "गोरखपुर में राप्ती नदी का जलस्तर तटबंध" --top-k 3

# Step 14: RAG Orchestration QA & Token Budget Validation (Sprint 2.4)
python scripts/validate_rag.py

# Step 15: End-to-End RAG Latency & Token Utilization Benchmarking (Sprint 2.4)
python scripts/benchmark_rag.py

# Step 16: Execute End-to-End RAG Pipeline CLI (Sprint 2.4)
python scripts/run_rag_pipeline.py --query "गोरखपुर में राप्ती नदी का जलस्तर तटबंध की स्थिति" --top-k 5
```

---

## 📋 Phase 1 & Phase 2 Milestone Summary

| Phase & Sprint | Objective | Primary Deliverables | Status |
| :--- | :--- | :--- | :-: |
| **Sprint 1.1** | Dataset Discovery & Analysis | `dataset_summary.md`, `schema_analysis.md`, `data_quality_report.md`, `data_dictionary.md` | 🟢 COMPLETE |
| **Sprint 1.2** | Data Cleaning Pipeline | `data/processed/processed_dataset.csv`, `preprocessing_report.md`, `cleaning_statistics.md` | 🟢 COMPLETE |
| **Sprint 1.3** | Document Standardization | `data/standardized/standardized_documents.json`, `standardized_dataset.csv`, `manifest.json` | 🟢 COMPLETE |
| **Sprint 1.4** | Phase 1 Validation & QA | `reports/phase1_validation_report.md`, `phase1_quality_assessment.md`, `phase1_readiness_report.md` | 🟢 COMPLETE |
| **Sprint 2.1** | Embedding Pipeline | `data/embeddings/chunks.json`, `data/embeddings/embeddings.npy`, `embedding_statistics.json` | 🟢 COMPLETE |
| **Sprint 2.2** | Vector Database Indexing | `data/vector_db/faiss_index.bin`, `metadata.sqlite`, `db_manifest.json`, `index_health.json` | 🟢 COMPLETE |
| **Sprint 2.3** | Semantic Retrieval | `data/retrieval/retrieval_health.json`, `benchmark_results.json`, `retrieval_benchmark_report.md` | 🟢 COMPLETE |
| **Sprint 2.4** | Context Assembly & RAG | `data/rag/rag_health.json`, `benchmark_results.json`, `rag_benchmark_report.md` | 🟢 COMPLETE |

---

## 🛑 Scope Boundary Notice

*Phase 2 (Knowledge Layer) is 100% COMPLETE and APPROVED. Stop condition reached. Conversation memory, multi-turn chat history, agent workflows, tool calling, autonomous planning, web search, and multi-agent systems belong to Phase 3 (Agentic Layer).*
