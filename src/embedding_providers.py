import numpy as np
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseEmbeddingProvider(ABC):
    """
    Abstract base class for provider-agnostic embedding models.
    Supports swapping local models (SentenceTransformers), API models (Gemini/OpenAI),
    or lightweight fallback models without modifying pipeline logic.
    """

    @abstractmethod
    def encode(self, texts: List[str]) -> np.ndarray:
        """Encodes a list of text strings into a 2D float32 NumPy array of shape (N, dim)."""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray:
        """Encodes a single query string into a 2D float32 NumPy array of shape (1, dim)."""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Returns the embedding vector dimension."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Returns the name of the active embedding model."""
        pass


from collections import OrderedDict
import threading

class SentenceTransformersProvider(BaseEmbeddingProvider):
    """
    SentenceTransformers local model provider:
    Supports sentence-transformers/all-MiniLM-L6-v2, intfloat/multilingual-e5-base, etc.
    Includes singleton model caching and bounded LRU query embedding cache.
    """

    _MODEL_CACHE: Dict[tuple, Any] = {}
    _QUERY_CACHE: OrderedDict = OrderedDict()
    _CACHE_LOCK = threading.Lock()
    _MAX_CACHE_SIZE = 512

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", device: str = "cpu", normalize_embeddings: bool = True):
        self.model_name = model_name
        self.device = device
        self.normalize_embeddings = normalize_embeddings
        
        cache_key = (model_name, device)
        with self._CACHE_LOCK:
            if cache_key in self._MODEL_CACHE:
                self.model, self.dimension = self._MODEL_CACHE[cache_key]
            else:
                try:
                    from sentence_transformers import SentenceTransformer
                    model = SentenceTransformer(model_name, device=device)
                    dim = model.get_embedding_dimension() if hasattr(model, "get_embedding_dimension") else model.get_sentence_embedding_dimension()
                except Exception as e:
                    print(f"[Warning] Failed to load '{model_name}': {e}. Falling back to 'sentence-transformers/all-MiniLM-L6-v2'.")
                    from sentence_transformers import SentenceTransformer
                    self.model_name = "sentence-transformers/all-MiniLM-L6-v2"
                    model = SentenceTransformer(self.model_name, device=device)
                    dim = model.get_embedding_dimension() if hasattr(model, "get_embedding_dimension") else model.get_sentence_embedding_dimension()

                self.model = model
                self.dimension = dim
                self._MODEL_CACHE[cache_key] = (self.model, self.dimension)

    def encode(self, texts: List[str]) -> np.ndarray:
        # Prepend 'passage: ' if using e5 models if not present
        if "e5" in self.model_name.lower():
            processed_texts = [f"passage: {t}" if not t.startswith("passage:") else t for t in texts]
        else:
            processed_texts = texts

        embeddings = self.model.encode(
            processed_texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=self.normalize_embeddings
        )
        return embeddings.astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        if "e5" in self.model_name.lower():
            qtext = f"query: {text}" if not text.startswith("query:") else text
        else:
            qtext = text

        cache_key = (self.model_name, self.device, self.normalize_embeddings, qtext)
        with self._CACHE_LOCK:
            if cache_key in self._QUERY_CACHE:
                self._QUERY_CACHE.move_to_end(cache_key)
                return self._QUERY_CACHE[cache_key].copy()

        # Compute embedding
        res = self.encode([qtext])

        with self._CACHE_LOCK:
            self._QUERY_CACHE[cache_key] = res
            if len(self._QUERY_CACHE) > self._MAX_CACHE_SIZE:
                self._QUERY_CACHE.popitem(last=False)

        return res.copy()

    def get_dimension(self) -> int:
        return int(self.dimension)

    def get_model_name(self) -> str:
        return self.model_name


class TFIDFMockProvider(BaseEmbeddingProvider):
    """
    Lightweight fallback provider using SVD/TF-IDF for fast unit testing or fallback.
    Produces 384-dimensional normalized dense float32 vectors.
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.model_name = "mock-tfidf-svd-384d"

    def encode(self, texts: List[str]) -> np.ndarray:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import TruncatedSVD

        vec = TfidfVectorizer(max_features=self.dimension * 2, stop_words=None)
        X = vec.fit_transform(texts)
        svd = TruncatedSVD(n_components=min(self.dimension, X.shape[1] - 1 if X.shape[1] > 1 else 1))
        X_dense = svd.fit_transform(X)
        
        # Pad or truncate to exact target dimension
        if X_dense.shape[1] < self.dimension:
            pad = np.zeros((len(texts), self.dimension - X_dense.shape[1]), dtype=np.float32)
            X_dense = np.hstack([X_dense, pad])
        elif X_dense.shape[1] > self.dimension:
            X_dense = X_dense[:, :self.dimension]

        # L2 normalize
        norms = np.linalg.norm(X_dense, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        X_norm = (X_dense / norms).astype(np.float32)
        return X_norm

    def embed_query(self, text: str) -> np.ndarray:
        return self.encode([text])

    def get_dimension(self) -> int:
        return self.dimension

    def get_model_name(self) -> str:
        return self.model_name


def get_embedding_provider(config: Dict[str, Any]) -> BaseEmbeddingProvider:
    emb_cfg = config.get("embedding", {})
    provider_type = emb_cfg.get("provider", "sentence-transformers").lower()
    model_name = emb_cfg.get("model_name", "sentence-transformers/all-MiniLM-L6-v2")
    device = emb_cfg.get("device", "cpu")
    normalize = emb_cfg.get("normalize_embeddings", True)

    if provider_type == "sentence-transformers":
        return SentenceTransformersProvider(model_name=model_name, device=device, normalize_embeddings=normalize)
    elif provider_type == "mock":
        return TFIDFMockProvider(dimension=384)
    else:
        raise ValueError(f"Unsupported embedding provider: {provider_type}")
