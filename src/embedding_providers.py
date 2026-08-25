import os
import time
import threading
from collections import OrderedDict
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

    def encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        # Prepend 'passage: ' if using e5 models if not present
        if "e5" in self.model_name.lower():
            processed_texts = [f"passage: {t}" if not t.startswith("passage:") else t for t in texts]
        else:
            processed_texts = texts

        embeddings = self.model.encode(
            processed_texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=self.normalize_embeddings,
            batch_size=batch_size
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


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    OpenAI API Embedding Provider:
    Uses OpenAI API (text-embedding-3-small) to generate high-performance embeddings
    without consuming process RAM for local PyTorch model inference.
    """

    _CLIENT_CACHE = None
    _CLIENT_LOCK = threading.Lock()
    _QUERY_CACHE: OrderedDict = OrderedDict()
    _CACHE_LOCK = threading.Lock()
    _MAX_CACHE_SIZE = 512

    def __init__(self, model_name: str = "text-embedding-3-small", dimension: int = 384, api_key: Optional[str] = None):
        self.model_name = model_name
        self.dimension = dimension
        self.retry_count = 0

        with self._CLIENT_LOCK:
            if OpenAIEmbeddingProvider._CLIENT_CACHE is None:
                key = api_key or os.getenv("OPENAI_API_KEY")
                if not key:
                    try:
                        from dotenv import load_dotenv
                        load_dotenv()
                        key = os.getenv("OPENAI_API_KEY")
                    except Exception:
                        pass

                if not key or not key.strip():
                    raise ValueError("OPENAI_API_KEY environment variable is not set in environment or .env file.")

                from openai import OpenAI
                OpenAIEmbeddingProvider._CLIENT_CACHE = OpenAI(api_key=key.strip())

        self.client = OpenAIEmbeddingProvider._CLIENT_CACHE

    def encode(self, texts: List[str], batch_size: int = 200, max_retries: int = 5) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        all_embeddings = []
        total_texts = len(texts)
        api_batch_size = max(batch_size, 200)

        for i in range(0, total_texts, api_batch_size):
            batch_texts = texts[i : i + api_batch_size]
            clean_batch = [str(t).replace("\n", " ").strip() if t is not None else "" for t in batch_texts]
            clean_batch = [t if t else "empty" for t in clean_batch]

            attempt = 0
            backoff = 1.0
            response = None

            while attempt < max_retries:
                try:
                    create_kwargs = {
                        "input": clean_batch,
                        "model": self.model_name
                    }
                    if "text-embedding-3" in self.model_name and self.dimension:
                        create_kwargs["dimensions"] = int(self.dimension)

                    response = self.client.embeddings.create(**create_kwargs)
                    break
                except Exception as e:
                    attempt += 1
                    self.retry_count += 1
                    if attempt >= max_retries:
                        raise RuntimeError(f"OpenAI Embeddings API failed after {max_retries} attempts: {e}")
                    time.sleep(backoff)
                    backoff *= 2.0

            sorted_data = sorted(response.data, key=lambda x: x.index)
            batch_vecs = [item.embedding for item in sorted_data]
            all_embeddings.extend(batch_vecs)

        arr = np.array(all_embeddings, dtype=np.float32)

        # L2 normalize
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        arr_norm = (arr / norms).astype(np.float32)
        return arr_norm

    def embed_query(self, text: str) -> np.ndarray:
        cache_key = (self.model_name, text)
        with self._CACHE_LOCK:
            if cache_key in self._QUERY_CACHE:
                self._QUERY_CACHE.move_to_end(cache_key)
                return self._QUERY_CACHE[cache_key].copy()

        res = self.encode([text])

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
    Produces 1536-dimensional normalized dense float32 vectors.
    """

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self.model_name = "mock-tfidf-svd-1536d"

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


def get_embedding_provider(config: Optional[Dict[str, Any]] = None) -> BaseEmbeddingProvider:
    if config is None:
        config = {}
        from pathlib import Path
        import json
        cfg_file = Path("config/embedding_config.json")
        if cfg_file.exists():
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                pass

    emb_cfg = config.get("embedding", {}) if config else {}
    provider_type = emb_cfg.get("provider", "openai").lower()
    model_name = emb_cfg.get("model_name", "text-embedding-3-small")
    dimension = emb_cfg.get("dimension", 384)

    if provider_type in ("openai", "openai-embeddings"):
        return OpenAIEmbeddingProvider(model_name=model_name, dimension=dimension)
    elif provider_type == "sentence-transformers":
        device = emb_cfg.get("device", "cpu")
        normalize = emb_cfg.get("normalize_embeddings", True)
        return SentenceTransformersProvider(model_name=model_name, device=device, normalize_embeddings=normalize)
    elif provider_type == "mock":
        return TFIDFMockProvider(dimension=dimension)
    else:
        return OpenAIEmbeddingProvider(model_name=model_name, dimension=dimension)
