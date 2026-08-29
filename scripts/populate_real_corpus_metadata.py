import sys
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.metadata_store import MetadataStore

def populate_real_metadata():
    chunks_path = PROJECT_ROOT / "data" / "embeddings" / "chunks.json"
    sqlite_path = PROJECT_ROOT / "data" / "vector_db" / "metadata.sqlite"

    print(f"Loading real chunks from {chunks_path}...")
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Loaded {len(chunks):,} real chunks. Populating SQLite metadata store: {sqlite_path}...")
    store = MetadataStore(db_path=str(sqlite_path))
    inserted = store.populate_from_chunks(chunks)
    print(f"Successfully populated {inserted:,} real records into metadata.sqlite!")

if __name__ == "__main__":
    populate_real_metadata()
