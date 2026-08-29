import sqlite3
from pathlib import Path

db_path = Path("data/vector_db/metadata.sqlite")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check existing columns
cursor.execute("PRAGMA table_info(chunk_metadata);")
cols = [c[1] for c in cursor.fetchall()]
print(f"Current columns ({len(cols)}):", cols)

if "source_dataset" not in cols:
    print("\nAdding 'source_dataset' column...")
    cursor.execute("ALTER TABLE chunk_metadata ADD COLUMN source_dataset TEXT DEFAULT 'master_corpus';")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_source_dataset ON chunk_metadata(source_dataset);")
    conn.commit()
    print("Migration applied successfully!")
else:
    print("\n'source_dataset' column already exists.")

# Check breakdown of origin patterns
print("\n--- Analyzing Origin Patterns ---")
queries = [
    ("Meltwater News (mo-*)", "SELECT count(*) FROM chunk_metadata WHERE parent_doc_id LIKE 'mo-%';"),
    ("Reddit Posts / Comments (reddit.com)", "SELECT count(*) FROM chunk_metadata WHERE source_url LIKE '%reddit.com%' OR parent_doc_id LIKE '%reddit.com%' OR post_id LIKE '%reddit.com%';"),
    ("Web/News URLs (http% non-reddit)", "SELECT count(*) FROM chunk_metadata WHERE (source_url LIKE 'http%' OR parent_doc_id LIKE 'http%') AND (source_url NOT LIKE '%reddit.com%' AND parent_doc_id NOT LIKE '%reddit.com%');"),
    ("Other / Unspecified", "SELECT count(*) FROM chunk_metadata WHERE parent_doc_id NOT LIKE 'mo-%' AND parent_doc_id NOT LIKE 'http%' AND (source_url IS NULL OR source_url NOT LIKE 'http%');")
]

for label, q in queries:
    cursor.execute(q)
    cnt = cursor.fetchone()[0]
    print(f"  {label}: {cnt} chunks")

# Apply Backfill Logic
print("\n--- Applying Backfill ---")
# 1. Meltwater News
cursor.execute("UPDATE chunk_metadata SET source_dataset = 'master_news_corpus' WHERE parent_doc_id LIKE 'mo-%';")

# 2. Reddit Dataset
cursor.execute("UPDATE chunk_metadata SET source_dataset = 'sagar_reddit_dataset' WHERE source_url LIKE '%reddit.com%' OR parent_doc_id LIKE '%reddit.com%' OR post_id LIKE '%reddit.com%';")

# 3. Regional / Web News articles
cursor.execute("UPDATE chunk_metadata SET source_dataset = 'master_news_corpus' WHERE source_dataset = 'master_corpus' AND (source_url LIKE 'http%' OR parent_doc_id LIKE 'http%');")

# 4. Fallback for any remainder
cursor.execute("UPDATE chunk_metadata SET source_dataset = 'master_news_corpus' WHERE source_dataset = 'master_corpus';")

conn.commit()

# Final Row Counts per source_dataset
print("\n--- Final Row Counts per source_dataset ---")
cursor.execute("SELECT source_dataset, count(*) as count, count(DISTINCT parent_doc_id) as unique_docs FROM chunk_metadata GROUP BY source_dataset;")
for r in cursor.fetchall():
    print(f"  Dataset: '{r[0]}' | Chunks: {r[1]} | Unique Parent Docs: {r[2]}")

conn.close()
