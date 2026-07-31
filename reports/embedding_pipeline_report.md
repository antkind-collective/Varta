# VARTA — Embedding Pipeline Report (Sprint 2.1)

## 1. Executive Summary
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Vector Dimension**: `384 dims`
- **Total Vector Embeddings**: `39,172`
- **Embedding Generation Time**: `812.51 seconds`
- **Throughput Rate**: `48.2 chunks/sec`
- **Binary Vector Output**: `C:\Users\binda\OneDrive\Desktop\Varta\data\embeddings\embeddings.npy`
- **Corpus Statistics Output**: `C:\Users\binda\OneDrive\Desktop\Varta\data\embeddings\embedding_statistics.json`

## 2. Technical Architecture Highlights
1. **Provider-Agnostic Engine**: Supports swapping local SentenceTransformers models, cloud APIs, or fallback models via `config/embedding_config.json`.
2. **FAISS & ChromaDB Optimized Matrix Storage**: Dense embeddings stored as a 2D float32 C-contiguous NumPy binary matrix (`embeddings.npy`) for microsecond zero-copy loading.
3. **Contextual Title Header Integration**: Embeddings generated on title-injected payload text (`"Title: {title}\nContent: {content}"`).
4. **Corpus-Level Statistics**: Metadata manifest exported to `embedding_statistics.json`.