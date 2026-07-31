import os
import sqlite3
import json
from typing import List, Dict, Any, Optional

class MetadataStore:
    """
    SQLite Relational Metadata Store Manager for VARTA Vector Database:
    Maps 0-based integer vector row indices (FAISS vector IDs) to full chunk payloads,
    clean titles, content, and metadata attributes.
    Supports SQL-accelerated indexing, filtering, and 1-to-1 vector synchronization.
    """

    def __init__(self, db_path: str, table_name: str = "chunk_metadata"):
        self.db_path = os.path.abspath(db_path)
        self.table_name = table_name
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    vector_id INTEGER PRIMARY KEY,
                    chunk_id TEXT UNIQUE NOT NULL,
                    parent_doc_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    total_chunks INTEGER NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    embedding_text TEXT,
                    post_id TEXT,
                    source_type TEXT,
                    category_taxonomy TEXT,
                    image_url TEXT,
                    user_rating REAL,
                    char_count INTEGER,
                    word_count INTEGER
                );
            """)
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_chunk_id ON {self.table_name}(chunk_id);")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_parent_doc_id ON {self.table_name}(parent_doc_id);")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_source_type ON {self.table_name}(source_type);")
            conn.commit()

    def populate_from_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        records = []
        for idx, chunk in enumerate(chunks):
            meta = chunk.get("metadata", {})
            records.append((
                idx,  # vector_id maps 1-to-1 with FAISS integer ID
                chunk.get("chunk_id"),
                chunk.get("parent_doc_id"),
                chunk.get("chunk_index", 0),
                chunk.get("total_chunks", 1),
                chunk.get("title"),
                chunk.get("content", ""),
                chunk.get("embedding_text", ""),
                meta.get("post_id"),
                meta.get("source_type"),
                meta.get("category_taxonomy"),
                meta.get("image_url"),
                meta.get("user_rating"),
                chunk.get("char_count", 0),
                chunk.get("word_count", 0)
            ))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {self.table_name};")
            cursor.executemany(f"""
                INSERT INTO {self.table_name} (
                    vector_id, chunk_id, parent_doc_id, chunk_index, total_chunks,
                    title, content, embedding_text, post_id, source_type,
                    category_taxonomy, image_url, user_rating, char_count, word_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, records)
            conn.commit()

        return len(records)

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "vector_id": row["vector_id"],
            "chunk_id": row["chunk_id"],
            "parent_doc_id": row["parent_doc_id"],
            "chunk_index": row["chunk_index"],
            "total_chunks": row["total_chunks"],
            "title": row["title"],
            "content": row["content"],
            "embedding_text": row["embedding_text"],
            "char_count": row["char_count"],
            "word_count": row["word_count"],
            "metadata": {
                "post_id": row["post_id"],
                "source_type": row["source_type"],
                "category_taxonomy": row["category_taxonomy"],
                "image_url": row["image_url"],
                "user_rating": row["user_rating"]
            }
        }

    def get_metadata_by_vector_ids(self, vector_ids: List[int]) -> List[Dict[str, Any]]:
        if not vector_ids:
            return []
        placeholders = ",".join("?" for _ in vector_ids)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {self.table_name} WHERE vector_id IN ({placeholders})", vector_ids)
            rows = cursor.fetchall()
            row_dict = {r["vector_id"]: self._row_to_dict(r) for r in rows}
            # Preserve query ordering
            return [row_dict[vid] for vid in vector_ids if vid in row_dict]

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {self.table_name} WHERE chunk_id = ?", (chunk_id,))
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None

    def get_chunks_by_parent_id(self, parent_doc_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {self.table_name} WHERE parent_doc_id = ? ORDER BY chunk_index ASC", (parent_doc_id,))
            rows = cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_total_records_count(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            return cursor.fetchone()[0]
