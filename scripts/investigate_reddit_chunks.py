import sqlite3
import os
from pathlib import Path

print("==================================================")
print("DEEP INVESTIGATION: REDDIT CHUNKS & SQLITE DATABASES")
print("==================================================")

# 1. Search for all SQLite/DB files in the repository
print("\n[Step 1] Locating all database files (.sqlite, .db) in workspace:")
for p in Path(".").rglob("*"):
    if p.is_file() and p.suffix.lower() in [".sqlite", ".db", ".sqlite3"]:
        print(f"  - Found DB: {p} (Size: {p.stat().st_size / (1024*1024):.2f} MB)")

# 2. Check data/vector_db/metadata.sqlite
active_db = Path("data/vector_db/metadata.sqlite")
if active_db.exists():
    conn = sqlite3.connect(active_db)
    cursor = conn.cursor()

    print(f"\n[Step 2] Inspecting active DB: {active_db}")
    
    # Check for 'reddit' across multiple columns (case-insensitive)
    search_queries = [
        ("LOWER(source_url) LIKE '%reddit%'", "SELECT count(*) FROM chunk_metadata WHERE LOWER(source_url) LIKE '%reddit%';"),
        ("LOWER(parent_doc_id) LIKE '%reddit%'", "SELECT count(*) FROM chunk_metadata WHERE LOWER(parent_doc_id) LIKE '%reddit%';"),
        ("LOWER(post_id) LIKE '%reddit%'", "SELECT count(*) FROM chunk_metadata WHERE LOWER(post_id) LIKE '%reddit%';"),
        ("LOWER(title) LIKE '%reddit%'", "SELECT count(*) FROM chunk_metadata WHERE LOWER(title) LIKE '%reddit%';"),
        ("LOWER(content) LIKE '%reddit%'", "SELECT count(*) FROM chunk_metadata WHERE LOWER(content) LIKE '%reddit%';"),
        ("LOWER(title) LIKE '%reddit moment%'", "SELECT count(*) FROM chunk_metadata WHERE LOWER(title) LIKE '%reddit moment%';"),
        ("LOWER(title) LIKE '%chennai rental%'", "SELECT count(*) FROM chunk_metadata WHERE LOWER(title) LIKE '%chennai rental%';"),
        ("LOWER(source_type) LIKE '%reddit%'", "SELECT count(*) FROM chunk_metadata WHERE LOWER(source_type) LIKE '%reddit%';")
    ]

    for label, q in search_queries:
        cursor.execute(q)
        cnt = cursor.fetchone()[0]
        print(f"  {label}: {cnt} rows")

    # Fetch sample rows if any matches
    cursor.execute("""
        SELECT vector_id, chunk_id, parent_doc_id, title, source_url, source_type, content
        FROM chunk_metadata
        WHERE LOWER(source_url) LIKE '%reddit%'
           OR LOWER(parent_doc_id) LIKE '%reddit%'
           OR LOWER(post_id) LIKE '%reddit%'
           OR LOWER(title) LIKE '%reddit%'
           OR LOWER(title) LIKE '%rental%'
        LIMIT 10;
    """)
    samples = cursor.fetchall()
    print(f"\n[Step 3] Sample matched rows in active DB ({len(samples)} found):")
    for s in samples:
        print(f"  VectorID: {s[0]} | Title: {s[3]} | SourceURL: {s[4]} | ParentDocID: {s[2]} | SourceType: {s[5]}")

    conn.close()

# 3. Check all other SQLite DB files found
for db_file in Path(".").rglob("*.sqlite"):
    if db_file != active_db:
        print(f"\n[Step 4] Checking alternate DB: {db_file}")
        try:
            c = sqlite3.connect(db_file)
            cur = c.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [t[0] for t in cur.fetchall()]
            print(f"  Tables: {tables}")
            if "chunk_metadata" in tables:
                cur.execute("SELECT count(*) FROM chunk_metadata;")
                print(f"  Total chunks: {cur.fetchone()[0]}")
                cur.execute("SELECT count(*) FROM chunk_metadata WHERE LOWER(source_url) LIKE '%reddit%' OR LOWER(title) LIKE '%reddit%';")
                print(f"  Reddit chunks: {cur.fetchone()[0]}")
            c.close()
        except Exception as e:
            print(f"  Error reading {db_file}: {e}")

# 4. Check data/ directory raw files (csv, json, uploads, etc.)
print("\n[Step 5] Checking data/ directory raw files:")
for p in Path("data").rglob("*"):
    if p.is_file() and p.suffix.lower() in [".csv", ".json", ".jsonl", ".txt"]:
        print(f"  - {p} ({p.stat().st_size / 1024:.1f} KB)")

