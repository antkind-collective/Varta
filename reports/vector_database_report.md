# VARTA — Vector Database Architecture Report (Sprint 2.2)

## 1. Executive Summary
- **Primary Vector Index Engine**: `FAISS (IndexFlatIP)`
- **Metadata Storage Engine**: `SQLite Relational Database`
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Vector Dimension**: `384 dims`
- **Indexed Dense Vector Count**: `39,172`
- **Indexed Metadata Records**: `39,172`
- **Binary Vector Index Output**: `C:\Users\binda\OneDrive\Desktop\Varta\data\vector_db\faiss_index.bin` (`57.38 MB`)
- **Metadata Database Output**: `C:\Users\binda\OneDrive\Desktop\Varta\data\vector_db\metadata.sqlite` (`114.6 MB`)
- **Database Manifest Output**: `C:\Users\binda\OneDrive\Desktop\Varta\data\vector_db\db_manifest.json`

## 2. Technical Architecture & Design Rationale
1. **Configurable Similarity Search**: Configured index type `IndexFlatIP` on float32 vector embeddings.
2. **1-to-1 Vector-to-Metadata Synchronization**: FAISS 0-based integer vector row IDs `0..39171` correspond strictly 1-to-1 with SQLite primary keys `0..39171`.
3. **Zero-Copy Ingestion**: Built directly from contiguous NumPy memory buffers (`data/embeddings/embeddings.npy`).
4. **Fast Persistent Reload**: Reloads persistent vector database into memory in `< 0.05 seconds` without re-generating embeddings.