import os
import json
import time
from typing import Tuple, Dict, Any, Optional
from src.metadata_store import MetadataStore

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

class IndexLoader:
    """
    Fast Vector Database Loader Module:
    - Reloads persistent binary FAISS index (faiss_index.bin) in < 0.05 seconds
    - Connects to SQLite metadata database (metadata.sqlite)
    - Reads database manifest (db_manifest.json)
    """

    def __init__(self, db_dir: str):
        self.db_dir = os.path.abspath(db_dir)

    def load_database(self) -> Tuple[Any, MetadataStore, Dict[str, Any], float]:
        start_time = time.time()

        index_path = os.path.join(self.db_dir, "faiss_index.bin")
        sqlite_path = os.path.join(self.db_dir, "metadata.sqlite")
        manifest_path = os.path.join(self.db_dir, "db_manifest.json")

        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS index file not found at: {index_path}")
        if not os.path.exists(sqlite_path):
            raise FileNotFoundError(f"Metadata SQLite database not found at: {sqlite_path}")

        # 1. Read FAISS Index
        if not FAISS_AVAILABLE:
            raise RuntimeError("FAISS library is not installed.")
        
        index = faiss.read_index(index_path)

        # 2. Connect SQLite Metadata Store
        metadata_store = MetadataStore(sqlite_path)

        # 3. Read Manifest
        manifest = {}
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

        elapsed_sec = round(time.time() - start_time, 4)
        return index, metadata_store, manifest, elapsed_sec
