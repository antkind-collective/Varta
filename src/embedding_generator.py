import time
import numpy as np
from typing import List, Dict, Any, Tuple
from src.embedding_providers import BaseEmbeddingProvider

class EmbeddingGenerator:
    """
    Batch Inference Engine for Embedding Generation:
    - Processes chunks in configurable batch sizes (e.g., 64 or 128).
    - Extracts embedding_text (title + content context) for vector encoding.
    - Assembles final C-contiguous float32 NumPy matrix (num_chunks, vector_dim).
    - Measures encoding duration and throughput (chunks / second).
    """

    def __init__(self, provider: BaseEmbeddingProvider, batch_size: int = 64):
        self.provider = provider
        self.batch_size = batch_size

    def generate_embeddings(self, chunks: List[Dict[str, Any]]) -> Tuple[np.ndarray, Dict[str, Any]]:
        total_chunks = len(chunks)
        if total_chunks == 0:
            dim = self.provider.get_dimension()
            return np.empty((0, dim), dtype=np.float32), {"num_chunks": 0, "duration_sec": 0.0}

        print(f"      [Embedding Engine] Provider: {self.provider.get_model_name()}")
        print(f"      [Embedding Engine] Target Batches: {(total_chunks + self.batch_size - 1) // self.batch_size} (Batch Size: {self.batch_size})")

        start_time = time.time()
        embedding_batches = []

        for i in range(0, total_chunks, self.batch_size):
            batch_chunks = chunks[i : i + self.batch_size]
            batch_texts = [c.get("embedding_text", c.get("content", "")) for c in batch_chunks]

            batch_vecs = self.provider.encode(batch_texts)
            embedding_batches.append(batch_vecs)

            if (i // self.batch_size + 1) % 50 == 0 or (i + len(batch_chunks)) == total_chunks:
                processed = i + len(batch_chunks)
                pct = round((processed / total_chunks) * 100, 1)
                elapsed = time.time() - start_time
                rate = round(processed / elapsed, 1) if elapsed > 0 else 0
                print(f"        Processed {processed:,}/{total_chunks:,} chunks ({pct}%) - {rate} chunks/sec")

        # Stack into single contiguous 2D float32 matrix
        embeddings_matrix = np.vstack(embedding_batches).astype(np.float32)
        total_duration = time.time() - start_time

        gen_stats = {
            "model_name": self.provider.get_model_name(),
            "vector_dimension": self.provider.get_dimension(),
            "num_chunks": total_chunks,
            "duration_sec": round(total_duration, 2),
            "throughput_chunks_per_sec": round(total_chunks / total_duration, 1) if total_duration > 0 else 0
        }

        return embeddings_matrix, gen_stats
