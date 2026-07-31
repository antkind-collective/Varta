import os
import numpy as np
from typing import Tuple, Dict, Any, Optional

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

class FAISSIndexBuilder:
    """
    Configurable FAISS C++ Vector Similarity Index Builder:
    Supports dynamic index construction based on configuration string:
    - IndexFlatIP (Exact Inner Product / Cosine Similarity)
    - IndexFlatL2 (Exact L2 Distance)
    - IndexIVFFlat (Inverted File Index with Voronoi cells)
    - IndexHNSWFlat (Hierarchical Navigable Small World Graph)
    """

    def __init__(self, index_type: str = "IndexFlatIP", normalize_vectors: bool = True, nlist: int = 100):
        self.index_type = index_type
        self.normalize_vectors = normalize_vectors
        self.nlist = nlist

    def build_and_save_index(self, embeddings_matrix: np.ndarray, output_path: str) -> Dict[str, Any]:
        if not FAISS_AVAILABLE:
            raise RuntimeError("FAISS library is not installed in current Python environment.")

        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        num_vectors, dimension = embeddings_matrix.shape

        # Ensure writeable float32 C-contiguous array
        matrix_f32 = np.array(embeddings_matrix, copy=True, dtype=np.float32)

        # Apply L2 normalization if required
        if self.normalize_vectors and "L2" not in self.index_type:
            faiss.normalize_L2(matrix_f32)

        # Dynamically build FAISS index based on configuration
        idx_type_lower = self.index_type.lower()

        if idx_type_lower == "indexflatip":
            index = faiss.IndexFlatIP(dimension)
            index.add(matrix_f32)

        elif idx_type_lower == "indexflatl2":
            index = faiss.IndexFlatL2(dimension)
            index.add(matrix_f32)

        elif idx_type_lower == "indexivfflat":
            quantizer = faiss.IndexFlatIP(dimension)
            nlist_val = min(self.nlist, max(1, num_vectors // 10))
            index = faiss.IndexIVFFlat(quantizer, dimension, nlist_val, faiss.METRIC_INNER_PRODUCT)
            index.train(matrix_f32)
            index.add(matrix_f32)

        elif idx_type_lower == "indexhnswflat":
            index = faiss.IndexHNSWFlat(dimension, 32, faiss.METRIC_INNER_PRODUCT)
            index.add(matrix_f32)

        else:
            # Fallback to IndexFlatIP
            print(f"[Warning] Unknown index_type '{self.index_type}'. Falling back to 'IndexFlatIP'.")
            index = faiss.IndexFlatIP(dimension)
            index.add(matrix_f32)

        # Serialize binary FAISS index file
        faiss.write_index(index, output_path)

        return {
            "index_type": self.index_type,
            "total_vectors": index.ntotal,
            "vector_dimension": index.d,
            "normalize_vectors": self.normalize_vectors,
            "output_path": output_path,
            "file_size_mb": round(os.path.getsize(output_path) / (1024 * 1024), 2)
        }
