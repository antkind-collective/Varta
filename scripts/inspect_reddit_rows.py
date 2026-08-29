import sqlite3
from pathlib import Path

active_db = Path("data/vector_db/metadata.sqlite")
conn = sqlite3.connect(active_db)
cursor = conn.cursor()

cursor.execute("""
    SELECT vector_id, chunk_id, parent_doc_id, title, source_url, source_type, content
    FROM chunk_metadata
    WHERE LOWER(source_url) LIKE '%reddit%'
       OR LOWER(parent_doc_id) LIKE '%reddit%'
       OR LOWER(post_id) LIKE '%reddit%'
       OR LOWER(title) LIKE '%reddit%'
       OR LOWER(content) LIKE '%reddit.com%'
    LIMIT 20;
""")
rows = cursor.fetchall()
print(f"Found {len(rows)} matching rows in metadata.sqlite:")
for r in rows:
    title = str(r[3]).encode('ascii', 'replace').decode('ascii')
    print(f"Vector ID: {r[0]}")
    print(f"  Title: {title}")
    print(f"  Parent Doc ID: {r[2]}")
    print(f"  Source URL: {r[4]}")
    print(f"  Source Type: {r[5]}")
    print(f"  Content snippet: {str(r[6])[:150].encode('ascii', 'replace').decode('ascii')}")
    print("-" * 50)

conn.close()
