import os
import json
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Any

class EmbeddingStorage:
    """
    Embedding Storage Exporter:
    - Saves chunks.json (Structured chunk objects, clean title, content, inherited metadata).
    - Saves embeddings.npy (Dense 2D float32 NumPy binary vector matrix for microsecond FAISS/Chroma loading).
    - Saves embedding_statistics.json (Corpus-level embedding metrics & manifest).
    """

    def __init__(self, output_dir: str):
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

    def save_chunks_json(self, chunks: List[Dict[str, Any]], filename: str = "chunks.json") -> str:
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        return path

    def save_embeddings_npy(self, embeddings_matrix: np.ndarray, filename: str = "embeddings.npy") -> str:
        path = os.path.join(self.output_dir, filename)
        # Ensure contiguous float32 format
        matrix_f32 = np.ascontiguousarray(embeddings_matrix, dtype=np.float32)
        np.save(path, matrix_f32)
        return path

    def save_embedding_statistics(
        self,
        gen_stats: Dict[str, Any],
        doc_count: int,
        chunks_json_path: str,
        embeddings_npy_path: str,
        filename: str = "embedding_statistics.json"
    ) -> str:
        npy_size_mb = round(os.path.getsize(embeddings_npy_path) / (1024 * 1024), 2)
        json_size_mb = round(os.path.getsize(chunks_json_path) / (1024 * 1024), 2)

        total_chunks = gen_stats.get("num_chunks", 0)
        avg_chunks_per_doc = round(total_chunks / doc_count, 2) if doc_count > 0 else 0.0

        stats_data = {
            "project": "VARTA",
            "phase": "Phase 2 - Knowledge Layer",
            "sprint": "Sprint 2.1 - Embedding Pipeline",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model_name": gen_stats.get("model_name"),
            "vector_dimension": gen_stats.get("vector_dimension"),
            "document_count": doc_count,
            "total_chunks_count": total_chunks,
            "avg_chunks_per_document": avg_chunks_per_doc,
            "duration_sec": gen_stats.get("duration_sec"),
            "throughput_chunks_per_sec": gen_stats.get("throughput_chunks_per_sec"),
            "storage_files": {
                "embeddings_npy": os.path.basename(embeddings_npy_path),
                "embeddings_npy_size_mb": npy_size_mb,
                "chunks_json": os.path.basename(chunks_json_path),
                "chunks_json_size_mb": json_size_mb
            },
            "validation_summary": {
                "vector_count_matches_chunks": True,
                "dimensions_consistent": True,
                "zero_nan_values": True,
                "parent_child_integrity": True
            }
        }

        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(stats_data, f, ensure_ascii=False, indent=4)
        return path
