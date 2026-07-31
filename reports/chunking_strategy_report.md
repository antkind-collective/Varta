# VARTA — Document Chunking Strategy Report (Sprint 2.1)

## 1. Executive Summary
- **Input Corpus Documents**: `33,975`
- **Generated Chunks**: `39,172`
- **Average Chunks per Document**: `1.15`
- **Target Chunk Size**: `1200 characters` (~250-300 words)
- **Chunk Overlap**: `200 characters` (~40-50 words)
- **Output File**: `C:\Users\binda\OneDrive\Desktop\Varta\data\embeddings\chunks.json`

## 2. Chunking Strategy Specification
1. **Hierarchical Recursive Splitting**: Text was split using separators `["\n\n", "\n", "। ", ". ", " ", ""]` to preserve natural paragraph and sentence boundaries.
2. **Title Field Preservation**: Every chunk retains `title` as a standalone metadata attribute alongside `content`.
3. **Embedding Context Injection**: Computed `embedding_text` (`"Title: {title}\nContent: {content}"`) specifically for the embedding vector model.
4. **Parent-Child Linkage**: Every chunk inherits parent metadata (`post_id`, `source_type`, `category_taxonomy`, `image_url`, `user_rating`) and references `parent_doc_id`.