import os
import sqlite3
import json
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Generator

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

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA temp_store = MEMORY;")
        except Exception:
            pass
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    vector_id INTEGER PRIMARY KEY,
                    chunk_id TEXT NOT NULL,
                    parent_doc_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    total_chunks INTEGER NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    embedding_text TEXT,
                    post_id TEXT,
                    source_url TEXT,
                    source_type TEXT,
                    category_taxonomy TEXT,
                    image_url TEXT,
                    user_rating REAL,
                    char_count INTEGER,
                    word_count INTEGER,
                    relevance_score REAL,
                    quality_score REAL,
                    relevance_decision TEXT,
                    relevance_reason TEXT
                );
            """)
            # Ensure source_url column exists for pre-existing databases
            cursor.execute(f"PRAGMA table_info({self.table_name});")
            existing_cols = [c[1] for c in cursor.fetchall()]
            for col_name, col_type in [
                ("source_url", "TEXT"),
                ("relevance_score", "REAL"),
                ("quality_score", "REAL"),
                ("relevance_decision", "TEXT"),
                ("relevance_reason", "TEXT")
            ]:
                if col_name not in existing_cols:
                    try:
                        cursor.execute(f"ALTER TABLE {self.table_name} ADD COLUMN {col_name} {col_type};")
                    except Exception:
                        pass

            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_chunk_id ON {self.table_name}(chunk_id);")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_parent_doc_id ON {self.table_name}(parent_doc_id);")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_source_type ON {self.table_name}(source_type);")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_decision ON {self.table_name}(relevance_decision);")
            conn.commit()

    def _extract_canonical_source_url(self, meta: Dict[str, Any], parent_doc_id: str) -> Optional[str]:
        raw_source_url = meta.get("source_url")
        post_id = meta.get("post_id")
        if raw_source_url and (str(raw_source_url).startswith("http://") or str(raw_source_url).startswith("https://")):
            import re
            return re.sub(r'\.\d+$', '', str(raw_source_url).strip())
        if post_id and (str(post_id).startswith("http://") or str(post_id).startswith("https://")):
            import re
            return re.sub(r'\.\d+$', '', str(post_id).strip())
        if parent_doc_id and (str(parent_doc_id).startswith("http://") or str(parent_doc_id).startswith("https://")):
            import re
            return re.sub(r'\.\d+$', '', str(parent_doc_id).strip())
        return None

    def populate_from_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        records = []
        for idx, chunk in enumerate(chunks):
            meta = chunk.get("metadata", {})
            parent_doc_id = chunk.get("parent_doc_id", "")
            source_url = self._extract_canonical_source_url(meta, parent_doc_id)
            records.append((
                idx,  # vector_id maps 1-to-1 with FAISS integer ID
                chunk.get("chunk_id"),
                parent_doc_id,
                chunk.get("chunk_index", 0),
                chunk.get("total_chunks", 1),
                chunk.get("title"),
                chunk.get("content", ""),
                chunk.get("embedding_text", ""),
                meta.get("post_id"),
                source_url,
                meta.get("source_type"),
                meta.get("category_taxonomy"),
                meta.get("image_url"),
                meta.get("user_rating"),
                chunk.get("char_count", 0),
                chunk.get("word_count", 0),
                meta.get("context_relevance_score", 1.0),
                meta.get("data_quality_score", 1.0),
                meta.get("relevance_decision", "KEEP"),
                meta.get("relevance_reason", "DEFAULT_KEEP")
            ))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {self.table_name};")
            cursor.executemany(f"""
                INSERT INTO {self.table_name} (
                    vector_id, chunk_id, parent_doc_id, chunk_index, total_chunks,
                    title, content, embedding_text, post_id, source_url, source_type,
                    category_taxonomy, image_url, user_rating, char_count, word_count,
                    relevance_score, quality_score, relevance_decision, relevance_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, records)
            conn.commit()

        return len(records)

    def append_chunks(self, chunks: List[Dict[str, Any]], start_vector_id: int) -> int:
        """
        Appends new chunk metadata records starting at specified start_vector_id,
        preserving FAISS vector synchronization.
        """
        records = []
        for idx, chunk in enumerate(chunks):
            meta = chunk.get("metadata", {})
            parent_doc_id = chunk.get("parent_doc_id", "")
            source_url = self._extract_canonical_source_url(meta, parent_doc_id)
            records.append((
                start_vector_id + idx,
                chunk.get("chunk_id"),
                parent_doc_id,
                chunk.get("chunk_index", 0),
                chunk.get("total_chunks", 1),
                chunk.get("title"),
                chunk.get("content", ""),
                chunk.get("embedding_text", ""),
                meta.get("post_id"),
                source_url,
                meta.get("source_type"),
                meta.get("category_taxonomy"),
                meta.get("image_url"),
                meta.get("user_rating"),
                chunk.get("char_count", 0),
                chunk.get("word_count", 0),
                meta.get("context_relevance_score", 1.0),
                meta.get("data_quality_score", 1.0),
                meta.get("relevance_decision", "KEEP"),
                meta.get("relevance_reason", "DEFAULT_KEEP")
            ))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(f"""
                INSERT OR REPLACE INTO {self.table_name} (
                    vector_id, chunk_id, parent_doc_id, chunk_index, total_chunks,
                    title, content, embedding_text, post_id, source_url, source_type,
                    category_taxonomy, image_url, user_rating, char_count, word_count,
                    relevance_score, quality_score, relevance_decision, relevance_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, records)
            conn.commit()

        return len(records)

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        row_keys = row.keys()
        source_url = None
        if "source_url" in row_keys and row["source_url"]:
            source_url = str(row["source_url"]).strip()
        elif row["post_id"] and (str(row["post_id"]).startswith("http://") or str(row["post_id"]).startswith("https://")):
            import re
            source_url = re.sub(r'\.\d+$', '', str(row["post_id"]).strip())
        elif row["parent_doc_id"] and (str(row["parent_doc_id"]).startswith("http://") or str(row["parent_doc_id"]).startswith("https://")):
            import re
            source_url = re.sub(r'\.\d+$', '', str(row["parent_doc_id"]).strip())

        relevance_score = row["relevance_score"] if "relevance_score" in row_keys and row["relevance_score"] is not None else 1.0
        quality_score = row["quality_score"] if "quality_score" in row_keys and row["quality_score"] is not None else 1.0
        relevance_decision = row["relevance_decision"] if "relevance_decision" in row_keys and row["relevance_decision"] is not None else "KEEP"
        relevance_reason = row["relevance_reason"] if "relevance_reason" in row_keys and row["relevance_reason"] is not None else "DEFAULT_KEEP"

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
            "relevance_score": relevance_score,
            "quality_score": quality_score,
            "relevance_decision": relevance_decision,
            "relevance_reason": relevance_reason,
            "metadata": {
                "post_id": row["post_id"],
                "source_url": source_url,
                "source_type": row["source_type"],
                "category_taxonomy": row["category_taxonomy"],
                "image_url": row["image_url"],
                "user_rating": row["user_rating"],
                "context_relevance_score": relevance_score,
                "data_quality_score": quality_score,
                "relevance_decision": relevance_decision,
                "relevance_reason": relevance_reason
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

    def get_dataset_representative_chunks(self, max_documents: int = 15) -> List[Dict[str, Any]]:
        """
        Retrieves representative chunks (e.g. opening chunks) distributed across diverse
        parent documents and categories in the dataset for dataset-level summarization.
        """
        sampled_rows = []
        seen_parent_ids = set()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Inspect distinct category taxonomies to sample evenly across topics
            cursor.execute(f"""
                SELECT category_taxonomy, COUNT(*) as cnt
                FROM {self.table_name}
                WHERE category_taxonomy IS NOT NULL AND category_taxonomy != ''
                GROUP BY category_taxonomy
                ORDER BY cnt DESC
            """)
            top_cats = [r[0] for r in cursor.fetchall()]

            if len(top_cats) > 1:
                per_cat = max(1, max_documents // len(top_cats))
                for cat in top_cats:
                    cursor.execute(f"""
                        SELECT * FROM {self.table_name}
                        WHERE category_taxonomy = ? AND chunk_index = 0
                        ORDER BY vector_id ASC
                        LIMIT ?
                    """, (cat, per_cat))
                    for row in cursor.fetchall():
                        if row["parent_doc_id"] not in seen_parent_ids:
                            seen_parent_ids.add(row["parent_doc_id"])
                            sampled_rows.append(row)
                        if len(sampled_rows) >= max_documents:
                            break
                    if len(sampled_rows) >= max_documents:
                        break

            # 2. Fill remaining slots with distinct parent documents
            remaining = max_documents - len(sampled_rows)
            if remaining > 0:
                cursor.execute(f"""
                    SELECT * FROM {self.table_name}
                    WHERE chunk_index = 0
                    ORDER BY vector_id ASC
                """)
                for row in cursor.fetchall():
                    if row["parent_doc_id"] not in seen_parent_ids:
                        seen_parent_ids.add(row["parent_doc_id"])
                        sampled_rows.append(row)
                    if len(sampled_rows) >= max_documents:
                        break

            # 3. Fallback if dataset has no chunk_index=0 records
            if not sampled_rows:
                cursor.execute(f"SELECT * FROM {self.table_name} ORDER BY vector_id ASC LIMIT ?", (max_documents,))
                sampled_rows = cursor.fetchall()

        results = []
        for r in sampled_rows:
            d = self._row_to_dict(r)
            d["similarity_score"] = 1.0
            results.append(d)

        return results

    def get_dataset_topic_breakdown(self) -> Dict[str, Any]:
        """
        Returns high-level dataset statistics including document counts, chunk counts,
        distinct categories, and source types.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*), COUNT(DISTINCT parent_doc_id) FROM {self.table_name}")
            row = cursor.fetchone()
            total_chunks = row[0] if row else 0
            total_docs = row[1] if row else 0

            cursor.execute(f"""
                SELECT category_taxonomy, COUNT(*)
                FROM {self.table_name}
                WHERE category_taxonomy IS NOT NULL AND category_taxonomy != ''
                GROUP BY category_taxonomy
                ORDER BY COUNT(*) DESC
            """)
            categories = {r[0]: r[1] for r in cursor.fetchall()}

            cursor.execute(f"""
                SELECT source_type, COUNT(*)
                FROM {self.table_name}
                WHERE source_type IS NOT NULL
                GROUP BY source_type
                ORDER BY COUNT(*) DESC
            """)
            sources = {r[0]: r[1] for r in cursor.fetchall()}

            return {
                "total_chunks": total_chunks,
                "total_documents": total_docs,
                "categories": categories,
                "source_types": sources
            }

