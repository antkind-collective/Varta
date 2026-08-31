import os
import gzip
import shutil
import sqlite3
import faiss
import numpy as np
from pathlib import Path

def main():
    db_path = Path("data/vector_db/metadata.sqlite")
    faiss_path = Path("data/vector_db/faiss_index.bin")
    seed_gz_path = Path("src/seed_metadata.sqlite.gz")
    data_gz_path = Path("data/vector_db/metadata.sqlite.gz")
    raw_news_csv = Path("data/Flood Regional News 25-26 - Sheet1.csv")
    processed_csv = Path("data/processed/processed_dataset.csv")

    print("================================================================================")
    print("STARTING PERMANENT REMOVAL OF MASTER_NEWS_CORPUS")
    print("================================================================================")

    # 1. Inspect existing state
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT source_dataset, COUNT(*) FROM chunk_metadata GROUP BY source_dataset")
    initial_counts = dict(c.fetchall())
    print("Initial SQLite row counts:", initial_counts)
    assert initial_counts.get("master_news_corpus") == 39164, f"Unexpected news count: {initial_counts}"
    assert initial_counts.get("sagar_reddit_dataset") == 10210, f"Unexpected reddit count: {initial_counts}"

    # Fetch Reddit rows in vector_id order
    c.execute("""
        SELECT * FROM chunk_metadata 
        WHERE source_dataset = 'sagar_reddit_dataset' 
        ORDER BY vector_id ASC
    """)
    col_names = [description[0] for description in c.description]
    reddit_rows = c.fetchall()
    conn.close()

    print(f"Fetched {len(reddit_rows)} Reddit rows from SQLite.")

    # 2. Re-slice FAISS index
    idx = faiss.read_index(str(faiss_path))
    print(f"Initial FAISS index: {idx.ntotal} vectors, dimension {idx.d}")
    
    vector_id_col_idx = col_names.index("vector_id")
    old_vector_ids = [r[vector_id_col_idx] for r in reddit_rows]

    extracted_vecs = [idx.reconstruct(vid) for vid in old_vector_ids]
    extracted_arr = np.array(extracted_vecs, dtype=np.float32)
    faiss.normalize_L2(extracted_arr)

    new_idx = faiss.IndexFlatIP(384)
    new_idx.add(extracted_arr)
    print(f"Created new FAISS index: {new_idx.ntotal} vectors, dimension {new_idx.d}")

    # Write new FAISS index to disk
    faiss.write_index(new_idx, str(faiss_path))
    print(f"Successfully saved new FAISS index to {faiss_path} ({faiss_path.stat().st_size / (1024*1024):.2f} MB)")

    # 3. Rebuild SQLite chunk_metadata with re-indexed vector_ids 0..10209
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS chunk_metadata_new;")
    c.execute("""
        CREATE TABLE chunk_metadata_new (
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
            relevance_reason TEXT,
            source_dataset TEXT DEFAULT 'master_corpus'
        );
    """)

    # Prepare rows with new continuous vector_id (0 to len(reddit_rows)-1)
    new_records = []
    for new_vid, r in enumerate(reddit_rows):
        r_dict = dict(zip(col_names, r))
        new_records.append((
            new_vid,
            r_dict.get("chunk_id"),
            r_dict.get("parent_doc_id"),
            r_dict.get("chunk_index", 0),
            r_dict.get("total_chunks", 1),
            r_dict.get("title"),
            r_dict.get("content"),
            r_dict.get("embedding_text"),
            r_dict.get("post_id"),
            r_dict.get("source_url"),
            r_dict.get("source_type"),
            r_dict.get("category_taxonomy"),
            r_dict.get("image_url"),
            r_dict.get("user_rating"),
            r_dict.get("char_count", 0),
            r_dict.get("word_count", 0),
            r_dict.get("relevance_score", 1.0),
            r_dict.get("quality_score", 1.0),
            r_dict.get("relevance_decision", "KEEP"),
            r_dict.get("relevance_reason", "DEFAULT_KEEP"),
            "sagar_reddit_dataset"
        ))

    c.executemany("""
        INSERT INTO chunk_metadata_new (
            vector_id, chunk_id, parent_doc_id, chunk_index, total_chunks,
            title, content, embedding_text, post_id, source_url, source_type,
            category_taxonomy, image_url, user_rating, char_count, word_count,
            relevance_score, quality_score, relevance_decision, relevance_reason,
            source_dataset
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, new_records)

    c.execute("DROP TABLE chunk_metadata;")
    c.execute("ALTER TABLE chunk_metadata_new RENAME TO chunk_metadata;")

    # Rebuild indexes
    c.execute("CREATE INDEX idx_chunk_metadata_chunk_id ON chunk_metadata(chunk_id);")
    c.execute("CREATE INDEX idx_chunk_metadata_parent_doc_id ON chunk_metadata(parent_doc_id);")
    c.execute("CREATE INDEX idx_chunk_metadata_source_type ON chunk_metadata(source_type);")
    c.execute("CREATE INDEX idx_chunk_metadata_decision ON chunk_metadata(relevance_decision);")
    c.execute("CREATE INDEX idx_chunk_metadata_source_dataset ON chunk_metadata(source_dataset);")
    conn.commit()

    print("Running VACUUM on SQLite database to reclaim free space...")
    c.execute("VACUUM;")
    conn.commit()
    conn.close()

    print(f"Vacuumed SQLite database saved ({db_path.stat().st_size / (1024*1024):.2f} MB)")

    # 4. Delete raw and intermediate news files
    if raw_news_csv.exists():
        size_mb = raw_news_csv.stat().st_size / (1024*1024)
        raw_news_csv.unlink()
        print(f"Deleted raw file: {raw_news_csv} (freed {size_mb:.2f} MB)")

    if processed_csv.exists():
        size_mb = processed_csv.stat().st_size / (1024*1024)
        processed_csv.unlink()
        print(f"Deleted intermediate file: {processed_csv} (freed {size_mb:.2f} MB)")

    # 5. Compress new seed database
    print("Generating compressed seed metadata archives...")
    for target_gz in [seed_gz_path, data_gz_path]:
        with open(db_path, "rb") as f_in:
            with gzip.open(target_gz, "wb", compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)
        print(f"Wrote compressed archive: {target_gz} ({target_gz.stat().st_size / (1024*1024):.2f} MB)")

    # 6. Final verification
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT source_dataset, COUNT(*), MIN(vector_id), MAX(vector_id) FROM chunk_metadata GROUP BY source_dataset")
    final_rows = c.fetchall()
    conn.close()

    print("\n================================================================================")
    print("FINAL POST-CLEANUP VERIFICATION")
    print("================================================================================")
    for r in final_rows:
        print(f"Dataset: {r[0]} | Total Chunks: {r[1]} | Min vector_id: {r[2]} | Max vector_id: {r[3]}")

    idx_check = faiss.read_index(str(faiss_path))
    print(f"FAISS index vector count: {idx_check.ntotal} (dimension: {idx_check.d})")
    assert len(final_rows) == 1 and final_rows[0][0] == "sagar_reddit_dataset" and final_rows[0][1] == 10210
    assert idx_check.ntotal == 10210

    print("\n[SUCCESS] master_news_corpus completely deleted, FAISS index synchronized, and disk reclaimed.")

if __name__ == "__main__":
    main()
